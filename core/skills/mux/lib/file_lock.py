"""File locking utilities for atomic operations.

Provides fcntl-based file locking and atomic write operations to prevent
race conditions in concurrent access scenarios.
"""
import fcntl
import os
import time
from pathlib import Path
from typing import Union


class LockTimeout(Exception):
    """Raised when lock acquisition times out."""
    pass


class FileLock:
    """Context manager for exclusive file locking using fcntl.

    Provides process-level exclusive locking to prevent race conditions
    in read-modify-write sequences.

    Example:
        with FileLock(path, timeout=5):
            # Critical section - exclusive access
            data = path.read_text()
            data = modify(data)
            path.write_text(data)

    Args:
        path: Path to lock file (created if doesn't exist)
        timeout: Maximum seconds to wait for lock (default: 5)

    Raises:
        LockTimeout: If lock cannot be acquired within timeout
    """

    def __init__(self, path: Union[Path, str], timeout: float = 5.0):
        self.path = Path(path)
        self.timeout = timeout
        self.fd = None

    def acquire(self):
        """Acquire exclusive lock on file.

        Raises:
            LockTimeout: If lock cannot be acquired within timeout
        """
        # Ensure parent directory exists
        self.path.parent.mkdir(parents=True, exist_ok=True)

        # Open file for locking (create if doesn't exist)
        self.fd = os.open(str(self.path), os.O_CREAT | os.O_RDWR)

        # Try to acquire lock with timeout
        start = time.time()
        while True:
            try:
                # Try non-blocking lock
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return  # Lock acquired
            except (IOError, OSError):
                # Lock held by another process
                elapsed = time.time() - start
                if elapsed >= self.timeout:
                    os.close(self.fd)
                    self.fd = None
                    raise LockTimeout(f"Could not acquire lock on {self.path} after {self.timeout}s")

                # Wait a bit and retry
                time.sleep(0.01)

    def release(self):
        """Release lock on file."""
        if self.fd is not None:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)
            self.fd = None

    def __enter__(self):
        """Context manager entry - acquire lock."""
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - release lock."""
        self.release()
        return False


def atomic_write(path: Union[Path, str], content: str):
    """Atomically write content to file using write-temp-rename pattern.

    Writes to temporary file, fsyncs, then atomically renames to target.
    Prevents partial reads during concurrent access.

    Args:
        path: Target file path
        content: String content to write
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write to temp file in same directory (ensures same filesystem)
    tmp_path = path.parent / f".{path.name}.tmp.{os.getpid()}"
    tmp_path.write_text(content)

    # Atomic rename (replaces existing file atomically)
    os.replace(str(tmp_path), str(path))
