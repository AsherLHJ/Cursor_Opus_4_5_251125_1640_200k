"""
蒸馏任务模块 (新架构)

蒸馏任务复用查询架构：
- 数据来源: 父任务结果中 relevant="Y" 的文献集合
- 费率: 0.1倍（十分之一）
- Block划分: 将相关DOI按100个一组划分为Block
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from ..redis.result_cache import ResultCache
from ..redis.task_queue import TaskQueue
from ..redis.paper_blocks import PaperBlocks
from ..redis.user_cache import UserCache
from ..redis.billing import BillingQueue
from ..load_data.query_dao import create_query_log, update_query_status
from ..load_data.paper_dao import get_paper_by_doi


# 蒸馏费率
DISTILL_RATE = 0.1
DISTILL_BLOCK_SIZE = 100  # 每个Block包含的DOI数量


def create_distill_task(uid: int, parent_qid: str, 
                        research_question: str = None,
                        requirements: str = None) -> Optional[str]:
    """
    创建蒸馏任务
    
    Args:
        uid: 用户ID
        parent_qid: 父任务（普通查询）的query_id
        research_question: 蒸馏的研究问题（可选，默认使用父任务的）
        requirements: 蒸馏的筛选要求（可选）
        
    Returns:
        蒸馏任务的query_id，或None（创建失败）
    """
    # 1. 获取父任务的相关DOI列表（优先Redis，MISS则回源MySQL）
    relevant_dois = ResultCache.get_relevant_dois(uid, parent_qid)
    
    if not relevant_dois:
        # Redis MISS（可能因为7天TTL过期），尝试从MySQL回源
        from ..load_data.search_dao import get_relevant_dois_from_mysql
        relevant_dois = get_relevant_dois_from_mysql(uid, parent_qid)
        if relevant_dois:
            print(f"[Distill] Redis MISS，从MySQL回源获取 {len(relevant_dois)} 个相关文献")
    
    if not relevant_dois:
        print(f"[Distill] 父任务 {parent_qid} 没有相关结果（Redis和MySQL均无数据）")
        return None
    
    print(f"[Distill] 父任务 {parent_qid} 有 {len(relevant_dois)} 个相关文献")
    
    # 2. 创建蒸馏任务记录
    search_params = {
        'type': 'distillation',
        'parent_qid': parent_qid,
        'research_question': research_question or '',
        'requirements': requirements or '',
        'source_dois_count': len(relevant_dois),
    }
    
    distill_qid = create_query_log(uid, search_params)
    if not distill_qid:
        print(f"[Distill] 创建任务记录失败")
        return None
    
    # 3. 将相关DOI划分为Block并入队
    block_keys = _create_distill_blocks(uid, distill_qid, relevant_dois, parent_qid)
    
    if not block_keys:
        print(f"[Distill] 创建Block失败")
        update_query_status(distill_qid, 'FAILED')
        return None
    
    # 4. 初始化任务状态
    TaskQueue.init_status(uid, distill_qid, len(block_keys))
    TaskQueue.enqueue_blocks(uid, distill_qid, block_keys)
    TaskQueue.reset_finished_count(uid, distill_qid)
    
    print(f"[Distill] 创建蒸馏任务 {distill_qid}: {len(block_keys)} 个Blocks")
    return distill_qid


def _create_distill_blocks(uid: int, qid: str, 
                           dois: List[str], parent_qid: str) -> List[str]:
    """
    为蒸馏任务创建Block
    
    将DOI列表按DISTILL_BLOCK_SIZE划分，存储到临时Block中
    
    Block Key格式: distill:{uid}:{qid}:{block_index}
    """
    from ..redis.connection import get_redis_client
    import json
    
    client = get_redis_client()
    if not client:
        return []
    
    block_keys = []
    
    # 按大小划分
    for i in range(0, len(dois), DISTILL_BLOCK_SIZE):
        batch = dois[i:i + DISTILL_BLOCK_SIZE]
        block_index = len(block_keys)
        block_key = f"distill:{uid}:{qid}:{block_index}"
        
        # 获取每个DOI的Bib信息
        block_data = {}
        for doi in batch:
            # 尝试从父任务结果中获取Block Key
            result_data = ResultCache.get_result(uid, parent_qid, doi)
            if result_data:
                parent_block_key = result_data.get('block_key', '')
                if parent_block_key:
                    # 从原Block获取Bib
                    parsed = PaperBlocks.parse_block_key(parent_block_key)
                    if parsed:
                        journal, year = parsed
                        bib = PaperBlocks.get_paper(journal, year, doi)
                        if bib:
                            block_data[doi] = bib
                            continue
            
            # 回退：从数据库获取
            paper = get_paper_by_doi(doi)
            if paper and paper.get('bib'):
                block_data[doi] = paper['bib']
        
        if block_data:
            # 存储Block（使用distill: 前缀区分）
            try:
                client.hset(block_key, mapping=block_data)
                # 设置7天过期
                client.expire(block_key, 7 * 24 * 3600)
                block_keys.append(block_key)
            except Exception as e:
                print(f"[Distill] 存储Block失败: {e}")
    
    return block_keys


def get_distill_block(block_key: str) -> Dict[str, str]:
    """
    获取蒸馏Block数据
    
    Args:
        block_key: 如 "distill:1:Q20241125...:0"
        
    Returns:
        {DOI: Bib} 字典
    """
    from ..redis.connection import get_redis_client
    
    if not block_key.startswith("distill:"):
        return {}
    
    client = get_redis_client()
    if not client:
        return {}
    
    try:
        return client.hgetall(block_key) or {}
    except Exception:
        return {}


def calculate_distill_cost(paper_count: int, base_price: int = 1) -> float:
    """
    计算蒸馏费用
    
    Args:
        paper_count: 文献数量
        base_price: 基础单价（默认1）
        
    Returns:
        蒸馏总费用（0.1倍）
    """
    return paper_count * base_price * DISTILL_RATE


def estimate_distill_cost(uid: int, parent_qid: str) -> Dict:
    """
    估算蒸馏任务费用
    
    Args:
        uid: 用户ID
        parent_qid: 父任务ID
        
    Returns:
        {relevant_count, estimated_cost, distill_rate}
    """
    relevant_dois = ResultCache.get_relevant_dois(uid, parent_qid)
    
    # Redis MISS时回源MySQL（可能因为7天TTL过期）
    if not relevant_dois:
        from ..load_data.search_dao import get_relevant_dois_from_mysql
        relevant_dois = get_relevant_dois_from_mysql(uid, parent_qid)
    
    count = len(relevant_dois)
    
    return {
        'relevant_count': count,
        'estimated_cost': calculate_distill_cost(count),
        'distill_rate': DISTILL_RATE,
    }


class DistillWorker:
    """
    蒸馏任务Worker
    
    与普通Worker类似，但使用0.1倍费率
    """
    
    def __init__(self, uid: int, qid: str, ai_processor=None):
        from .worker import BlockWorker
        
        self.uid = uid
        self.qid = qid
        self._inner_worker = BlockWorker(uid, qid, ai_processor)
        # 覆盖费率
        self._inner_worker._process_paper = self._process_paper_with_distill_rate
    
    def _process_paper_with_distill_rate(self, doi: str, bib_str: str,
                                         block_key: str, price: int) -> None:
        """使用蒸馏费率处理文献"""
        # 计算蒸馏费用
        distill_price = price * DISTILL_RATE
        
        # 调用父类方法，但使用蒸馏价格
        from .worker import BlockWorker
        
        # 解析Bib
        title, abstract = self._inner_worker._parse_bib(bib_str)
        
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
    
    def start(self):
        """启动Worker"""
        self._inner_worker.start()
    
    def stop(self):
        """停止Worker"""
        self._inner_worker.stop()


def spawn_distill_workers(uid: int, qid: str, count: int, 
                          ai_processor=None) -> List[DistillWorker]:
    """
    生产蒸馏Worker
    
    新架构优化：实际启动的Worker数量 = min(count, 待处理Block数量)
    避免启动多余的Worker
    """
    from ..redis.task_queue import TaskQueue
    
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

