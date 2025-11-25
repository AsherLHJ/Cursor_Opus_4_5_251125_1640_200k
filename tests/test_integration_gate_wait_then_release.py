import threading
import time
import unittest
from unittest import mock

from lib.process import worker as worker_mod
from lib.log import utils

"""Integration-style test (updated capacity model):
Scenario: expected_used_capacity >= remaining_capacity causes worker to wait until remaining increases.
We simulate by adjusting max_capacity and running stats.
"""

class DummyAgg:
    def __init__(self):
        self.max_cap = 400.0
        self.running_sum = 0
        self.running_cnt = 0
        self.uid_perm = {}
    # new getters used by worker
    def get_max_capacity_per_min(self, default=0.0):
        return self.max_cap
    def get_running_perm_sum(self):
        return self.running_sum
    def get_running_tasks_count(self):
        return self.running_cnt
    def incr_running_stats(self, perm):
        self.running_cnt += 1
        self.running_sum += int(perm or 0)
    def decr_running_stats(self, perm):
        self.running_cnt = max(0, self.running_cnt - 1)
        self.running_sum = max(0, self.running_sum - int(perm or 0))
    def compute_and_set_remaining_capacity_per_min(self):
        # occupied 使用 running_perm_sum（req/min）；remaining = max - occupied
        occupied = float(self.running_sum)
        return float(self.max_cap) - occupied
    def get_uid_permission(self, uid):
        return self.uid_perm.get(uid, 0)
    def set_uid_perm(self, uid, perm):
        self.uid_perm[uid] = perm

class InMemoryQueue:
    def __init__(self):
        self.tasks = []
        self.lock = threading.Lock()
    def user_backlog_size(self, uid):
        with self.lock:
            return sum(1 for t in self.tasks if t['uid']==uid and not t.get('done'))
    def peek_head_for_user(self, uid):
        with self.lock:
            for t in self.tasks:
                if t['uid']==uid and not t.get('done'):
                    return t
        return None
    def conditional_pop(self, task_id, uid):
        with self.lock:
            if self.tasks and self.tasks[0]['task_id']==task_id and self.tasks[0]['uid']==uid and not self.tasks[0].get('done'):
                return self.tasks[0]
        return None
    def mark_done(self, task_id):
        with self.lock:
            for t in self.tasks:
                if t['task_id']==task_id:
                    t['done']=True
                    return True
        return False
    def push_back_ready(self, task_id):
        return True
    def mark_failed(self, task_id, reason):
        return True

class DummyDBReader:
    def get_tokens_per_req(self, default):
        # 为测试设置较小 tpr，便于 expected < remaining 的释放场景
        return 100
    def get_query_log_by_index(self, qi):
        return {'query_table':'t','research_question':'rq','requirements':'req'}
    def get_paper_title_abstract_by_doi(self, doi):
        return {'title':'Title','abstract':'Abstract'}
    def get_search_id_by_doi(self, table, qi, doi):
        return 1
    def update_search_result(self, *args, **kwargs):
        return True
    def compute_query_progress(self, table, qi):  # 与真实 worker 签名一致 (table, query_index)
        return {'completed':0,'total':0}
    def finalize_query_if_done(self, table, qi):
        return True
    def get_active_queries_info(self):
        return []
    def close_thread_connection(self):
        return True
    def get_active_api_accounts(self):
        return [{'api_key': 'test-key'}]

class TestWorkerGateIntegration(unittest.TestCase):
    def test_wait_then_release(self):
        uid = 42
        dagg = DummyAgg()
        dagg.set_uid_perm(uid, 2)
        # expected=permission=2。初始 max=1 -> remaining=1 < 2 等待；随后提升 max>2 使通过
        dagg.max_cap = 1.0

        q = InMemoryQueue()
        q.tasks.append({'task_id': 1001, 'uid': uid, 'query_index':1, 'doi':'10.test/abc'})

        with mock.patch.object(worker_mod, 'agg', dagg), \
             mock.patch.object(worker_mod, 'queue_manager', q), \
             mock.patch.object(worker_mod, 'db_reader', DummyDBReader()), \
             mock.patch.object(worker_mod, 'rate_limiter', mock.MagicMock(try_acquire_for_any_account=lambda tokens: (True, {'api':'dummy'}))), \
             mock.patch.object(worker_mod.search_paper, 'search_relevant_papers', return_value={'is_relevant': True, 'reason': 'ok', 'prompt_tokens':10, 'completion_tokens':5}), \
             mock.patch.object(utils, 'print_and_log') as mock_log:

            result_holder = {}
            def run():
                result_holder['res'] = worker_mod.worker_queue_loop_for_user(uid)
            th = threading.Thread(target=run, daemon=True)
            th.start()

            time.sleep(1.0)  # 初始应仍在等待（gate-wait）
            self.assertIsNot(q.tasks[0].get('done'), True)

            # 增加 max_capacity，让 remaining 足够放行 expected（expected=2 < new remaining=10）
            dagg.max_cap = 10.0
            th.join(timeout=3)

            self.assertTrue(q.tasks[0].get('done'))
            self.assertGreaterEqual(result_holder.get('res', 0), 0)

            # Ensure at least one gate-wait log happened
            found_wait = any('[gate-wait-' in str(args[0]) for args, _ in getattr(mock_log, 'call_args_list', []))
            self.assertTrue(found_wait)

if __name__ == '__main__':
    unittest.main()
