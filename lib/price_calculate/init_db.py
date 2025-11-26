"""
数据库初始化脚本 (新架构)

新架构变更:
- 数据库表结构由 DB_tools/init_database.py 管理
- PriceCalculator 只负责运行时价格查询和扣费
"""


def initialize_price_system():
    """
    初始化价格系统（新架构已简化）
    
    新架构中数据库表结构由 DB_tools/init_database.py 管理，
    PriceCalculator 只负责运行时价格查询和扣费。
    """
    print("正在初始化价格系统...")
    # 新架构中无需动态添加列，表结构由 DB_tools 统一管理
    print("价格系统初始化完成")


if __name__ == "__main__":
    initialize_price_system()