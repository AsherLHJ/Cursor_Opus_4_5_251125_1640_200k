"""
工作线程模块 (新架构)
实现任务池+抢占模式的Worker

规则R4实现:
a) 任务拆解: Query -> Block Keys -> task:{uid}:{qid}:pending_blocks
b) 线程启动: 根据permission启动对应数量的Worker
c) 抢占执行: Worker循环领取Block，处理文献
d) 暂停响应: 检测pause_signal，有信号时退出
"""

import time
import threading
import json
from typing import Dict, Optional, List, Any, Callable
from ..redis.task_queue import TaskQueue
from ..redis.paper_blocks import PaperBlocks
from ..redis.result_cache import ResultCache
from ..redis.user_cache import UserCache
from ..redis.billing import BillingQueue
from ..redis.system_cache import SystemCache
from ..redis.connection import redis_ping
from .tpm_accumulator import report_tokens
from .sliding_window import get_current_tpm, get_current_rpm

# 工作线程跟踪
ACTIVE_WORKERS: Dict[threading.Thread, Dict] = {}
_workers_lock = threading.Lock()

# Worker计数器（用于日志）
_worker_counter = 0
_counter_lock = threading.Lock()


def _get_worker_id() -> int:
    """获取唯一的Worker ID"""
    global _worker_counter
    with _counter_lock:
        _worker_counter += 1
        return _worker_counter


class BlockWorker:
    """
    Block处理工作线程
    
    按照新架构规则R4/R5实现：
    - 从 task:{uid}:{qid}:pending_blocks 领取Block
    - 检查暂停信号
    - 处理Block中的每篇文献
    - 原子扣费并写入结果
    """
    
    def __init__(self, uid: int, qid: str, 
                 ai_processor: Callable[[str, str, str], Dict] = None):
        """
        Args:
            uid: 用户ID
            qid: 查询ID  
            ai_processor: AI处理函数 (doi, title, abstract) -> {relevant, reason}
        """
        self.uid = uid
        self.qid = qid
        self.worker_id = _get_worker_id()
        self.ai_processor = ai_processor or self._default_processor
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._processed_count = 0
        self._current_block: Optional[str] = None
    
    def start(self) -> None:
        """启动Worker线程"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop,
            name=f"Worker-{self.uid}-{self.qid}-{self.worker_id}",
            daemon=True
        )
        
        # 注册到活跃Worker列表
        with _workers_lock:
            ACTIVE_WORKERS[self._thread] = {
                'uid': self.uid,
                'qid': self.qid,
                'worker_id': self.worker_id,
                'start_time': time.time(),
            }
        
        self._thread.start()
        print(f"[Worker-{self.worker_id}] 启动 uid={self.uid} qid={self.qid}")
    
    def stop(self) -> None:
        """停止Worker"""
        self._running = False
    
    def _run_loop(self) -> None:
        """Worker主循环 (规则R4.c)"""
        try:
            while self._running:
                # 1. 检查终止信号（优先于暂停信号）
                if TaskQueue.is_terminated(self.uid, self.qid):
                    # 终止信号：任务被强制取消，不推回Block
                    self._current_block = None
                    print(f"[Worker-{self.worker_id}] 收到终止信号，退出")
                    break
                
                # 2. 检查暂停信号 (R4.c.i)
                if TaskQueue.is_paused(self.uid, self.qid):
                    # 如果有未处理的Block，推回队列（暂停可恢复）
                    if self._current_block:
                        TaskQueue.push_back_block(self.uid, self.qid, self._current_block)
                        self._current_block = None
                    print(f"[Worker-{self.worker_id}] 收到暂停信号，退出")
                    break
                
                # 2. 领取任务 (R4.c.ii)
                block_key = TaskQueue.pop_block(self.uid, self.qid)
                
                if not block_key:
                    # 队列为空，检查是否完成
                    if TaskQueue.is_completed(self.uid, self.qid):
                        TaskQueue.set_state(self.uid, self.qid, 'DONE')
                        print(f"[Worker-{self.worker_id}] 任务完成，退出")
                    break
                
                self._current_block = block_key
                
                # 3. 处理Block (R5规则)
                self._process_block(block_key)
                
                # 4. 更新Block完成计数 (R6规则)
                finished = TaskQueue.incr_finished_blocks(self.uid, self.qid)
                status = TaskQueue.get_status(self.uid, self.qid)
                total = status.get('total_blocks', 0) if status else 0
                
                # 完成判定前再次检查暂停/终止信号（修复9: 防止暂停后被错误标记为完成）
                if total > 0 and finished >= total:
                    # 检查是否被终止
                    if TaskQueue.is_terminated(self.uid, self.qid):
                        print(f"[Worker-{self.worker_id}] 检测到终止信号，不触发归档")
                        self._current_block = None
                        break
                    # 检查是否被暂停
                    if TaskQueue.is_paused(self.uid, self.qid):
                        print(f"[Worker-{self.worker_id}] 检测到暂停信号，不触发归档")
                        self._current_block = None
                        break
                    
                    # 只有没被暂停/终止时才设为完成
                    TaskQueue.set_state(self.uid, self.qid, 'DONE')
                    print(f"[Worker-{self.worker_id}] 所有Block处理完成")
                    # 触发归档
                    self._trigger_archive()
                
                self._current_block = None
                
        except Exception as e:
            print(f"[Worker-{self.worker_id}] 异常: {e}")
        finally:
            self._cleanup()
    
    def _process_block(self, block_key: str) -> None:
        """
        处理单个Block (规则R5)
        
        a) 获取Block中所有文献的DOI和Bib
        b) 逐篇解析并处理
        c) 原子扣费并写入结果
        """
        print(f"[Worker-{self.worker_id}] 处理Block: {block_key}")
        
        # 获取Block数据
        papers = PaperBlocks.get_block_by_key(block_key)
        if not papers:
            print(f"[Worker-{self.worker_id}] Block为空或不存在: {block_key}")
            return
        
        # 获取期刊价格
        parsed = PaperBlocks.parse_block_key(block_key)
        if parsed:
            journal, year = parsed
            price = SystemCache.get_journal_price(journal) or 1
        else:
            price = 1
        
        # 逐篇处理
        for doi, bib_str in papers.items():
            if not self._running:
                break
            
            # 再次检查暂停信号
            if TaskQueue.is_paused(self.uid, self.qid):
                break
            
            try:
                self._process_paper(doi, bib_str, block_key, price)
            except Exception as e:
                print(f"[Worker-{self.worker_id}] 处理文献失败 {doi}: {e}")
    
    def _process_paper(self, doi: str, bib_str: str, 
                       block_key: str, price: int) -> None:
        """
        处理单篇文献 (规则R5.b-d)
        """
        # 解析Bib获取标题和摘要
        title, abstract = self._parse_bib(bib_str)
        
        # 调用AI处理
        ai_result = self.ai_processor(doi, title, abstract)
        tokens_used = ai_result.pop('_tokens', 0)
        
        # 上报Token消耗
        if tokens_used > 0:
            report_tokens(tokens_used)
        
        # 原子扣费并写入结果 (R5.c)
        balance = UserCache.get_balance(self.uid)
        if balance is not None and balance >= price:
            # 扣费
            new_balance = UserCache.deduct_balance(self.uid, price)
            
            if new_balance is not None:
                # 写入结果
                ResultCache.set_result(
                    self.uid, self.qid, doi,
                    ai_result, block_key
                )
                
                # 写入计费流水
                BillingQueue.push_billing_record(
                    self.uid, self.qid, doi, price
                )
                
                # 更新进度
                TaskQueue.incr_finished_count(self.uid, self.qid)
                
                self._processed_count += 1
        else:
            print(f"[Worker-{self.worker_id}] 余额不足，跳过 {doi}")
    
    def _parse_bib(self, bib_str: str) -> tuple:
        """从Bib字符串解析标题和摘要"""
        import re
        
        title = ""
        abstract = ""
        
        try:
            # 提取title
            title_match = re.search(
                r'title\s*=\s*[{"]([^}"]+)[}"]', 
                bib_str, re.IGNORECASE
            )
            if title_match:
                title = title_match.group(1).strip()
            
            # 提取abstract
            abstract_match = re.search(
                r'abstract\s*=\s*[{"]([^}"]+)[}"]', 
                bib_str, re.IGNORECASE
            )
            if abstract_match:
                abstract = abstract_match.group(1).strip()
        except Exception:
            pass
        
        return title, abstract
    
    def _default_processor(self, doi: str, title: str, 
                           abstract: str) -> Dict:
        """默认的AI处理函数（占位）"""
        # 实际应该调用search_paper.search_relevant_papers
        return {
            'relevant': 'N',
            'reason': 'Default processor - not implemented',
            '_tokens': 0,
        }
    
    def _trigger_archive(self) -> None:
        """触发结果归档到MySQL"""
        from ..load_data.search_dao import archive_results_to_mysql
        try:
            archive_results_to_mysql(self.uid, self.qid)
        except Exception as e:
            print(f"[Worker-{self.worker_id}] 归档失败: {e}")
    
    def _cleanup(self) -> None:
        """清理Worker"""
        self._running = False
        
        # 从活跃列表移除
        with _workers_lock:
            if self._thread in ACTIVE_WORKERS:
                del ACTIVE_WORKERS[self._thread]
        
        print(f"[Worker-{self.worker_id}] 退出，处理了 {self._processed_count} 篇文献")


def spawn_workers(uid: int, qid: str, count: int,
                  ai_processor: Callable = None) -> List[BlockWorker]:
    """
    生产指定数量的Worker线程
    
    Args:
        uid: 用户ID
        qid: 查询ID
        count: Worker数量（通常等于用户permission）
        ai_processor: AI处理函数
        
    Returns:
        Worker实例列表
    """
    workers = []
    for _ in range(count):
        worker = BlockWorker(uid, qid, ai_processor)
        worker.start()
        workers.append(worker)
    
    print(f"[WorkerManager] 为 uid={uid} qid={qid} 启动了 {count} 个Worker")
    return workers


def get_active_worker_count() -> int:
    """获取当前活跃Worker数量"""
    with _workers_lock:
        return len(ACTIVE_WORKERS)


def get_active_workers_info() -> List[Dict]:
    """获取所有活跃Worker的信息"""
    with _workers_lock:
        return list(ACTIVE_WORKERS.values())


def stop_workers_for_query(uid: int, qid: str) -> int:
    """停止指定查询的所有Worker"""
    stopped = 0
    with _workers_lock:
        for thread, info in list(ACTIVE_WORKERS.items()):
            if info['uid'] == uid and info['qid'] == qid:
                # 设置暂停信号让Worker自行退出
                TaskQueue.set_pause_signal(uid, qid)
                stopped += 1
    return stopped
