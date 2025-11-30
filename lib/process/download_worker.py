"""
下载Worker模块 (新架构)
实现异步下载任务处理

设计要点:
- DownloadWorkerPool 管理多个 DownloadWorker 线程
- 每个 Worker 从 download_queue 抢占任务
- 使用 Redis Pipeline 批量获取 Bib 数据
- 生成的文件存入 Redis 临时缓存 (TTL 5分钟)
"""

import io
import csv
import re
import time
import threading
from typing import Optional, Dict, List, Any

from ..redis.download import (
    DownloadQueue, 
    DOWNLOAD_STATE_PROCESSING,
    DOWNLOAD_STATE_READY,
    DOWNLOAD_STATE_FAILED,
)
from ..redis.result_cache import ResultCache
from ..redis.paper_blocks import PaperBlocks
from ..redis.connection import redis_ping


class DownloadWorker:
    """下载任务Worker"""
    
    def __init__(self, worker_id: int):
        self.worker_id = worker_id
        self._running = False
        self._thread: Optional[threading.Thread] = None
    
    def start(self) -> None:
        """启动Worker线程"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(
            target=self._worker_loop,
            name=f"DownloadWorker-{self.worker_id}",
            daemon=True
        )
        self._thread.start()
        print(f"[DownloadWorker-{self.worker_id}] 启动")
    
    def stop(self) -> None:
        """停止Worker"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        print(f"[DownloadWorker-{self.worker_id}] 停止")
    
    def _worker_loop(self) -> None:
        """Worker主循环"""
        while self._running:
            try:
                # 从队列取任务
                task = DownloadQueue.dequeue_download()
                
                if task:
                    self._process_task(task)
                else:
                    # 队列为空，等待一段时间
                    time.sleep(0.5)
            except Exception as e:
                print(f"[DownloadWorker-{self.worker_id}] 循环异常: {e}")
                time.sleep(1)
    
    def _process_task(self, task: Dict) -> None:
        """
        处理单个下载任务
        
        Args:
            task: 任务信息 {task_id, uid, qid, type, timestamp}
        """
        task_id = task.get('task_id')
        uid = task.get('uid')
        qid = task.get('qid')
        download_type = task.get('type', 'csv')
        
        if not task_id or not uid or not qid:
            print(f"[DownloadWorker-{self.worker_id}] 无效任务: {task}")
            return
        
        print(f"[DownloadWorker-{self.worker_id}] 开始处理: {task_id} (uid={uid}, qid={qid}, type={download_type})")
        
        try:
            # 更新状态为处理中
            DownloadQueue.set_processing(task_id)
            
            # 获取结果数据并生成文件
            if download_type == 'bib':
                content = self._generate_bib_file(uid, qid)
            else:
                content = self._generate_csv_file(uid, qid)
            
            if content:
                # 存储文件内容
                DownloadQueue.store_file_content(task_id, content)
                # 更新状态为就绪
                DownloadQueue.set_ready(task_id)
                print(f"[DownloadWorker-{self.worker_id}] 完成: {task_id} (大小={len(content)} bytes)")
            else:
                DownloadQueue.set_failed(task_id, "生成文件失败：无结果数据")
                print(f"[DownloadWorker-{self.worker_id}] 失败: {task_id} (无结果数据)")
                
        except Exception as e:
            error_msg = str(e)
            DownloadQueue.set_failed(task_id, error_msg)
            print(f"[DownloadWorker-{self.worker_id}] 异常: {task_id} - {error_msg}")
    
    def _generate_csv_file(self, uid: int, qid: str) -> Optional[bytes]:
        """
        生成CSV文件内容
        
        使用 Pipeline 批量获取 Bib 数据
        """
        # 获取所有结果
        results = ResultCache.get_all_results(uid, qid)
        if not results:
            return None
        
        # 收集所有 block_key -> [dois]
        block_dois: Dict[str, List[str]] = {}
        for doi, data in results.items():
            block_key = data.get('block_key', '')
            if block_key:
                if block_key not in block_dois:
                    block_dois[block_key] = []
                block_dois[block_key].append(doi)
        
        # 批量获取所有 Bib 数据
        all_bibs = PaperBlocks.batch_get_papers(block_dois) if block_dois else {}
        
        # 生成CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # 写入表头
        writer.writerow([
            'DOI', 'Title', 'Source', 'Year', 'URL', 
            'Is_Relevant', 'Reason'
        ])
        
        # 写入数据行
        for doi, data in results.items():
            ai_result = data.get('ai_result', {})
            block_key = data.get('block_key', '')
            
            # 获取 Bib 数据
            bib_str = all_bibs.get(doi, '')
            
            # 解析 Bib 提取字段
            title = self._extract_bib_field(bib_str, 'title')
            url = self._extract_bib_field(bib_str, 'url')
            year = self._extract_bib_field(bib_str, 'year')
            
            # 从 block_key 提取 source
            source = ''
            if block_key:
                parts = PaperBlocks.parse_block_key(block_key)
                if parts:
                    source = parts[0]
                    if not year:
                        year = parts[1]
            
            # 如果没有URL，从DOI生成
            if not url and doi:
                url = f"https://doi.org/{doi}"
            
            # 相关性判断
            relevant = 'N'
            reason = ''
            if isinstance(ai_result, dict):
                relevant = ai_result.get('relevant', 'N')
                reason = ai_result.get('reason', '')
            
            writer.writerow([
                doi, title, source, year, url,
                'Y' if str(relevant).upper() in ('Y', 'YES', '1', 'TRUE') else 'N',
                reason
            ])
        
        return output.getvalue().encode('utf-8-sig')  # 使用 BOM 便于 Excel 识别
    
    def _generate_bib_file(self, uid: int, qid: str) -> Optional[bytes]:
        """
        生成BIB文件内容（仅包含相关文献）
        
        使用 Pipeline 批量获取 Bib 数据
        """
        # 获取所有结果
        results = ResultCache.get_all_results(uid, qid)
        if not results:
            return None
        
        # 筛选相关的DOI
        relevant_dois = []
        block_dois: Dict[str, List[str]] = {}
        
        for doi, data in results.items():
            ai_result = data.get('ai_result', {})
            relevant = 'N'
            if isinstance(ai_result, dict):
                relevant = ai_result.get('relevant', 'N')
            
            if str(relevant).upper() in ('Y', 'YES', '1', 'TRUE'):
                relevant_dois.append(doi)
                block_key = data.get('block_key', '')
                if block_key:
                    if block_key not in block_dois:
                        block_dois[block_key] = []
                    block_dois[block_key].append(doi)
        
        if not relevant_dois:
            # 没有相关文献，返回空的BIB文件
            return b"% No relevant papers found\n"
        
        # 批量获取所有 Bib 数据
        all_bibs = PaperBlocks.batch_get_papers(block_dois) if block_dois else {}
        
        # 生成BIB内容
        bib_entries = []
        for doi in relevant_dois:
            bib_str = all_bibs.get(doi, '')
            if bib_str and bib_str.strip():
                bib_entries.append(bib_str.strip())
        
        if not bib_entries:
            return b"% No BibTeX entries found for relevant papers\n"
        
        content = "\n\n".join(bib_entries)
        return content.encode('utf-8')
    
    def _extract_bib_field(self, bib_str: str, field: str) -> str:
        """从BibTeX字符串提取指定字段"""
        if not bib_str:
            return ''
        
        try:
            # 支持 field = {value} 和 field = "value" 格式
            pattern = rf'{field}\s*=\s*[{{"](.*?)[}}"]\s*[,}}]'
            match = re.search(pattern, bib_str, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()
        except Exception:
            pass
        
        return ''


class DownloadWorkerPool:
    """下载Worker池管理器"""
    
    def __init__(self, pool_size: int = 10):
        """
        Args:
            pool_size: Worker数量，默认10个
        """
        self.pool_size = pool_size
        self.workers: List[DownloadWorker] = []
        self._started = False
    
    def start(self) -> None:
        """启动所有Worker"""
        if self._started:
            return
        
        print(f"[DownloadWorkerPool] 启动 {self.pool_size} 个 Worker")
        
        for i in range(self.pool_size):
            worker = DownloadWorker(worker_id=i)
            worker.start()
            self.workers.append(worker)
        
        self._started = True
    
    def stop(self) -> None:
        """停止所有Worker"""
        if not self._started:
            return
        
        print(f"[DownloadWorkerPool] 停止所有 Worker")
        
        for worker in self.workers:
            worker.stop()
        
        self.workers.clear()
        self._started = False
    
    def get_active_count(self) -> int:
        """获取活跃Worker数量"""
        return len(self.workers)


# ============================================================
# 全局实例和便捷函数
# ============================================================

_pool: Optional[DownloadWorkerPool] = None
_pool_lock = threading.Lock()


def get_download_pool() -> DownloadWorkerPool:
    """获取全局下载Worker池"""
    global _pool
    
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = DownloadWorkerPool()
    
    return _pool


def start_download_workers(pool_size: int = 10) -> None:
    """
    启动下载Worker池
    
    Args:
        pool_size: Worker数量
    """
    global _pool
    
    with _pool_lock:
        if _pool is None:
            _pool = DownloadWorkerPool(pool_size=pool_size)
        _pool.start()


def stop_download_workers() -> None:
    """停止下载Worker池"""
    global _pool
    
    if _pool:
        _pool.stop()


def get_download_worker_count() -> int:
    """获取当前活跃的下载Worker数量"""
    pool = get_download_pool()
    return pool.get_active_count() if pool else 0

