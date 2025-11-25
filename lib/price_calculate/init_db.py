"""
数据库初始化脚本
确保价格相关的表结构正确
"""

from .price_calculator import PriceCalculator


def initialize_price_system():
    """
    初始化价格系统，确保所有必要的数据库列存在
    """
    calculator = PriceCalculator()
    try:
        print("正在初始化价格系统...")
        
        # 为ContentList表添加Price列
        calculator.add_price_column_to_contentlist()
        
        # 为query_log表添加total_cost列
        calculator.add_cost_column_to_query_log()
        
        print("价格系统初始化完成")
        
    except Exception as e:
        print(f"价格系统初始化失败: {e}")
    finally:
        calculator.close()


if __name__ == "__main__":
    initialize_price_system()