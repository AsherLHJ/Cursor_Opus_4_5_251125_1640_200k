"""
价格计算器模块 (新架构)
实现Redis实时扣费+消费流水记录

新架构计费流程:
1. Worker处理文献时，从Redis原子扣减余额
2. 扣费成功后，将流水记录写入billing_queue:{uid}
3. BillingSyncer后台线程定期将流水批量同步到MySQL
"""

from typing import Dict, Optional, List
from ..redis.user_cache import UserCache
from ..redis.billing import BillingQueue
from ..redis.system_cache import SystemCache
from ..redis.connection import redis_ping


class PriceCalculator:
    """
    价格计算器
    
    提供期刊价格查询、余额检查、扣费等功能
    """
    
    def __init__(self):
        """初始化"""
        pass
    
    def get_journal_price(self, journal_name: str) -> int:
        """
        获取期刊单价
        
        优先从Redis缓存读取
        """
        if redis_ping():
            price = SystemCache.get_journal_price(journal_name)
            if price is not None:
                return price
        
        # 回源MySQL
        from ..load_data.db_base import _get_connection
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COALESCE(Price, 1) FROM ContentList WHERE Name = %s",
                (journal_name,)
            )
            row = cursor.fetchone()
            cursor.close()
            return int(row[0]) if row else 1
        finally:
            conn.close()
    
    def get_user_balance(self, uid: int) -> float:
        """
        获取用户余额
        
        优先从Redis缓存读取
        """
        if redis_ping():
            balance = UserCache.get_balance(uid)
            if balance is not None:
                return balance
        
        # 回源MySQL
        from ..load_data.db_base import _get_connection
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT balance FROM user_info WHERE uid = %s",
                (uid,)
            )
            row = cursor.fetchone()
            cursor.close()
            balance = float(row[0]) if row else 0.0
            
            # 写入Redis缓存
            if redis_ping():
                UserCache.set_balance(uid, balance)
            
            return balance
        finally:
            conn.close()
    
    def check_balance(self, uid: int, amount: float) -> bool:
        """检查余额是否足够"""
        balance = self.get_user_balance(uid)
        return balance >= amount
    
    def deduct_balance(self, uid: int, amount: float, 
                       qid: str = None, doi: str = None) -> bool:
        """
        扣减用户余额 (Redis原子操作)
        
        Args:
            uid: 用户ID
            amount: 扣减金额
            qid: 查询ID（可选，用于记录流水）
            doi: 文献DOI（可选，用于记录流水）
            
        Returns:
            扣减是否成功
        """
        if not uid or uid <= 0 or amount <= 0:
            return False
        
        # Redis原子扣减
        if redis_ping():
            new_balance = UserCache.deduct_balance(uid, amount)
            
            if new_balance is not None:
                # 记录消费流水
                if qid:
                    BillingQueue.push_billing_record(uid, qid, doi or '', amount)
                return True
            else:
                return False  # 余额不足
        
        # Redis不可用时回退到MySQL
        return self._deduct_balance_mysql(uid, amount)
    
    def _deduct_balance_mysql(self, uid: int, amount: float) -> bool:
        """MySQL扣减余额（回退方案）"""
        from ..load_data.db_base import _get_connection
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE user_info SET balance = balance - %s "
                "WHERE uid = %s AND balance >= %s",
                (amount, uid, amount)
            )
            conn.commit()
            success = cursor.rowcount > 0
            cursor.close()
            return success
        finally:
            conn.close()
    
    def calculate_total_cost(self, journals: List[str], 
                             paper_counts: Dict[str, int]) -> float:
        """
        计算总费用
        
        Args:
            journals: 期刊名列表
            paper_counts: {期刊名: 论文数量} 字典
        """
        total = 0.0
        
        prices = {}
        if redis_ping():
            prices = SystemCache.get_all_prices()
        
        for journal in journals:
            count = paper_counts.get(journal, 0)
            price = prices.get(journal) if prices else None
            
            if price is None:
                price = self.get_journal_price(journal)
            
            total += count * price
        
        return total
    
    def estimate_query_cost(self, journal_names: List[str],
                            year_range: Dict = None) -> Dict:
        """
        估算查询费用
        
        Args:
            journal_names: 期刊名列表
            year_range: 年份范围 {start_year, end_year, include_all}
            
        Returns:
            {total_papers, total_cost, breakdown}
        """
        from ..load_data.journal_dao import get_year_number
        
        total_papers = 0
        total_cost = 0.0
        breakdown = {}
        
        start_year = year_range.get('start_year') if year_range else None
        end_year = year_range.get('end_year') if year_range else None
        include_all = year_range.get('include_all', True) if year_range else True
        
        for journal in journal_names:
            year_counts = get_year_number(journal)
            price = self.get_journal_price(journal)
            
            if year_counts:
                if include_all:
                    count = sum(year_counts.values())
                else:
                    count = sum(
                        c for y, c in year_counts.items()
                        if (not start_year or y >= start_year) and
                           (not end_year or y <= end_year)
                    )
            else:
                count = 0
            
            cost = count * price
            total_papers += count
            total_cost += cost
            breakdown[journal] = {'papers': count, 'price': price, 'cost': cost}
        
        return {
            'total_papers': total_papers,
            'total_cost': total_cost,
            'breakdown': breakdown
        }
    
    def close(self):
        """关闭（兼容旧接口）"""
        pass


# 便捷函数
def get_price_calculator() -> PriceCalculator:
    """获取价格计算器实例"""
    return PriceCalculator()


def deduct_for_paper(uid: int, journal_name: str, 
                     qid: str = None, doi: str = None) -> bool:
    """
    为单篇文献扣费
    
    Args:
        uid: 用户ID
        journal_name: 期刊名
        qid: 查询ID
        doi: 文献DOI
        
    Returns:
        扣费是否成功
    """
    calculator = PriceCalculator()
    price = calculator.get_journal_price(journal_name)
    return calculator.deduct_balance(uid, price, qid, doi)
