#!/usr/bin/env python3
"""Unit tests for file locking utilities."""
import sys
import tempfile
import time
from multiprocessing import Process, Queue
from pathlib import Path

import pytest

# Add lib to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lib"))

from file_lock import FileLock, atomic_write, LockTimeout


def _hold_lock_helper(lock_path: Path, q: Queue):
    """Process helper that holds lock for 2 seconds."""
    try:
        lock = FileLock(lock_path, timeout=5)
        lock.acquire()
        q.put("acquired")
        time.sleep(2)
        lock.release()
        q.put("released")
    except Exception as e:
        q.put(f"error:{e}")


def test_file_lock_basic():
    """Test basic lock acquisition and release."""
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_file = Path(tmpdir) / "test.lock"

        # Acquire lock
        lock = FileLock(lock_file)
        lock.acquire()

        # Verify lock file exists
        assert lock_file.exists(), "Lock file should exist"

        # Release lock
        lock.release()

        # Lock file can remain (that's OK)


def test_file_lock_exclusive():
    """Test that two processes cannot hold lock simultaneously."""
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_file = Path(tmpdir) / "test.lock"
        queue = Queue()

        # Start process that holds lock
        p = Process(target=_hold_lock_helper, args=(lock_file, queue))
        p.start()

        # Wait for first process to acquire lock
        msg = queue.get(timeout=2)
        assert msg == "acquired", f"First process should acquire lock, got: {msg}"

        # Try to acquire lock from main process (should timeout)
        lock = FileLock(lock_file, timeout=0.5)
        with pytest.raises(LockTimeout):
            lock.acquire()

        # Wait for first process to release
        p.join(timeout=5)


def test_file_lock_timeout():
    """Test that lock acquisition times out correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_file = Path(tmpdir) / "test.lock"

        # Acquire lock
        lock1 = FileLock(lock_file, timeout=5)
        lock1.acquire()

        try:
            # Try to acquire same lock with short timeout
            lock2 = FileLock(lock_file, timeout=0.5)
            start = time.time()
            with pytest.raises(LockTimeout):
                lock2.acquire()
            elapsed = time.time() - start
            # Should timeout around 0.5s (allow 0.2s margin)
            assert 0.3 <= elapsed <= 0.7, f"Timeout took {elapsed}s, expected ~0.5s"
        finally:
            lock1.release()


def test_file_lock_context_manager():
    """Test context manager automatic cleanup."""
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_file = Path(tmpdir) / "test.lock"

        # Use context manager
        with FileLock(lock_file, timeout=5):
            pass  # Lock held here

        # Lock should be released, we should be able to acquire it
        lock = FileLock(lock_file, timeout=0.5)
        lock.acquire()
        lock.release()


def test_atomic_write_basic():
    """Test atomic write creates file correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        target_file = Path(tmpdir) / "test.txt"
        content = "test content\n"

        atomic_write(target_file, content)

        # Verify file exists and has correct content
        assert target_file.exists(), "File should exist"
        assert target_file.read_text() == content, "Content should match"


def test_atomic_write_concurrent():
    """Test atomic write safety under concurrent access."""
    with tempfile.TemporaryDirectory() as tmpdir:
        target_file = Path(tmpdir) / "test.txt"

        # Write multiple times concurrently
        processes = []
        for i in range(5):
            content = f"content-{i}\n"
            p = Process(target=atomic_write, args=(target_file, content))
            p.start()
            processes.append(p)

        for p in processes:
            p.join(timeout=2)

        # File should exist and contain valid content from one of the writes
        assert target_file.exists(), "File should exist"
        final_content = target_file.read_text()
        assert final_content.startswith("content-"), "Content should be valid"
