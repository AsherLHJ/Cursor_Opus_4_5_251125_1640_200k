import threading
import time
import unittest
from unittest import mock

from lib.process import worker as worker_mod

class DummyAgg:
    def __init__(self, tpr=100):
        self.max_cap = 300.0
        self.running_sum = 0
        self.running_cnt = 0
        self.uid_perm = {}
        self.tpr = tpr
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
        # occupied 统一为 running_perm_sum（req/min）
        occupied = float(self.running_sum)
        return float(self.max_cap) - occupied
    def get_uid_permission(self, uid):
        return self.uid_perm.get(uid, 0)
    def set_uid_perm(self, uid, perm):
        self.uid_perm[uid] = perm
    def get_tokens_per_req(self, default):
        return self.tpr

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
        return 100
    def get_query_log_by_index(self, qi):
        return {'query_table':'t','research_question':'rq','requirements':'req'}
    def get_paper_title_abstract_by_doi(self, doi):
        return {'title':'Title','abstract':'Abstract'}
    def get_search_id_by_doi(self, table, qi, doi):
        return 1
    def update_search_result(self, *args, **kwargs):
        return True
    def compute_query_progress(self, table, qi):
        return {'completed':0,'total':0}
    def finalize_query_if_done(self, table, qi):
        return True
    def get_active_queries_info(self):
        return []
    def close_thread_connection(self):
        return True
    def get_active_api_accounts(self):
        return [{'api_key': 'test-key'}]

class TestRemainingCapacityGate(unittest.TestCase):
    def setUp(self):
        # patch limiter to always allow token acquisition
        self.p_rate = mock.MagicMock(try_acquire_for_any_account=lambda tokens: (True, {'api':'dummy'}))

    def test_pass_when_remaining_sufficient(self):
        uid = 11
        dagg = DummyAgg(tpr=100)
        dagg.set_uid_perm(uid, 2)  # expected=2
        dagg.max_cap = 5.0         # remaining initially 5
        q = InMemoryQueue()
        q.tasks.append({'task_id': 1, 'uid': uid, 'query_index':1, 'doi':'x'})
        with mock.patch.object(worker_mod, 'agg', dagg), \
             mock.patch.object(worker_mod, 'queue_manager', q), \
             mock.patch.object(worker_mod, 'db_reader', DummyDBReader()), \
           mock.patch.object(worker_mod, 'rate_limiter', self.p_rate), \
           mock.patch.object(worker_mod.search_paper, 'search_relevant_papers', return_value={'is_relevant': True, 'reason': 'ok', 'prompt_tokens':10, 'completion_tokens':5}):
            th = threading.Thread(target=worker_mod.worker_queue_loop_for_user, args=(uid,), daemon=True)
            th.start()
            th.join(timeout=2)
            self.assertTrue(q.tasks[0].get('done'))

    def test_block_when_occupied_near_max(self):
        uid = 22
        dagg = DummyAgg(tpr=100)
        dagg.set_uid_perm(uid, 2)    # expected=2
        dagg.max_cap = 2.0           # remaining=2 初始不通过（严格小于）
        # 模拟正在运行的任务：running_perm_sum=1 -> occupied=1 -> remaining=1 < expected(2)
        dagg.running_cnt = 1
        dagg.running_sum = 1
        q = InMemoryQueue()
        q.tasks.append({'task_id': 2, 'uid': uid, 'query_index':1, 'doi':'y'})
        with mock.patch.object(worker_mod, 'agg', dagg), \
             mock.patch.object(worker_mod, 'queue_manager', q), \
             mock.patch.object(worker_mod, 'db_reader', DummyDBReader()), \
           mock.patch.object(worker_mod, 'rate_limiter', self.p_rate), \
           mock.patch.object(worker_mod.search_paper, 'search_relevant_papers', return_value={'is_relevant': True, 'reason': 'ok', 'prompt_tokens':10, 'completion_tokens':5}):
            # 运行一小段时间，确认没有完成
            th = threading.Thread(target=worker_mod.worker_queue_loop_for_user, args=(uid,), daemon=True)
            th.start()
            time.sleep(1.0)
            self.assertIsNot(q.tasks[0].get('done'), True)
            # 提升 max，使 remaining>expected（expected=2，设置 max=10）随后应完成
            dagg.max_cap = 10.0
            th.join(timeout=3)
            self.assertTrue(q.tasks[0].get('done'))

if __name__ == '__main__':
    unittest.main()
