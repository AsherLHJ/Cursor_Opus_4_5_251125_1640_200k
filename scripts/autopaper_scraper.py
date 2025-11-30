#!/usr/bin/env python3
"""
AutoPaperWeb 高并发压力测试脚本 - HTTP API 版本

测试场景:
1. 注册100个用户 (autoTest1~autoTest100)，设置权限=2，余额=30000
2. 前50用户 (autoTest1~50) 同时发起查询
3. 前50查询全部完成后:
   - 后50用户 (autoTest51~100) 开始查询
   - 前50用户同时下载CSV和BIB结果

查询参数:
- 研究问题: 人机交互相关的任何研究
- 数据源: ANNU REV NEUROSCI, TRENDS NEUROSCI, ISMAR
- 年份范围: 2020-2025

使用方法:
  # 本地测试
  python scripts/autopaper_scraper.py --base-url http://localhost:18080

  # 生产环境测试
  python scripts/autopaper_scraper.py --production

  # 自定义下载目录
  python scripts/autopaper_scraper.py --download-dir "D:\\Downloads\\test"

Requirements:
  pip install requests
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# =============================================================================
# 配置常量
# =============================================================================

DEFAULT_BASE_URL = "http://localhost:18080"
PRODUCTION_URL = "https://autopapersearch.com"

# 管理员凭据
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Paper2025"

# 测试用户配置
TEST_USER_PASSWORD = "123456"
TEST_USER_PERMISSION = 2
TEST_USER_BALANCE = 30000.0
TOTAL_USERS = 100

# 查询参数
SEARCH_QUESTION = "人机交互相关的任何研究"
SEARCH_REQUIREMENTS = ""
SEARCH_JOURNALS = ["ANNU REV NEUROSCI", "TRENDS NEUROSCI", "ISMAR"]
SEARCH_START_YEAR = "2020"
SEARCH_END_YEAR = "2025"

# 下载目录
DEFAULT_DOWNLOAD_DIR = Path(r"C:\Users\Asher\Downloads\testDownloadFile")

# 并发配置
PHASE1_USER_COUNT = 50  # 第一阶段用户数 (1-50)
PHASE2_USER_COUNT = 50  # 第二阶段用户数 (51-100)
SETUP_CONCURRENCY = 20   # 账户设置并发数
QUERY_CONCURRENCY = 50   # 查询并发数
DOWNLOAD_CONCURRENCY = 50  # 下载并发数

# 轮询配置
PROGRESS_POLL_INTERVAL = 5  # 进度轮询间隔(秒)
DOWNLOAD_POLL_INTERVAL = 1  # 下载状态轮询间隔(秒)
PROGRESS_TIMEOUT = 3600     # 查询超时时间(秒)
DOWNLOAD_TIMEOUT = 300      # 下载超时时间(秒)

# 结果文件
RESULTS_DIR = Path("results")
PERFORMANCE_FILE = Path("performance.csv")
TEST_REPORT_FILE = Path("test_report.csv")


# =============================================================================
# 数据类定义
# =============================================================================

@dataclass
class TestAccount:
    """测试账户"""
    username: str
    user_id: int = 0
    uid: int = 0
    token: str = ""
    query_id: str = ""
    query_start_time: Optional[datetime] = None
    query_end_time: Optional[datetime] = None
    query_completed: bool = False
    csv_downloaded: bool = False
    bib_downloaded: bool = False
    download_start_time: Optional[datetime] = None
    download_end_time: Optional[datetime] = None
    errors: List[str] = field(default_factory=list)
    
    @property
    def query_duration(self) -> Optional[float]:
        if self.query_start_time and self.query_end_time:
            return (self.query_end_time - self.query_start_time).total_seconds()
        return None
    
    @property
    def download_duration(self) -> Optional[float]:
        if self.download_start_time and self.download_end_time:
            return (self.download_end_time - self.download_start_time).total_seconds()
        return None


@dataclass
class TestResult:
    """测试结果汇总"""
    start_time: datetime
    end_time: Optional[datetime] = None
    phase1_start: Optional[datetime] = None
    phase1_end: Optional[datetime] = None
    phase2_start: Optional[datetime] = None
    phase2_end: Optional[datetime] = None
    total_accounts: int = 0
    successful_queries: int = 0
    failed_queries: int = 0
    successful_downloads: int = 0
    failed_downloads: int = 0


# =============================================================================
# API 客户端
# =============================================================================

class APIClient:
    """HTTP API 客户端"""
    
    def __init__(self, base_url: str, timeout: int = 60):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """创建带重试机制的 Session"""
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session
    
    def _url(self, path: str) -> str:
        """构建完整URL"""
        return f"{self.base_url}{path}"
    
    def _handle_response(self, response: requests.Response, 
                         operation: str) -> Dict[str, Any]:
        """处理API响应"""
        try:
            data = response.json()
        except json.JSONDecodeError:
            raise APIError(f"{operation}: 无效的JSON响应 - {response.text[:200]}")
        
        if not response.ok:
            error_msg = data.get('message') or data.get('error') or f"HTTP {response.status_code}"
            raise APIError(f"{operation}: {error_msg}")
        
        return data
    
    # -------------------------------------------------------------------------
    # 管理员 API
    # -------------------------------------------------------------------------
    
    def admin_login(self, username: str, password: str) -> str:
        """管理员登录，返回token"""
        response = self.session.post(
            self._url('/api/admin/login'),
            json={'username': username, 'password': password},
            timeout=self.timeout
        )
        data = self._handle_response(response, "管理员登录")
        if not data.get('success'):
            raise APIError(f"管理员登录失败: {data.get('message', '未知错误')}")
        return data.get('token', '')
    
    def admin_get_users(self, admin_token: str) -> List[Dict]:
        """获取所有用户列表"""
        response = self.session.get(
            self._url('/api/admin/users'),
            headers={'Authorization': f'Bearer {admin_token}'},
            timeout=self.timeout
        )
        data = self._handle_response(response, "获取用户列表")
        return data.get('users', [])
    
    def admin_update_balance(self, admin_token: str, uid: int, balance: float) -> bool:
        """更新用户余额"""
        response = self.session.post(
            self._url('/api/admin/users/balance'),
            json={'uid': uid, 'balance': balance},
            headers={'Authorization': f'Bearer {admin_token}'},
            timeout=self.timeout
        )
        data = self._handle_response(response, "更新用户余额")
        return data.get('success', False)
    
    def admin_update_permission(self, admin_token: str, uid: int, permission: int) -> bool:
        """更新用户权限"""
        response = self.session.post(
            self._url('/api/admin/users/permission'),
            json={'uid': uid, 'permission': permission},
            headers={'Authorization': f'Bearer {admin_token}'},
            timeout=self.timeout
        )
        data = self._handle_response(response, "更新用户权限")
        return data.get('success', False)
    
    # -------------------------------------------------------------------------
    # 用户 API
    # -------------------------------------------------------------------------
    
    def register_user(self, username: str, password: str) -> Dict:
        """注册新用户"""
        response = self.session.post(
            self._url('/api/register'),
            json={'username': username, 'password': password},
            timeout=self.timeout
        )
        # 注册可能返回 "用户已存在"，这种情况不算错误
        try:
            data = response.json()
        except json.JSONDecodeError:
            raise APIError(f"注册用户: 无效的JSON响应")
        
        return data
    
    def login_user(self, username: str, password: str) -> Tuple[int, str]:
        """用户登录，返回 (uid, token)"""
        response = self.session.post(
            self._url('/api/login'),
            json={'username': username, 'password': password},
            timeout=self.timeout
        )
        data = self._handle_response(response, "用户登录")
        if not data.get('success'):
            raise APIError(f"用户登录失败: {data.get('message', '未知错误')}")
        return data.get('uid', 0), data.get('token', '')
    
    def get_user_info(self, uid: int) -> Dict:
        """获取用户信息"""
        response = self.session.get(
            self._url(f'/api/user_info?uid={uid}'),
            timeout=self.timeout
        )
        data = self._handle_response(response, "获取用户信息")
        return data
    
    # -------------------------------------------------------------------------
    # 查询 API
    # -------------------------------------------------------------------------
    
    def start_search(self, uid: int, question: str, requirements: str,
                     journals: List[str], start_year: str, end_year: str) -> str:
        """发起搜索查询，返回 query_id"""
        payload = {
            'uid': uid,
            'question': question,
            'requirements': requirements,
            'selected_journals': journals,
            'include_all_years': False,
            'start_year': start_year,
            'end_year': end_year
        }
        response = self.session.post(
            self._url('/api/start_search'),
            json=payload,
            timeout=self.timeout
        )
        data = self._handle_response(response, "开始搜索")
        if not data.get('success'):
            error = data.get('error', '')
            message = data.get('message', '未知错误')
            raise APIError(f"开始搜索失败: {error} - {message}")
        return data.get('query_id', '')
    
    def get_query_progress(self, uid: int, query_id: str) -> Dict:
        """获取查询进度"""
        response = self.session.get(
            self._url(f'/api/query_progress?uid={uid}&query_id={query_id}'),
            timeout=self.timeout
        )
        data = self._handle_response(response, "获取查询进度")
        return data
    
    def get_query_history(self, uid: int) -> List[Dict]:
        """获取查询历史"""
        response = self.session.get(
            self._url(f'/api/query_history?uid={uid}'),
            timeout=self.timeout
        )
        data = self._handle_response(response, "获取查询历史")
        return data.get('history', [])
    
    # -------------------------------------------------------------------------
    # 下载 API (异步队列模式)
    # -------------------------------------------------------------------------
    
    def create_download_task(self, uid: int, query_id: str, 
                             file_type: str) -> str:
        """创建下载任务，返回 task_id
        
        Args:
            uid: 用户ID
            query_id: 查询ID
            file_type: 'csv' 或 'bib'
        """
        payload = {
            'uid': uid,
            'query_id': query_id,
            'type': file_type
        }
        response = self.session.post(
            self._url('/api/download/create'),
            json=payload,
            timeout=self.timeout
        )
        data = self._handle_response(response, "创建下载任务")
        if not data.get('success'):
            raise APIError(f"创建下载任务失败: {data.get('message', '未知错误')}")
        return data.get('task_id', '')
    
    def get_download_status(self, task_id: str) -> Dict:
        """获取下载任务状态"""
        response = self.session.get(
            self._url(f'/api/download/status?task_id={task_id}'),
            timeout=self.timeout
        )
        data = self._handle_response(response, "获取下载状态")
        return data
    
    def download_file(self, task_id: str) -> bytes:
        """下载文件内容"""
        response = self.session.get(
            self._url(f'/api/download/file?task_id={task_id}'),
            timeout=self.timeout * 2  # 下载可能需要更长时间
        )
        if not response.ok:
            raise APIError(f"下载文件失败: HTTP {response.status_code}")
        return response.content
    
    # -------------------------------------------------------------------------
    # 兼容旧版下载 API (同步模式，作为备选)
    # -------------------------------------------------------------------------
    
    def download_csv_sync(self, uid: int, query_id: str) -> bytes:
        """同步下载CSV (兼容旧API)"""
        response = self.session.get(
            self._url(f'/api/download_csv?uid={uid}&query_id={query_id}'),
            timeout=self.timeout * 3
        )
        if not response.ok:
            raise APIError(f"下载CSV失败: HTTP {response.status_code}")
        return response.content
    
    def download_bib_sync(self, uid: int, query_id: str) -> bytes:
        """同步下载BIB (兼容旧API)"""
        response = self.session.get(
            self._url(f'/api/download_bib?uid={uid}&query_id={query_id}'),
            timeout=self.timeout * 3
        )
        if not response.ok:
            raise APIError(f"下载BIB失败: HTTP {response.status_code}")
        return response.content


class APIError(Exception):
    """API调用错误"""
    pass


# =============================================================================
# 并发测试控制器
# =============================================================================

class ConcurrencyTest:
    """高并发测试控制器"""
    
    def __init__(self, base_url: str, download_dir: Path, 
                 start_id: int = 1, end_id: int = 100):
        self.client = APIClient(base_url)
        self.download_dir = download_dir
        self.start_id = start_id
        self.end_id = end_id
        self.accounts: List[TestAccount] = []
        self.admin_token: str = ""
        self.result = TestResult(start_time=datetime.now())
        self._lock = threading.Lock()
        
        # 确保下载目录存在
        self.download_dir.mkdir(parents=True, exist_ok=True)
    
    def run(self):
        """执行完整测试流程"""
        print("=" * 70)
        print("AutoPaperWeb 高并发压力测试")
        print("=" * 70)
        print(f"服务器地址: {self.client.base_url}")
        print(f"下载目录: {self.download_dir}")
        print(f"测试用户: autoTest{self.start_id} ~ autoTest{self.end_id}")
        print(f"查询参数:")
        print(f"  - 研究问题: {SEARCH_QUESTION}")
        print(f"  - 数据源: {', '.join(SEARCH_JOURNALS)}")
        print(f"  - 年份范围: {SEARCH_START_YEAR} - {SEARCH_END_YEAR}")
        print("=" * 70)
        
        try:
            # 阶段0: 初始化账户
            self._setup_accounts()
            
            # 阶段1: 前50用户并发查询
            self._phase1_query()
            
            # 阶段2: 后50查询 + 前50下载
            self._phase2_query_and_download()
            
            # 生成报告
            self.result.end_time = datetime.now()
            self._generate_report()
            
        except Exception as e:
            print(f"\n[!] 测试过程中发生严重错误: {e}")
            import traceback
            traceback.print_exc()
            return 1
        
        return 0
    
    # -------------------------------------------------------------------------
    # 阶段0: 账户初始化
    # -------------------------------------------------------------------------
    
    def _setup_accounts(self):
        """初始化所有测试账户"""
        print("\n[阶段0] 初始化测试账户...")
        
        # 1. 管理员登录
        print(f"  [1/4] 管理员登录 ({ADMIN_USERNAME})...")
        try:
            self.admin_token = self.client.admin_login(ADMIN_USERNAME, ADMIN_PASSWORD)
            print(f"        ✓ 管理员登录成功")
        except APIError as e:
            print(f"        ✗ 管理员登录失败: {e}")
            raise
        
        # 2. 创建账户对象
        total_users = self.end_id - self.start_id + 1
        for i in range(self.start_id, self.end_id + 1):
            username = f"autoTest{i}"
            self.accounts.append(TestAccount(username=username, user_id=i))
        self.result.total_accounts = len(self.accounts)
        
        # 3. 并发注册/登录
        print(f"  [2/4] 注册/登录 {total_users} 个用户 (并发数: {SETUP_CONCURRENCY})...")
        with ThreadPoolExecutor(max_workers=SETUP_CONCURRENCY) as executor:
            futures = {executor.submit(self._register_and_login, acc): acc 
                       for acc in self.accounts}
            completed = 0
            for future in as_completed(futures):
                completed += 1
                acc = futures[future]
                try:
                    future.result()
                except Exception as e:
                    acc.errors.append(f"注册/登录失败: {e}")
                if completed % 20 == 0 or completed == total_users:
                    print(f"        进度: {completed}/{total_users}")
        
        # 统计成功数
        logged_in = sum(1 for acc in self.accounts if acc.uid > 0)
        print(f"        ✓ 登录成功: {logged_in}/{total_users}")
        
        # 4. 并发设置权限和余额
        print(f"  [3/4] 设置用户权限({TEST_USER_PERMISSION})和余额({TEST_USER_BALANCE})...")
        accounts_to_configure = [acc for acc in self.accounts if acc.uid > 0]
        with ThreadPoolExecutor(max_workers=SETUP_CONCURRENCY) as executor:
            futures = {executor.submit(self._configure_account, acc): acc 
                       for acc in accounts_to_configure}
            completed = 0
            for future in as_completed(futures):
                completed += 1
                acc = futures[future]
                try:
                    future.result()
                except Exception as e:
                    acc.errors.append(f"配置失败: {e}")
                if completed % 20 == 0 or completed == len(accounts_to_configure):
                    print(f"        进度: {completed}/{len(accounts_to_configure)}")
        
        print(f"        ✓ 账户配置完成")
        
        # 5. 验证配置
        print(f"  [4/4] 验证账户配置...")
        sample_accounts = self.accounts[:3]
        for acc in sample_accounts:
            if acc.uid > 0:
                try:
                    info = self.client.get_user_info(acc.uid)
                    balance = info.get('balance', 0)
                    print(f"        {acc.username}: uid={acc.uid}, balance={balance}")
                except Exception as e:
                    print(f"        {acc.username}: 验证失败 - {e}")
        
        print(f"\n[阶段0] 完成 - {logged_in} 个账户已就绪")
    
    def _register_and_login(self, account: TestAccount):
        """注册并登录单个账户"""
        username = account.username
        
        # 尝试注册
        try:
            result = self.client.register_user(username, TEST_USER_PASSWORD)
            # 注册成功或用户已存在都可以继续
        except APIError:
            pass  # 忽略注册错误，尝试登录
        
        # 登录
        uid, token = self.client.login_user(username, TEST_USER_PASSWORD)
        account.uid = uid
        account.token = token
    
    def _configure_account(self, account: TestAccount):
        """配置单个账户的权限和余额"""
        if account.uid <= 0:
            return
        
        # 更新余额
        self.client.admin_update_balance(self.admin_token, account.uid, TEST_USER_BALANCE)
        
        # 更新权限
        self.client.admin_update_permission(self.admin_token, account.uid, TEST_USER_PERMISSION)
    
    # -------------------------------------------------------------------------
    # 阶段1: 前50用户并发查询
    # -------------------------------------------------------------------------
    
    def _phase1_query(self):
        """阶段1: 前50用户并发查询"""
        print("\n" + "=" * 70)
        print("[阶段1] 前50用户并发查询")
        print("=" * 70)
        
        self.result.phase1_start = datetime.now()
        
        # 获取前50个有效账户
        phase1_accounts = [acc for acc in self.accounts[:PHASE1_USER_COUNT] if acc.uid > 0]
        print(f"  参与查询的账户数: {len(phase1_accounts)}")
        
        if not phase1_accounts:
            print("  ✗ 没有可用账户，跳过阶段1")
            return
        
        # 并发发起查询
        print(f"  [1/2] 并发发起 {len(phase1_accounts)} 个查询...")
        with ThreadPoolExecutor(max_workers=QUERY_CONCURRENCY) as executor:
            futures = {executor.submit(self._start_query, acc): acc 
                       for acc in phase1_accounts}
            for future in as_completed(futures):
                acc = futures[future]
                try:
                    future.result()
                except Exception as e:
                    acc.errors.append(f"发起查询失败: {e}")
        
        started = sum(1 for acc in phase1_accounts if acc.query_id)
        print(f"        ✓ 成功发起: {started}/{len(phase1_accounts)}")
        
        # 轮询等待所有查询完成
        print(f"  [2/2] 等待所有查询完成...")
        self._wait_for_queries(phase1_accounts)
        
        completed = sum(1 for acc in phase1_accounts if acc.query_completed)
        self.result.successful_queries += completed
        self.result.failed_queries += len(phase1_accounts) - completed
        
        self.result.phase1_end = datetime.now()
        duration = (self.result.phase1_end - self.result.phase1_start).total_seconds()
        
        print(f"\n[阶段1] 完成 - 成功: {completed}/{len(phase1_accounts)}, 耗时: {duration:.1f}秒")
    
    def _start_query(self, account: TestAccount):
        """为单个账户发起查询"""
        account.query_start_time = datetime.now()
        query_id = self.client.start_search(
            uid=account.uid,
            question=SEARCH_QUESTION,
            requirements=SEARCH_REQUIREMENTS,
            journals=SEARCH_JOURNALS,
            start_year=SEARCH_START_YEAR,
            end_year=SEARCH_END_YEAR
        )
        account.query_id = query_id
    
    def _wait_for_queries(self, accounts: List[TestAccount], timeout: int = PROGRESS_TIMEOUT):
        """等待一组查询完成"""
        pending = [acc for acc in accounts if acc.query_id and not acc.query_completed]
        start_time = time.time()
        
        while pending and (time.time() - start_time) < timeout:
            # 并发检查进度
            with ThreadPoolExecutor(max_workers=len(pending)) as executor:
                futures = {executor.submit(self._check_query_progress, acc): acc 
                           for acc in pending}
                for future in as_completed(futures):
                    acc = futures[future]
                    try:
                        future.result()
                    except Exception as e:
                        acc.errors.append(f"检查进度失败: {e}")
            
            # 更新待处理列表
            pending = [acc for acc in pending if not acc.query_completed]
            
            if pending:
                completed = len(accounts) - len(pending)
                print(f"        进度: {completed}/{len(accounts)} 完成, "
                      f"等待中: {len(pending)}")
                time.sleep(PROGRESS_POLL_INTERVAL)
        
        # 超时处理
        for acc in pending:
            acc.errors.append("查询超时")
    
    def _check_query_progress(self, account: TestAccount):
        """检查单个查询的进度"""
        progress = self.client.get_query_progress(account.uid, account.query_id)
        
        if progress.get('completed'):
            account.query_completed = True
            account.query_end_time = datetime.now()
    
    # -------------------------------------------------------------------------
    # 阶段2: 后50查询 + 前50下载
    # -------------------------------------------------------------------------
    
    def _phase2_query_and_download(self):
        """阶段2: 后50用户查询 + 前50用户下载"""
        print("\n" + "=" * 70)
        print("[阶段2] 后50用户查询 + 前50用户下载")
        print("=" * 70)
        
        self.result.phase2_start = datetime.now()
        
        # 获取各组账户
        phase1_accounts = [acc for acc in self.accounts[:PHASE1_USER_COUNT] 
                          if acc.uid > 0 and acc.query_completed]
        phase2_accounts = [acc for acc in self.accounts[PHASE1_USER_COUNT:PHASE1_USER_COUNT + PHASE2_USER_COUNT] 
                          if acc.uid > 0]
        
        print(f"  后50查询账户数: {len(phase2_accounts)}")
        print(f"  前50下载账户数: {len(phase1_accounts)}")
        
        # 使用两个线程并行执行
        query_thread = threading.Thread(
            target=self._run_phase2_queries, 
            args=(phase2_accounts,),
            name="Phase2-Query"
        )
        download_thread = threading.Thread(
            target=self._run_phase2_downloads, 
            args=(phase1_accounts,),
            name="Phase2-Download"
        )
        
        # 启动两个任务
        query_thread.start()
        download_thread.start()
        
        # 等待完成
        query_thread.join()
        download_thread.join()
        
        self.result.phase2_end = datetime.now()
        duration = (self.result.phase2_end - self.result.phase2_start).total_seconds()
        
        # 统计结果
        query_success = sum(1 for acc in phase2_accounts if acc.query_completed)
        download_success = sum(1 for acc in phase1_accounts if acc.csv_downloaded and acc.bib_downloaded)
        
        self.result.successful_queries += query_success
        self.result.failed_queries += len(phase2_accounts) - query_success
        self.result.successful_downloads = download_success
        self.result.failed_downloads = len(phase1_accounts) - download_success
        
        print(f"\n[阶段2] 完成 - 查询成功: {query_success}/{len(phase2_accounts)}, "
              f"下载成功: {download_success}/{len(phase1_accounts)}, 耗时: {duration:.1f}秒")
    
    def _run_phase2_queries(self, accounts: List[TestAccount]):
        """执行阶段2的查询任务"""
        if not accounts:
            return
        
        print(f"\n  [查询线程] 开始发起 {len(accounts)} 个查询...")
        
        # 并发发起查询
        with ThreadPoolExecutor(max_workers=QUERY_CONCURRENCY) as executor:
            futures = {executor.submit(self._start_query, acc): acc 
                       for acc in accounts}
            for future in as_completed(futures):
                acc = futures[future]
                try:
                    future.result()
                except Exception as e:
                    acc.errors.append(f"发起查询失败: {e}")
        
        started = sum(1 for acc in accounts if acc.query_id)
        print(f"  [查询线程] 成功发起: {started}/{len(accounts)}")
        
        # 等待查询完成
        print(f"  [查询线程] 等待查询完成...")
        self._wait_for_queries(accounts)
        
        completed = sum(1 for acc in accounts if acc.query_completed)
        print(f"  [查询线程] 完成: {completed}/{len(accounts)}")
    
    def _run_phase2_downloads(self, accounts: List[TestAccount]):
        """执行阶段2的下载任务"""
        if not accounts:
            return
        
        print(f"\n  [下载线程] 开始下载 {len(accounts)} 个用户的结果...")
        
        # 并发下载
        with ThreadPoolExecutor(max_workers=DOWNLOAD_CONCURRENCY) as executor:
            futures = {executor.submit(self._download_results, acc): acc 
                       for acc in accounts}
            completed = 0
            for future in as_completed(futures):
                completed += 1
                acc = futures[future]
                try:
                    future.result()
                except Exception as e:
                    acc.errors.append(f"下载失败: {e}")
                if completed % 10 == 0 or completed == len(accounts):
                    success = sum(1 for a in accounts if a.csv_downloaded and a.bib_downloaded)
                    print(f"  [下载线程] 进度: {completed}/{len(accounts)}, 成功: {success}")
        
        success = sum(1 for acc in accounts if acc.csv_downloaded and acc.bib_downloaded)
        print(f"  [下载线程] 完成: {success}/{len(accounts)}")
    
    def _download_results(self, account: TestAccount):
        """下载单个账户的CSV和BIB结果"""
        account.download_start_time = datetime.now()
        
        # 尝试使用异步下载API
        try:
            self._download_with_async_api(account)
        except Exception as async_error:
            # 如果异步API失败，回退到同步API
            print(f"      {account.username}: 异步下载失败，尝试同步下载...")
            try:
                self._download_with_sync_api(account)
            except Exception as sync_error:
                raise APIError(f"异步和同步下载都失败: {async_error} / {sync_error}")
        
        account.download_end_time = datetime.now()
    
    def _download_with_async_api(self, account: TestAccount):
        """使用异步队列API下载"""
        for file_type in ['csv', 'bib']:
            # 创建下载任务
            task_id = self.client.create_download_task(
                account.uid, account.query_id, file_type)
            
            # 轮询等待就绪
            start_time = time.time()
            while (time.time() - start_time) < DOWNLOAD_TIMEOUT:
                status = self.client.get_download_status(task_id)
                state = status.get('state', '')
                
                if state == 'READY':
                    break
                elif state == 'FAILED':
                    raise APIError(f"下载任务失败: {status.get('error', '未知错误')}")
                elif state in ('PENDING', 'PROCESSING'):
                    time.sleep(DOWNLOAD_POLL_INTERVAL)
                else:
                    raise APIError(f"未知下载状态: {state}")
            else:
                raise APIError("下载超时")
            
            # 下载文件
            content = self.client.download_file(task_id)
            
            # 保存文件
            suffix = 'csv' if file_type == 'csv' else 'bib'
            filename = f"{account.username}_Result.{suffix}"
            filepath = self.download_dir / filename
            filepath.write_bytes(content)
            
            # 标记完成
            if file_type == 'csv':
                account.csv_downloaded = True
            else:
                account.bib_downloaded = True
    
    def _download_with_sync_api(self, account: TestAccount):
        """使用同步API下载（备选方案）"""
        # 下载CSV
        content = self.client.download_csv_sync(account.uid, account.query_id)
        filepath = self.download_dir / f"{account.username}_Result.csv"
        filepath.write_bytes(content)
        account.csv_downloaded = True
        
        # 下载BIB
        content = self.client.download_bib_sync(account.uid, account.query_id)
        filepath = self.download_dir / f"{account.username}_Result.bib"
        filepath.write_bytes(content)
        account.bib_downloaded = True
    
    # -------------------------------------------------------------------------
    # 报告生成
    # -------------------------------------------------------------------------
    
    def _generate_report(self):
        """生成测试报告"""
        print("\n" + "=" * 70)
        print("测试报告")
        print("=" * 70)
        
        # 总体统计
        total_duration = (self.result.end_time - self.result.start_time).total_seconds()
        print(f"\n总体统计:")
        print(f"  - 总耗时: {total_duration:.1f} 秒")
        print(f"  - 测试账户数: {self.result.total_accounts}")
        print(f"  - 查询成功: {self.result.successful_queries}")
        print(f"  - 查询失败: {self.result.failed_queries}")
        print(f"  - 下载成功: {self.result.successful_downloads}")
        print(f"  - 下载失败: {self.result.failed_downloads}")
        
        # 阶段统计
        if self.result.phase1_start and self.result.phase1_end:
            phase1_duration = (self.result.phase1_end - self.result.phase1_start).total_seconds()
            print(f"\n阶段1 (前50用户查询):")
            print(f"  - 耗时: {phase1_duration:.1f} 秒")
        
        if self.result.phase2_start and self.result.phase2_end:
            phase2_duration = (self.result.phase2_end - self.result.phase2_start).total_seconds()
            print(f"\n阶段2 (后50查询 + 前50下载):")
            print(f"  - 耗时: {phase2_duration:.1f} 秒")
        
        # 保存详细报告到CSV
        self._save_csv_report()
        
        # 错误汇总
        errors = [(acc.username, err) for acc in self.accounts for err in acc.errors]
        if errors:
            print(f"\n错误汇总 ({len(errors)} 个):")
            for username, error in errors[:20]:  # 只显示前20个
                print(f"  - {username}: {error}")
            if len(errors) > 20:
                print(f"  ... 还有 {len(errors) - 20} 个错误")
        
        print("\n" + "=" * 70)
        print(f"详细报告已保存到: {TEST_REPORT_FILE}")
        print(f"下载文件位于: {self.download_dir}")
        print("=" * 70)
    
    def _save_csv_report(self):
        """保存CSV格式的详细报告"""
        with open(TEST_REPORT_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'username', 'uid', 'query_id',
                'query_start_time', 'query_end_time', 'query_duration_sec',
                'query_completed',
                'csv_downloaded', 'bib_downloaded',
                'download_start_time', 'download_end_time', 'download_duration_sec',
                'errors'
            ])
            
            for acc in self.accounts:
                writer.writerow([
                    acc.username,
                    acc.uid,
                    acc.query_id,
                    acc.query_start_time.isoformat() if acc.query_start_time else '',
                    acc.query_end_time.isoformat() if acc.query_end_time else '',
                    f"{acc.query_duration:.1f}" if acc.query_duration else '',
                    acc.query_completed,
                    acc.csv_downloaded,
                    acc.bib_downloaded,
                    acc.download_start_time.isoformat() if acc.download_start_time else '',
                    acc.download_end_time.isoformat() if acc.download_end_time else '',
                    f"{acc.download_duration:.1f}" if acc.download_duration else '',
                    '; '.join(acc.errors)
                ])


# =============================================================================
# 命令行入口
# =============================================================================

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="AutoPaperWeb 高并发压力测试脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 本地测试
  python scripts/autopaper_scraper.py
  
  # 指定本地端口
  python scripts/autopaper_scraper.py --base-url http://localhost:18080
  
  # 生产环境测试
  python scripts/autopaper_scraper.py --production
  
  # 自定义下载目录
  python scripts/autopaper_scraper.py --download-dir "D:\\Downloads\\test"
  
  # 测试部分用户
  python scripts/autopaper_scraper.py --start-id 1 --end-id 10
"""
    )
    
    parser.add_argument(
        '--base-url',
        type=str,
        default=DEFAULT_BASE_URL,
        help=f"服务器地址 (默认: {DEFAULT_BASE_URL})"
    )
    
    parser.add_argument(
        '--production',
        action='store_true',
        help=f"使用生产环境 ({PRODUCTION_URL})"
    )
    
    parser.add_argument(
        '--start-id',
        type=int,
        default=1,
        help="起始用户ID (默认: 1)"
    )
    
    parser.add_argument(
        '--end-id',
        type=int,
        default=TOTAL_USERS,
        help=f"结束用户ID (默认: {TOTAL_USERS})"
    )
    
    parser.add_argument(
        '--download-dir',
        type=str,
        default=str(DEFAULT_DOWNLOAD_DIR),
        help=f"下载目录 (默认: {DEFAULT_DOWNLOAD_DIR})"
    )
    
    parser.add_argument(
        '--admin-user',
        type=str,
        default=ADMIN_USERNAME,
        help=f"管理员用户名 (默认: {ADMIN_USERNAME})"
    )
    
    parser.add_argument(
        '--admin-pass',
        type=str,
        default=ADMIN_PASSWORD,
        help="管理员密码"
    )
    
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    """主函数"""
    args = parse_args(argv)
    
    # 确定服务器地址
    base_url = PRODUCTION_URL if args.production else args.base_url
    
    # 更新全局配置（如果通过参数提供）
    global ADMIN_USERNAME, ADMIN_PASSWORD
    ADMIN_USERNAME = args.admin_user
    ADMIN_PASSWORD = args.admin_pass
    
    # 验证参数
    if args.start_id < 1:
        print("错误: start-id 必须 >= 1", file=sys.stderr)
        return 1
    
    if args.end_id < args.start_id:
        print("错误: end-id 必须 >= start-id", file=sys.stderr)
        return 1
    
    # 创建下载目录
    download_dir = Path(args.download_dir)
    
    # 执行测试
    test = ConcurrencyTest(
        base_url=base_url,
        download_dir=download_dir,
        start_id=args.start_id,
        end_id=args.end_id
    )
    
    return test.run()


if __name__ == "__main__":
    sys.exit(main())
