import threading
from collections import deque

# 论文处理相关的全局变量
result_file_name = ""
paper_data = {}
token_used = 0

# 更详细的token统计
prompt_tokens_used = 0
completion_tokens_used = 0
prompt_cache_hit_tokens_used = 0
prompt_cache_miss_tokens_used = 0

# 日志文件相关的全局变量
full_log_file = None

# 线程锁
file_write_lock = threading.Lock()
token_lock = threading.Lock()
progress_lock = threading.Lock()

# 进度跟踪相关的全局变量
# 以下旧的基于全局计数的变量已废弃（使用隔离进度桶取代）
# 保留占位以避免其他遗留代码直接引用时报错，可逐步清理调用点后再删除。
processed_papers = 0  # Deprecated: 请使用 progress_map[(uid,qidx)]['processed']
processing_times = deque(maxlen=10)  # Deprecated: 请使用 progress_map[(uid,qidx)]['times']
start_time = None  # Deprecated: 仅在 reset_progress_tracking 中作为最终统计兜底
total_papers_to_process = 0  # Deprecated: 使用桶的 total 或 DB compute_query_progress
progress_stop_event = threading.Event()
active_threads = 0  # 活跃线程数追踪
current_query_index = None  # 当前进度关联的 query_index（用于从DB读取start_time）

# ========== 新增：按 (uid, query_index) 隔离的进度 Map ==========
# 结构：progress_map[(uid, query_index)] = {
#   'processed': int,                # 已处理篇数
#   'times': deque<float>,           # 最近处理耗时窗口
#   'start_time': float,             # 进程内起始时间（兜底），优先 DB start_time
#   'total': int                     # 预期总数（初始化时写入，后续可被 DB 校正）
# }
progress_map = {}
progress_map_lock = threading.Lock()

# 当前聚焦的 uid（用于进度展示选择，默认由启动查询的入口设置）
current_uid = None

def init_progress_bucket(uid: int, query_index, total: int):
	"""若 (uid, query_index) 进度桶不存在则初始化。"""
	if uid is None or query_index is None:
		return
	key = (int(uid), str(query_index))
	with progress_map_lock:
		if key not in progress_map:
			from collections import deque as _dq
			progress_map[key] = {
				'processed': 0,
				'times': _dq(maxlen=10),
				'start_time': None,
				'total': int(total or 0)
			}

def bump_progress(uid: int, query_index, single_elapsed: float):
	"""在指定桶中增加进度（仅正常完成的任务调用）。"""
	key = (int(uid), str(query_index))
	with progress_map_lock:
		bucket = progress_map.get(key)
		if not bucket:
			return
		bucket['processed'] += 1
		try:
			bucket['times'].append(float(single_elapsed or 0.0))
		except Exception:
			pass

def set_bucket_start_time_if_absent(uid: int, query_index, ts: float):
	key = (int(uid), str(query_index))
	with progress_map_lock:
		bucket = progress_map.get(key)
		if bucket and bucket.get('start_time') is None:
			bucket['start_time'] = float(ts)

def update_bucket_total(uid: int, query_index, total: int):
	key = (int(uid), str(query_index))
	with progress_map_lock:
		bucket = progress_map.get(key)
		if bucket:
			bucket['total'] = int(total or 0)

def read_bucket(uid: int, query_index):
	key = (int(uid), str(query_index))
	with progress_map_lock:
		b = progress_map.get(key)
		if not b:
			return None
		# 返回浅拷贝避免外部改动
		return {
			'processed': b['processed'],
			'times': list(b['times']),
			'start_time': b['start_time'],
			'total': b['total']
		}

def remove_bucket(uid: int, query_index):
	key = (int(uid), str(query_index))
	with progress_map_lock:
		progress_map.pop(key, None)