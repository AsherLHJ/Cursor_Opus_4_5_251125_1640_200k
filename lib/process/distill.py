"""
蒸馏任务模块 (新架构)

蒸馏任务复用查询架构：
- 数据来源: 父任务结果中 relevant="Y" 的文献集合
- 费率: 动态蒸馏费率（从 SystemConfig 获取，默认 0.1）
- Block划分: 将相关DOI按100个一组划分为Block

修复30：
- 清理未使用的函数，仅保留被 scheduler 和 paper_processor 调用的代码
- 蒸馏费率改为动态获取（遵循修复17原则）

修复31：
- 蒸馏费率在Worker初始化时缓存，避免每次处理都调用（1次 vs N次）
- 蒸馏Block存储格式改为JSON，包含bib和price，Worker直接读取无需查询
"""

import json
from typing import List
from ..redis.result_cache import ResultCache
from ..redis.task_queue import TaskQueue
from ..redis.user_cache import UserCache
from ..redis.billing import BillingQueue
from ..redis.system_config import SystemConfig


DISTILL_BLOCK_SIZE = 100  # 每个Block包含的DOI数量


class DistillWorker:
    """
    蒸馏任务Worker
    
    与普通Worker类似，但使用动态蒸馏费率（从 SystemConfig 获取）
    
    修复31优化：
    - 蒸馏费率在初始化时缓存（1次调用）
    - 从Block解析价格JSON（0次额外查询）
    """
    
    def __init__(self, uid: int, qid: str, ai_processor=None):
        from .worker import BlockWorker
        
        self.uid = uid
        self.qid = qid
        # 修复31: 缓存蒸馏费率，避免每次处理都调用
        self._distill_rate = SystemConfig.get_distill_rate()
        self._inner_worker = BlockWorker(uid, qid, ai_processor)
        # 覆盖费率
        self._inner_worker._process_paper = self._process_paper_with_distill_rate
    
    def _process_paper_with_distill_rate(self, doi: str, bib_str: str,
                                         block_key: str, price: int) -> None:
        """
        使用蒸馏费率处理文献
        
        修复31: bib_str 现在可能是JSON格式（包含bib和price）
        格式: {"bib": "实际bib内容", "price": 2}
        """
        # 修复31: 解析JSON获取实际bib和价格
        actual_bib = bib_str
        actual_price = price  # 默认使用传入价格
        
        try:
            data = json.loads(bib_str)
            if isinstance(data, dict):
                actual_bib = data.get('bib', bib_str)
                actual_price = data.get('price', price)
        except (json.JSONDecodeError, TypeError):
            # 不是JSON格式，使用原始值
            pass
        
        # 使用缓存的蒸馏费率计算扣费
        distill_price = actual_price * self._distill_rate
        
        # 解析Bib
        title, abstract = self._inner_worker._parse_bib(actual_bib)
        
        # 调用AI处理
        ai_result = self._inner_worker.ai_processor(doi, title, abstract)
        tokens_used = ai_result.pop('_tokens', 0)
        
        # 上报Token消耗
        from .tpm_accumulator import report_tokens
        if tokens_used > 0:
            report_tokens(tokens_used)
        
        # 原子扣费（蒸馏费率）
        balance = UserCache.get_balance(self.uid)
        if balance is not None and balance >= distill_price:
            new_balance = UserCache.deduct_balance(self.uid, distill_price)
            
            if new_balance is not None:
                # 写入结果
                ResultCache.set_result(
                    self.uid, self.qid, doi,
                    ai_result, block_key
                )
                
                # 写入计费流水（标记为蒸馏）
                BillingQueue.push_billing_record(
                    self.uid, self.qid, doi, distill_price
                )
                
                # 更新进度
                TaskQueue.incr_finished_count(self.uid, self.qid)
                
                self._inner_worker._processed_count += 1
    
    @property
    def _running(self):
        """代理 _inner_worker 的 _running 属性（修复29）"""
        return self._inner_worker._running
    
    @property
    def _thread(self):
        """代理 _inner_worker 的 _thread 属性（修复29）"""
        return self._inner_worker._thread
    
    def start(self):
        """启动Worker"""
        self._inner_worker.start()
    
    def stop(self):
        """停止Worker"""
        self._inner_worker.stop()


def spawn_distill_workers(uid: int, qid: str, count: int, 
                          ai_processor=None) -> List['DistillWorker']:
    """
    生产蒸馏Worker
    
    新架构优化：实际启动的Worker数量 = min(count, 待处理Block数量)
    避免启动多余的Worker
    """
    # 获取待处理Block数量
    pending_blocks = TaskQueue.get_pending_count(uid, qid)
    
    # 实际Worker数量 = min(permission/count, block数量)
    actual_count = min(count, pending_blocks) if pending_blocks > 0 else 0
    if actual_count <= 0:
        actual_count = 1  # 至少1个Worker
    
    print(f"[Distill] 任务 {qid}: {pending_blocks} 个Blocks, "
          f"请求={count}, 实际启动 {actual_count} 个DistillWorker")
    
    workers = []
    for _ in range(actual_count):
        worker = DistillWorker(uid, qid, ai_processor)
        worker.start()
        workers.append(worker)
    
    return workers
