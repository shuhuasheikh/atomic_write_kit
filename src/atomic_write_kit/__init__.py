"""Atomic write helpers.

Public API:

    atomic_write_bytes(path, data, *, mode=0o666, fsync=True)
    atomic_write_text(path, text, *, encoding="utf-8", errors="strict", mode=0o666, fsync=True)
    AtomicWriter(path, *, mode=0o666, fsync=True)
"""

from .core import AtomicWriter, atomic_write_bytes, atomic_write_text

__all__ = ["AtomicWriter", "atomic_write_bytes", "atomic_write_text"]
