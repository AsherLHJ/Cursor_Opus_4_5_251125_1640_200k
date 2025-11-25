"""门控最小测试（修正单位为 req/min）

验证核心场景：
1) expected_used_capacity = permission（req/min）
2) occupied_capacity = running_perm_sum（req/min）
3) remaining_capacity = max_capacity - occupied_capacity（req/min）
放行条件：expected < remaining
"""
import unittest
from lib.process import worker


class TestGateBehavior(unittest.TestCase):
    def test_gate_allow_when_remaining_greater(self):
        # permission=2 => expected=2
        # running_sum=2 => occupied=2
        # max=5 => remaining=3 => expected(2) < remaining(3) -> True
        self.assertTrue(worker.gate_permits(2, 100, 5.0, 2, 1))

    def test_gate_reject_when_equal_or_less(self):
        # max=4, running_sum=2 => remaining=2
        # expected=2, remaining=2 -> False（严格小于）
        self.assertFalse(worker.gate_permits(2, 100, 4.0, 2, 1))
        # expected=3, remaining=2 -> False
        self.assertFalse(worker.gate_permits(3, 100, 4.0, 2, 1))

    def test_gate_invalid_numbers(self):
        # 非法值 -> False
        self.assertFalse(worker.gate_permits("bad", 100, 4.0, 2, 1))  # type: ignore[arg-type]
        self.assertFalse(worker.gate_permits(2, "bad", 4.0, 2, 1))    # type: ignore[arg-type]


if __name__ == '__main__':
    unittest.main()
