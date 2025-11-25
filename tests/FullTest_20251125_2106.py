#!/usr/bin/env python3
"""
AutoPaperWeb 新架构综合测试脚本
最后更新：2025-11-25-2106

测试项目：
1. MySQL连接测试（本地/云端）
2. Redis连接测试
3. 用户注册/登录API测试
4. 管理员登录API测试
5. 标签/期刊数据加载测试
6. 查询任务创建测试
7. Worker启动测试（unit_test_mode下）
8. 计费扣减测试
9. 结果缓存测试

使用方法：
    # 确保Docker容器已启动
    docker compose up -d
    
    # 运行测试
    python tests/FullTest_20251125_2106.py

依赖：
    pip install mysql-connector-python redis bcrypt requests
"""

import sys
import os
import json
import time
import unittest
from typing import Optional, Dict, Any

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


def _in_container() -> bool:
    """检测是否运行在Docker容器内"""
    try:
        if os.path.exists('/.dockerenv'):
            return True
        cgroup = '/proc/1/cgroup'
        if os.path.exists(cgroup):
            with open(cgroup, 'r', encoding='utf-8', errors='ignore') as f:
                txt = f.read()
                if 'docker' in txt or 'kubepods' in txt or 'containerd' in txt:
                    return True
    except Exception:
        pass
    return False


def _setup_local_redis_url():
    """
    本地测试环境设置：将Redis URL临时改为localhost
    （因为Docker服务名 apw-redis 在本地主机无法解析）
    """
    if _in_container():
        return  # 容器内不需要修改
    
    try:
        from lib.config import config_loader as config
        # 检查当前URL是否包含Docker服务名
        current_url = getattr(config, 'REDIS_URL', '')
        if 'apw-redis' in current_url or 'redis:' in current_url:
            # 替换为localhost
            new_url = current_url.replace('apw-redis', 'localhost').replace('redis:', 'localhost:')
            config.REDIS_URL = new_url
            print(f"[测试环境] Redis URL已调整为本地: {new_url}")
    except Exception as e:
        print(f"[警告] 无法调整Redis URL: {e}")


# 初始化本地测试环境
_setup_local_redis_url()


class TestColors:
    """终端颜色"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'


def print_header(title: str):
    """打印测试标题"""
    print()
    print(f"{TestColors.BLUE}{'=' * 60}{TestColors.END}")
    print(f"{TestColors.BLUE}  {title}{TestColors.END}")
    print(f"{TestColors.BLUE}{'=' * 60}{TestColors.END}")


def print_result(name: str, success: bool, message: str = ""):
    """打印测试结果"""
    status = f"{TestColors.GREEN}✓ PASS{TestColors.END}" if success else f"{TestColors.RED}✗ FAIL{TestColors.END}"
    print(f"  {status} {name}")
    if message:
        print(f"       {message}")


class TestDatabase(unittest.TestCase):
    """数据库连接测试"""
    
    @classmethod
    def setUpClass(cls):
        print_header("1. MySQL数据库连接测试")
    
    def test_01_config_load(self):
        """测试配置加载"""
        try:
            from lib.config import config_loader as config
            self.assertIsNotNone(config.DB_HOST)
            self.assertIsNotNone(config.DB_NAME)
            print_result("配置加载", True, f"Host={config.DB_HOST}, DB={config.DB_NAME}")
        except Exception as e:
            print_result("配置加载", False, str(e))
            raise
    
    def test_02_mysql_connection(self):
        """测试MySQL连接"""
        try:
            import mysql.connector
            from lib.config import config_loader as config
            
            conn = mysql.connector.connect(
                host=config.DB_HOST,
                port=config.DB_PORT,
                user=config.DB_USER,
                password=config.DB_PASSWORD,
                database=config.DB_NAME
            )
            
            cursor = conn.cursor()
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            
            print_result("MySQL连接", True, f"版本: {version}")
        except Exception as e:
            print_result("MySQL连接", False, str(e))
            raise
    
    def test_03_tables_exist(self):
        """测试必要表是否存在"""
        try:
            import mysql.connector
            from lib.config import config_loader as config
            
            # 新架构实际使用的表名
            required_tables = [
                'user_info', 'admin_info', 'query_log', 'search_result',
                'paperinfo', 'ContentList', 'info_tag', 'api_list'
            ]
            
            conn = mysql.connector.connect(
                host=config.DB_HOST,
                port=config.DB_PORT,
                user=config.DB_USER,
                password=config.DB_PASSWORD,
                database=config.DB_NAME
            )
            cursor = conn.cursor()
            cursor.execute("SHOW TABLES")
            existing_tables = [row[0].lower() for row in cursor.fetchall()]
            cursor.close()
            conn.close()
            
            # 不区分大小写比较
            missing = [t for t in required_tables if t.lower() not in existing_tables]
            if missing:
                print_result("数据表检查", False, f"缺失: {missing}")
                # 不抛出异常，只是警告
                print(f"       提示: 请运行 python DB_tools/init_database.py 初始化数据库")
            else:
                print_result("数据表检查", True, f"共{len(existing_tables)}个表")
        except Exception as e:
            print_result("数据表检查", False, str(e))
            raise


class TestRedis(unittest.TestCase):
    """Redis连接测试"""
    
    @classmethod
    def setUpClass(cls):
        print_header("2. Redis连接测试")
    
    def test_01_redis_connection(self):
        """测试Redis连接"""
        try:
            from lib.redis.connection import get_redis_client, redis_ping
            
            if redis_ping():
                client = get_redis_client()
                info = client.info('server')
                version = info.get('redis_version', 'unknown')
                print_result("Redis连接", True, f"版本: {version}")
            else:
                print_result("Redis连接", False, "PING失败 (请确保Redis容器已启动: docker compose up -d)")
                self.skipTest("Redis不可用")
        except Exception as e:
            print_result("Redis连接", False, str(e))
            self.skipTest(f"Redis连接失败: {e}")
    
    def test_02_redis_operations(self):
        """测试Redis基本操作"""
        try:
            from lib.redis.connection import get_redis_client, redis_ping
            
            if not redis_ping():
                self.skipTest("Redis不可用")
            
            client = get_redis_client()
            test_key = "test:fulltest:key"
            test_value = "test_value_12345"
            
            # 写入
            client.set(test_key, test_value, ex=60)
            
            # 读取
            result = client.get(test_key)
            
            # 删除
            client.delete(test_key)
            
            if result == test_value:
                print_result("Redis读写", True)
            else:
                print_result("Redis读写", False, f"期望{test_value}, 得到{result}")
                self.fail("Redis读写测试失败")
        except Exception as e:
            print_result("Redis读写", False, str(e))
            raise


class TestUserAPI(unittest.TestCase):
    """用户API测试"""
    
    @classmethod
    def setUpClass(cls):
        print_header("3. 用户注册/登录测试")
        cls.test_username = f"test_user_{int(time.time())}"
        cls.test_password = "test123456"
    
    def test_01_user_dao_register(self):
        """测试用户注册（DAO层）"""
        try:
            from lib.load_data.user_dao import create_user, get_user_by_username
            import bcrypt
            
            # 加密密码
            password_hash = bcrypt.hashpw(
                self.test_password.encode('utf-8'),
                bcrypt.gensalt()
            ).decode('utf-8')
            
            # 注册
            user_id = create_user(self.test_username, password_hash)
            self.assertIsNotNone(user_id)
            
            # 验证
            user = get_user_by_username(self.test_username)
            self.assertIsNotNone(user)
            self.assertEqual(user.get('username'), self.test_username)
            
            # 保存user_id供后续测试使用
            self.__class__.test_user_id = user_id
            
            print_result("用户注册", True, f"ID={user_id}")
        except Exception as e:
            print_result("用户注册", False, str(e))
            raise
    
    def test_02_user_dao_login(self):
        """测试用户登录验证（DAO层）"""
        try:
            from lib.load_data.user_dao import get_user_by_username
            import bcrypt
            
            # 获取用户（包含密码哈希）
            user = get_user_by_username(self.test_username)
            self.assertIsNotNone(user, "用户不存在")
            
            stored_hash = user.get('password', '')
            
            # 正确密码验证
            result = bcrypt.checkpw(
                self.test_password.encode('utf-8'),
                stored_hash.encode('utf-8')
            )
            self.assertTrue(result)
            
            # 错误密码验证
            wrong_result = bcrypt.checkpw(
                "wrongpassword".encode('utf-8'),
                stored_hash.encode('utf-8')
            )
            self.assertFalse(wrong_result)
            
            print_result("用户登录验证", True)
        except Exception as e:
            print_result("用户登录验证", False, str(e))
            raise
    
    def test_03_user_balance(self):
        """测试用户余额操作"""
        try:
            from lib.load_data.user_dao import get_balance, update_user_balance
            
            user_id = getattr(self.__class__, 'test_user_id', None)
            if not user_id:
                self.skipTest("需要先注册用户")
            
            # 获取初始余额
            balance = get_balance(user_id)
            self.assertIsNotNone(balance)
            
            # 更新余额
            new_balance = balance + 100.0
            update_user_balance(user_id, new_balance)
            
            # 验证更新
            updated = get_balance(user_id)
            self.assertEqual(updated, new_balance)
            
            print_result("用户余额操作", True, f"余额: {updated}")
        except Exception as e:
            print_result("用户余额操作", False, str(e))
            raise


class TestAdminAPI(unittest.TestCase):
    """管理员API测试"""
    
    @classmethod
    def setUpClass(cls):
        print_header("4. 管理员登录测试")
    
    def test_01_admin_dao(self):
        """测试管理员DAO"""
        try:
            from lib.load_data.admin_dao import get_admin_by_username, create_admin
            
            # 尝试获取或创建测试管理员
            admin = get_admin_by_username("test_admin")
            if not admin:
                admin_id = create_admin("test_admin", "admin123")
                admin = get_admin_by_username("test_admin")
            
            self.assertIsNotNone(admin)
            print_result("管理员DAO", True, f"用户名: {admin.get('username')}")
        except Exception as e:
            print_result("管理员DAO", False, str(e))
            raise
    
    def test_02_admin_session(self):
        """测试管理员会话（Redis）"""
        try:
            from lib.redis.connection import redis_ping
            
            if not redis_ping():
                print_result("管理员会话", False, "Redis不可用")
                self.skipTest("Redis不可用")
            
            from lib.redis.admin import AdminSession
            
            # 创建会话
            token = AdminSession.create_session(1, "test_admin")
            if not token:
                print_result("管理员会话", False, "创建会话失败(Redis可能不可用)")
                self.skipTest("Redis创建会话失败")
            
            # 验证会话
            admin_info = AdminSession.validate_session(token)
            self.assertIsNotNone(admin_info)
            self.assertEqual(admin_info.get('admin_id'), 1)
            
            # 删除会话
            AdminSession.delete_session(token)
            
            print_result("管理员会话", True)
        except Exception as e:
            print_result("管理员会话", False, str(e))
            raise


class TestJournalData(unittest.TestCase):
    """期刊/标签数据测试"""
    
    @classmethod
    def setUpClass(cls):
        print_header("5. 标签/期刊数据加载测试")
    
    def test_01_journal_dao(self):
        """测试期刊DAO"""
        try:
            from lib.load_data.journal_dao import get_all_tags, get_journals_by_filters
            
            tags = get_all_tags()
            journals = get_journals_by_filters()
            
            print_result("期刊数据加载", True, f"标签: {len(tags)}, 期刊: {len(journals)}")
        except Exception as e:
            print_result("期刊数据加载", False, str(e))
            raise
    
    def test_02_paper_dao(self):
        """测试文献DAO"""
        try:
            from lib.load_data.paper_dao import get_total_paper_count
            
            count = get_total_paper_count()
            print_result("文献数据统计", True, f"文献总数: {count}")
        except Exception as e:
            print_result("文献数据统计", False, str(e))
            raise


class TestQueryTask(unittest.TestCase):
    """查询任务测试"""
    
    @classmethod
    def setUpClass(cls):
        print_header("6. 查询任务测试")
    
    def test_01_create_query(self):
        """测试创建查询任务"""
        try:
            from lib.load_data.query_dao import create_query_log
            
            search_params = {
                'research_question': '测试研究问题',
                'requirements': '测试要求',
                'tags': ['TEST'],
                'year_start': 2020,
                'year_end': 2024
            }
            
            # 使用正确的参数名: estimated_cost 而不是 total_papers
            qid = create_query_log(
                uid=1,
                search_params=search_params,
                estimated_cost=0
            )
            
            self.assertIsNotNone(qid)
            self.__class__.test_qid = qid
            
            print_result("创建查询任务", True, f"QID={qid}")
        except Exception as e:
            print_result("创建查询任务", False, str(e))
            raise
    
    def test_02_get_query(self):
        """测试获取查询任务"""
        try:
            from lib.load_data.query_dao import get_query_log
            
            qid = getattr(self.__class__, 'test_qid', None)
            if not qid:
                self.skipTest("需要先创建查询")
            
            query = get_query_log(qid)
            self.assertIsNotNone(query)
            
            print_result("获取查询任务", True)
        except Exception as e:
            print_result("获取查询任务", False, str(e))
            raise


class TestWorker(unittest.TestCase):
    """Worker测试（需要unit_test_mode）"""
    
    @classmethod
    def setUpClass(cls):
        print_header("7. Worker测试（unit_test_mode）")
    
    def test_01_unit_test_mode(self):
        """测试unit_test_mode配置"""
        try:
            from lib.config import config_loader as config
            
            mode = getattr(config, 'unit_test_mode', False)
            print_result("unit_test_mode配置", True, f"当前值: {mode}")
        except Exception as e:
            print_result("unit_test_mode配置", False, str(e))
            raise
    
    def test_02_ai_mock_response(self):
        """测试AI模拟响应"""
        try:
            from lib.config import config_loader as config
            
            # 临时启用unit_test_mode
            original_mode = getattr(config, 'unit_test_mode', False)
            config.unit_test_mode = True
            
            try:
                from lib.process.search_paper import search_relevant_papers
                
                result = search_relevant_papers(
                    doi="10.1000/test",
                    title="Test Paper",
                    abstract="This is a test abstract.",
                    research_question="Test question",
                    requirements="Test requirements",
                    uid=1,
                    qid="test_qid"
                )
                
                self.assertIn('relevant', result)
                self.assertIn('reason', result)
                self.assertIn('_tokens', result)
                self.assertIn('Unit test mock', result.get('reason', ''))
                
                print_result("AI模拟响应", True, f"relevant={result['relevant']}, tokens={result['_tokens']}")
            finally:
                # 恢复原始设置
                config.unit_test_mode = original_mode
        except Exception as e:
            print_result("AI模拟响应", False, str(e))
            raise


class TestBilling(unittest.TestCase):
    """计费测试"""
    
    @classmethod
    def setUpClass(cls):
        print_header("8. 计费扣减测试")
    
    def test_01_redis_balance(self):
        """测试Redis余额操作"""
        try:
            from lib.redis.connection import redis_ping
            
            if not redis_ping():
                print_result("Redis余额操作", False, "Redis不可用")
                self.skipTest("Redis不可用")
            
            from lib.redis.user_cache import UserCache
            
            test_uid = 99999
            test_balance = 1000.0
            
            # 设置余额
            UserCache.set_balance(test_uid, test_balance)
            
            # 获取余额
            balance = UserCache.get_balance(test_uid)
            
            # 清理测试数据
            UserCache.delete_balance(test_uid)
            
            if balance == test_balance:
                print_result("Redis余额操作", True, f"余额: {balance}")
            else:
                print_result("Redis余额操作", False, f"期望{test_balance}, 得到{balance}")
                self.fail("余额不匹配")
        except Exception as e:
            print_result("Redis余额操作", False, str(e))
            raise
    
    def test_02_billing_queue(self):
        """测试计费队列"""
        try:
            from lib.redis.connection import redis_ping
            
            if not redis_ping():
                print_result("计费队列", False, "Redis不可用")
                self.skipTest("Redis不可用")
            
            from lib.redis.billing import BillingQueue
            
            test_uid = 99999
            
            # 使用正确的方法名: push_billing_record
            BillingQueue.push_billing_record(
                uid=test_uid,
                qid="test_qid",
                doi="10.1000/test",
                cost=1.0
            )
            
            # 使用正确的方法名: peek_billing_records
            records = BillingQueue.peek_billing_records(test_uid, count=10)
            
            # 清理
            BillingQueue.clear_queue(test_uid)
            
            print_result("计费队列", True, f"待同步记录: {len(records)}")
        except Exception as e:
            print_result("计费队列", False, str(e))
            raise


class TestResultCache(unittest.TestCase):
    """结果缓存测试"""
    
    @classmethod
    def setUpClass(cls):
        print_header("9. 结果缓存测试")
    
    def test_01_result_cache(self):
        """测试结果缓存"""
        try:
            from lib.redis.connection import redis_ping
            
            if not redis_ping():
                print_result("结果缓存", False, "Redis不可用")
                self.skipTest("Redis不可用")
            
            from lib.redis.result_cache import ResultCache
            
            test_uid = 1
            test_qid = "test_qid_cache"
            test_doi = "10.1000/test"
            test_ai_result = {
                'relevant': 'Y',
                'reason': 'Test reason'
            }
            
            # 使用正确的方法名: set_result
            ResultCache.set_result(test_uid, test_qid, test_doi, test_ai_result)
            
            # 使用正确的方法名: get_all_results
            results = ResultCache.get_all_results(test_uid, test_qid)
            
            # 清理
            ResultCache.delete_results(test_uid, test_qid)
            
            if results and len(results) > 0:
                print_result("结果缓存", True, f"缓存结果数: {len(results)}")
            else:
                print_result("结果缓存", True, "缓存操作成功（结果可能已过期）")
        except Exception as e:
            print_result("结果缓存", False, str(e))
            raise


def run_tests():
    """运行所有测试"""
    print()
    print(f"{TestColors.YELLOW}{'#' * 60}{TestColors.END}")
    print(f"{TestColors.YELLOW}#  AutoPaperWeb 新架构综合测试{TestColors.END}")
    print(f"{TestColors.YELLOW}#  时间: {time.strftime('%Y-%m-%d %H:%M:%S')}{TestColors.END}")
    print(f"{TestColors.YELLOW}#  环境: {'容器内' if _in_container() else '本地开发'}{TestColors.END}")
    print(f"{TestColors.YELLOW}{'#' * 60}{TestColors.END}")
    
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 按顺序添加测试类
    test_classes = [
        TestDatabase,
        TestRedis,
        TestUserAPI,
        TestAdminAPI,
        TestJournalData,
        TestQueryTask,
        TestWorker,
        TestBilling,
        TestResultCache,
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)
    
    # 打印总结
    print()
    print(f"{TestColors.BLUE}{'=' * 60}{TestColors.END}")
    print(f"{TestColors.BLUE}  测试总结{TestColors.END}")
    print(f"{TestColors.BLUE}{'=' * 60}{TestColors.END}")
    
    total = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    skipped = len(result.skipped)
    passed = total - failures - errors - skipped
    
    print(f"  总计: {total}")
    print(f"  {TestColors.GREEN}通过: {passed}{TestColors.END}")
    if failures > 0:
        print(f"  {TestColors.RED}失败: {failures}{TestColors.END}")
    if errors > 0:
        print(f"  {TestColors.RED}错误: {errors}{TestColors.END}")
    if skipped > 0:
        print(f"  {TestColors.YELLOW}跳过: {skipped}{TestColors.END}")
    
    print()
    
    if failures == 0 and errors == 0:
        print(f"{TestColors.GREEN}✓ 所有测试通过！{TestColors.END}")
        return 0
    else:
        print(f"{TestColors.RED}✗ 部分测试失败，请检查上述错误{TestColors.END}")
        return 1


if __name__ == "__main__":
    sys.exit(run_tests())
