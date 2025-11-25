"""
滑动窗口模块 (新架构)
实现TPM/RPM的实时统计

滑动窗口设计:
- 容量为60个单位的队列
- 每单位存放1秒间隔内的数据
- 队列中所有单位内存储的数量之和为当前的"已使用量"
"""

import time
import threading
from collections import deque
from typing import Deque, Tuple


class SlidingWindow:
    """
    滑动窗口实现
    
    用于统计最近60秒内的累计值（TPM或RPM）
    """
    
    def __init__(self, window_size: int = 60):
        """
        Args:
            window_size: 窗口大小（秒），默认60秒
        """
        self.window_size = window_size
        self._data: Deque[Tuple[float, float]] = deque()  # (timestamp, value)
        self._lock = threading.Lock()
        self._total = 0.0
    
    def add(self, value: float) -> None:
        """
        添加一个数据点
        
        Args:
            value: 要添加的值（如Token数或请求数）
        """
        now = time.time()
        with self._lock:
            self._data.append((now, value))
            self._total += value
            self._cleanup(now)
    
    def get_total(self) -> float:
        """获取当前窗口内的总和"""
        now = time.time()
        with self._lock:
            self._cleanup(now)
            return self._total
    
    def _cleanup(self, now: float) -> None:
        """清理过期的数据点（不加锁，调用者需持有锁）"""
        cutoff = now - self.window_size
        while self._data and self._data[0][0] < cutoff:
            _, old_value = self._data.popleft()
            self._total -= old_value
        
        # 防止浮点数精度问题
        if self._total < 0:
            self._total = 0
    
    def clear(self) -> None:
        """清空窗口"""
        with self._lock:
            self._data.clear()
            self._total = 0.0
    
    def get_count(self) -> int:
        """获取窗口内的数据点数量"""
        now = time.time()
        with self._lock:
            self._cleanup(now)
            return len(self._data)


class TPMSlidingWindow(SlidingWindow):
    """
    TPM (Tokens Per Minute) 滑动窗口
    
    用于统计系统每分钟消耗的Token总数
    """
    
    def add_tokens(self, tokens: int) -> None:
        """添加Token消耗"""
        self.add(float(tokens))
    
    def get_tpm(self) -> int:
        """获取当前TPM"""
        return int(self.get_total())


class RPMSlidingWindow(SlidingWindow):
    """
    RPM (Requests Per Minute) 滑动窗口
    
    用于统计系统每分钟发送的请求总数
    """
    
    def add_request(self) -> None:
        """添加一次请求"""
        self.add(1.0)
    
    def get_rpm(self) -> int:
        """获取当前RPM"""
        return int(self.get_total())


# 全局滑动窗口实例
_tpm_window = TPMSlidingWindow(60)
_rpm_window = RPMSlidingWindow(60)


def get_tpm_window() -> TPMSlidingWindow:
    """获取全局TPM滑动窗口"""
    return _tpm_window


def get_rpm_window() -> RPMSlidingWindow:
    """获取全局RPM滑动窗口"""
    return _rpm_window


def report_api_usage(tokens: int) -> None:
    """
    上报一次API调用的使用量
    
    Args:
        tokens: 本次调用消耗的Token数
    """
    _tpm_window.add_tokens(tokens)
    _rpm_window.add_request()


def get_current_tpm() -> int:
    """获取当前系统TPM"""
    return _tpm_window.get_tpm()


def get_current_rpm() -> int:
    """获取当前系统RPM"""
    return _rpm_window.get_rpm()


def reset_windows() -> None:
    """重置所有窗口（用于测试）"""
    _tpm_window.clear()
    _rpm_window.clear()

