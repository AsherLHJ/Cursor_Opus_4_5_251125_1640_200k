"""
TPM累加器模块 (新架构)
以1秒为周期收集所有Worker线程上报的Token消耗，然后发送给滑动窗口

设计:
- 每个Worker线程调用report_tokens()上报Token
- 累加器以1秒为周期汇总并发送给TPM滑动窗口
- 发送完成后清空内部数据
"""

import time
import threading
from typing import Optional
from .sliding_window import get_tpm_window, get_rpm_window


class TPMAccumulator:
    """
    TPM累加器
    
    职责: 以1秒为周期统计收到的tokens数值总和，
    然后发送给滑动窗口，发送后清空内部数据
    """
    
    def __init__(self, interval: float = 1.0):
        """
        Args:
            interval: 累加周期（秒），默认1秒
        """
        self.interval = interval
        self._tokens = 0
        self._requests = 0
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
    
    def start(self) -> None:
        """启动累加器后台线程"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._accumulate_loop, daemon=True)
        self._thread.start()
    
    def stop(self) -> None:
        """停止累加器"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
    
    def report(self, tokens: int) -> None:
        """
        上报一次API调用的Token消耗
        
        Args:
            tokens: 本次调用消耗的Token数（包含发送和接收）
        """
        if tokens <= 0:
            return
        
        with self._lock:
            self._tokens += tokens
            self._requests += 1
    
    def _accumulate_loop(self) -> None:
        """累加器后台循环"""
        last_flush = time.time()
        
        while self._running:
            time.sleep(0.1)  # 100ms检查间隔
            
            now = time.time()
            if now - last_flush >= self.interval:
                self._flush()
                last_flush = now
    
    def _flush(self) -> None:
        """将累积的数据发送给滑动窗口"""
        with self._lock:
            tokens = self._tokens
            requests = self._requests
            self._tokens = 0
            self._requests = 0
        
        if tokens > 0:
            tpm_window = get_tpm_window()
            tpm_window.add_tokens(tokens)
        
        if requests > 0:
            rpm_window = get_rpm_window()
            for _ in range(requests):
                rpm_window.add_request()
    
    def get_pending(self) -> tuple:
        """获取当前待发送的累积值（用于调试）"""
        with self._lock:
            return (self._tokens, self._requests)


# 全局累加器实例
_accumulator: Optional[TPMAccumulator] = None
_accumulator_lock = threading.Lock()


def get_accumulator() -> TPMAccumulator:
    """获取全局TPM累加器"""
    global _accumulator
    
    if _accumulator is None:
        with _accumulator_lock:
            if _accumulator is None:
                _accumulator = TPMAccumulator()
    
    return _accumulator


def start_accumulator() -> None:
    """启动全局累加器"""
    acc = get_accumulator()
    acc.start()


def stop_accumulator() -> None:
    """停止全局累加器"""
    global _accumulator
    if _accumulator:
        _accumulator.stop()


def report_tokens(tokens: int) -> None:
    """
    上报Token消耗
    
    Worker线程每次收到AI响应后调用此函数
    
    Args:
        tokens: response.usage.total_tokens 的值
    """
    acc = get_accumulator()
    acc.report(tokens)

