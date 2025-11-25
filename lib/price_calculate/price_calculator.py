"""
检索点价格计算器
负责计算检索任务的花费和扣费操作
"""

import mysql.connector
from typing import List, Dict, Optional
from ..config import config_loader as config


class PriceCalculator:
    """检索点价格计算器"""
    
    def __init__(self):
        self.connection = None
    
    def _get_connection(self):
        """获取数据库连接"""
        if self.connection and self.connection.is_connected():
            return self.connection
            
        # 优先用 config_loader 中的 DB_*，若缺失则从根目录 config.json 兜底读取
        host = getattr(config, 'DB_HOST', None)
        port = getattr(config, 'DB_PORT', None)
        user = getattr(config, 'DB_USER', None)
        password = getattr(config, 'DB_PASSWORD', None)
        database = getattr(config, 'DB_NAME', None)

        if not host or not user or not database:
            import json, os
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'config.json')
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
            except Exception:
                cfg = {}
            host = host or cfg.get('DB_HOST', '127.0.0.1')
            port = port or cfg.get('DB_PORT', 3306)
            user = user or cfg.get('DB_USER', 'root')
            password = password or cfg.get('DB_PASSWORD', '')
            database = database or cfg.get('DB_NAME', 'PaperDB')

        try:
            port = int(port or 3306)
        except Exception:
            port = 3306

        self.connection = mysql.connector.connect(
            host=host,
            port=port,
            user=str(user or ''),
            password=str(password or ''),
            database=str(database or '')
        )
        return self.connection
    
    def get_journal_price(self, journal_name: str) -> int:
        """
        获取指定期刊/会议的单篇文章检索价格
        
        Args:
            journal_name: 期刊/会议名称
            
        Returns:
            int: 单篇文章检索价格（检索点），如果未找到则返回1
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT Price FROM ContentList WHERE Name = %s", (journal_name,))
                result = cursor.fetchone()
                if result and result[0] is not None:
                    return int(result[0])
                else:
                    # 如果没有找到价格信息，返回默认价格1
                    return 1
        except Exception as e:
            print(f"获取期刊价格失败: {e}")
            return 1
    
    def calculate_total_cost(self, selected_journals: List[str], paper_counts: Dict[str, int]) -> Dict[str, int]:
        """
        计算总的检索花费
        
        Args:
            selected_journals: 选中的期刊/会议名称列表
            paper_counts: 每个期刊的论文数量 {journal_name: count}
            
        Returns:
            Dict: {"total_cost": 总花费, "journal_costs": {journal_name: cost}}
        """
        total_cost = 0
        journal_costs = {}
        
        for journal_name in selected_journals:
            price_per_paper = self.get_journal_price(journal_name)
            paper_count = paper_counts.get(journal_name, 0)
            journal_cost = price_per_paper * paper_count
            
            journal_costs[journal_name] = journal_cost
            total_cost += journal_cost
        
        return {
            "total_cost": total_cost,
            "journal_costs": journal_costs
        }
    
    def get_user_balance(self, uid: int) -> float:
        """
        获取用户余额
        
        Args:
            uid: 用户ID
            
        Returns:
            float: 用户余额
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT balance FROM user_info WHERE uid = %s", (uid,))
                result = cursor.fetchone()
                if result and result[0] is not None:
                    return float(result[0])
                else:
                    return 0.0
        except Exception as e:
            print(f"获取用户余额失败: {e}")
            return 0.0
    
    def deduct_balance(self, uid: int, amount: float) -> bool:
        """
        扣除用户余额
        
        Args:
            uid: 用户ID
            amount: 扣除金额
            
        Returns:
            bool: 是否扣除成功
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                # 检查余额是否充足
                current_balance = self.get_user_balance(uid)
                if current_balance < amount:
                    return False
                
                # 扣除余额
                new_balance = current_balance - amount
                cursor.execute("UPDATE user_info SET balance = %s WHERE uid = %s", (new_balance, uid))
                conn.commit()
                return True
        except Exception as e:
            print(f"扣除用户余额失败: {e}")
            conn.rollback()
            return False
    
    def add_price_column_to_contentlist(self):
        """
        为ContentList表添加Price列（如果不存在）
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                # 检查Price列是否存在
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM information_schema.columns 
                    WHERE table_schema = DATABASE() 
                    AND table_name = 'ContentList' 
                    AND column_name = 'Price'
                """)
                (count,) = cursor.fetchone()
                
                if count == 0:
                    # 添加Price列，默认值为1
                    cursor.execute("ALTER TABLE ContentList ADD COLUMN Price INT NOT NULL DEFAULT 1")
                    conn.commit()
                    print("已为ContentList表添加Price列")
        except Exception as e:
            print(f"添加Price列失败: {e}")
        finally:
            conn.close()

    def add_actual_cost_column_to_query_log(self):
        """
        确保 query_log.actual_cost 为 DECIMAL(10,1) NOT NULL DEFAULT 0.0
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT DATA_TYPE, COLUMN_TYPE
                    FROM information_schema.columns 
                    WHERE table_schema = DATABASE() 
                      AND table_name = 'query_log' 
                      AND column_name = 'actual_cost'
                """)
                row = cursor.fetchone()
                if not row:
                    cursor.execute("ALTER TABLE query_log ADD COLUMN actual_cost DECIMAL(10,1) NOT NULL DEFAULT 0.0")
                    conn.commit()
                    print("已为query_log表添加actual_cost列")
                else:
                    _, column_type = row
                    if str(column_type).lower() != 'decimal(10,1)':
                        cursor.execute("ALTER TABLE query_log MODIFY COLUMN actual_cost DECIMAL(10,1) NOT NULL DEFAULT 0.0")
                        conn.commit()
                        print("已修正query_log表actual_cost列类型")
        except Exception as e:
            print(f"添加/修正actual_cost列失败: {e}")
            try:
                conn.rollback()
            except Exception:
                pass
        finally:
            conn.close()
    
    def add_cost_column_to_query_log(self):
        """
        确保 query_log.total_cost 为 DECIMAL(10,1) NOT NULL DEFAULT 0.0
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT DATA_TYPE, COLUMN_TYPE
                    FROM information_schema.columns 
                    WHERE table_schema = DATABASE() 
                      AND table_name = 'query_log' 
                      AND column_name = 'total_cost'
                """)
                row = cursor.fetchone()
                if not row:
                    cursor.execute("ALTER TABLE query_log ADD COLUMN total_cost DECIMAL(10,1) NOT NULL DEFAULT 0.0")
                    conn.commit()
                else:
                    data_type, column_type = row
                    if str(column_type).lower() != 'decimal(10,1)':
                        cursor.execute("ALTER TABLE query_log MODIFY COLUMN total_cost DECIMAL(10,1) NOT NULL DEFAULT 0.0")
                        conn.commit()
        except Exception as e:
            print(f"添加/修正total_cost列失败: {e}")
            try:
                conn.rollback()
            except Exception:
                pass
        finally:
            conn.close()
    
    def add_price_column_to_search_table(self, table_name: str):
        """
        为search_{date}表添加Price列（如果不存在）
        
        Args:
            table_name: 搜索表名称
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                # 检查Price列是否存在
                cursor.execute(f"""
                    SELECT COUNT(*) 
                    FROM information_schema.columns 
                    WHERE table_schema = DATABASE() 
                    AND table_name = '{table_name}' 
                    AND column_name = 'price'
                """)
                (count,) = cursor.fetchone()
                
                if count == 0:
                    # 添加为 DECIMAL(10,1)
                    cursor.execute(f"ALTER TABLE `{table_name}` ADD COLUMN price DECIMAL(10,1) NOT NULL DEFAULT 1.0")
                    conn.commit()
                    print(f"已为{table_name}表添加price列(DECIMAL(10,1))")
                else:
                    # 若已存在但类型不为 DECIMAL(10,1)，则修正
                    cursor.execute(f"""
                        SELECT DATA_TYPE, NUMERIC_SCALE 
                        FROM information_schema.columns 
                        WHERE table_schema = DATABASE() 
                          AND table_name = '{table_name}' 
                          AND column_name = 'price'
                    """)
                    row = cursor.fetchone()
                    data_type = (row[0] or '').lower() if row else ''
                    scale = int(row[1] or 0) if row else 0
                    if data_type != 'decimal' or scale != 1:
                        cursor.execute(f"ALTER TABLE `{table_name}` MODIFY COLUMN price DECIMAL(10,1) NOT NULL DEFAULT 1.0")
                        conn.commit()
                        print(f"已修正{table_name}.price为DECIMAL(10,1)")
        except Exception as e:
            print(f"为{table_name}添加price列失败: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def close(self):
        """关闭数据库连接"""
        if self.connection and self.connection.is_connected():
            self.connection.close()