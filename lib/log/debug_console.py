import io
import sys
import threading
from pathlib import Path
from typing import Optional

_original_stdout = sys.stdout
_original_stderr = sys.stderr
_log_file_handle: Optional[io.TextIOWrapper] = None
_log_file_path: Optional[Path] = None
_init_lock = threading.Lock()
_initialized = False


def _resolve_log_root() -> Path:
    """Return the directory to store the debug console log."""
    try:
        from ..config import config_loader as config  # local import to avoid circular dependency
        folder = getattr(config, "LOG_FOLDER", None)
        if folder:
            return Path(folder).resolve()
    except Exception:
        pass
    return Path(__file__).resolve().parents[2] / "Log"


class _TeeStream(io.TextIOBase):
    """Mirror writes to both the original stream and the debug log file."""

    def __init__(self, original: io.TextIOBase, sink: io.TextIOWrapper):
        self._original = original
        self._sink = sink
        self._lock = threading.Lock()

    def write(self, s):
        if not isinstance(s, str):
            s = str(s)
        with self._lock:
            try:
                self._original.write(s)
            except Exception:
                pass
            try:
                self._sink.write(s)
                self._sink.flush()
            except Exception:
                pass
        return len(s)

    def flush(self):
        with self._lock:
            try:
                self._original.flush()
            except Exception:
                pass
            try:
                self._sink.flush()
            except Exception:
                pass

    def isatty(self):
        return getattr(self._original, "isatty", lambda: False)()

    def fileno(self):
        return getattr(self._original, "fileno", lambda: -1)()


def init_debug_console():
    """Redirect stdout/stderr to a tee that also writes to the debug log file."""
    global _initialized, _log_file_handle, _log_file_path

    if _initialized:
        return

    with _init_lock:
        if _initialized:
            return

        log_root = _resolve_log_root()
        log_root.mkdir(parents=True, exist_ok=True)
        _log_file_path = log_root / "debug_console.log"

        _log_file_handle = _log_file_path.open("a", encoding="utf-8")

        sys.stdout = _TeeStream(_original_stdout, _log_file_handle)
        sys.stderr = _TeeStream(_original_stderr, _log_file_handle)

        _initialized = True


def get_debug_log_path() -> Optional[str]:
    """Return the path to the debug console log file, initializing on demand."""
    if not _initialized:
        try:
            init_debug_console()
        except Exception:
            return None
    return str(_log_file_path) if _log_file_path else None


def close_debug_console():
    """Restore original streams and close the log file handle."""
    global _initialized, _log_file_handle
    if not _initialized:
        return
    with _init_lock:
        if not _initialized:
            return
        sys.stdout = _original_stdout
        sys.stderr = _original_stderr
        if _log_file_handle:
            try:
                _log_file_handle.flush()
                _log_file_handle.close()
            except Exception:
                pass
        _log_file_handle = None
        _initialized = False
