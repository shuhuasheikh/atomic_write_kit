import os
import tempfile
from typing import IO, Optional, Union

__all__ = ["AtomicWriter", "atomic_write_bytes", "atomic_write_text"]


class AtomicWriter:
    """Write a file atomically.

    A temporary file is created in the same directory as the target, written to,
    flushed, optionally fsynced, and then renamed over the target with
    ``os.replace``. Readers therefore observe either the old contents or the new
    contents, never a partial write.

    The temporary file lives in the destination directory so the final rename is
    on the same filesystem and therefore atomic. Using the system temp directory
    would risk a cross-device rename, which is not atomic and can fail outright.

    The temporary file is removed if the context manager exits with an exception,
    so a failed write does not leave litter behind. Existing file mode is
    preserved unless *mode* is given explicitly.
    """

    def __init__(
        self,
        path: Union[str, bytes, os.PathLike],
        *,
        mode: Optional[int] = None,
        fsync: bool = True,
    ) -> None:
        self.path = os.fspath(path)
        self._explicit_mode = mode
        self.fsync = fsync
        self._tmp_path: Optional[str] = None
        self._file: Optional[IO[bytes]] = None
        self._dir_fd: Optional[int] = None

    def __enter__(self) -> IO[bytes]:
        directory = os.path.dirname(os.path.abspath(self.path)) or "."
        mode = self._explicit_mode
        if mode is None:
            try:
                mode = os.stat(self.path).st_mode & 0o777
            except FileNotFoundError:
                mode = 0o666

        # ``dir`` plus an empty prefix keeps the temporary name close to the
        # target name. ``delete=False`` is required because we rename it
        # ourselves; we clean up manually on failure.
        fd, tmp_path = tempfile.mkstemp(
            prefix=".atomic_write_kit-", dir=directory, suffix=".tmp"
        )
        self._tmp_path = tmp_path
        try:
            self._file = os.fdopen(fd, "wb")
        except BaseException:
            os.close(fd)
            raise

        # Apply the requested mode before any data is written so the final
        # rename never exposes a file with the wrong permissions.
        try:
            os.chmod(tmp_path, mode)
        except BaseException:
            self._cleanup()
            raise
        return self._file

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc_type is not None:
            self._cleanup()
            return False

        assert self._file is not None
        assert self._tmp_path is not None
        try:
            self._file.flush()
            if self.fsync:
                os.fsync(self._file.fileno())
            self._file.close()
            self._file = None
            os.replace(self._tmp_path, self.path)
            self._tmp_path = None
            if self.fsync:
                self._fsync_directory(os.path.dirname(os.path.abspath(self.path)) or ".")
        except BaseException:
            self._cleanup()
            raise
        return False

    def _fsync_directory(self, directory: str) -> None:
        """Flush the directory entry so the rename survives a crash.

        Some platforms (notably Windows) do not permit opening a directory for
        fsync. In that case the data is still safe; only the durability of the
        rename itself is best-effort.
        """
        try:
            fd = os.open(directory, os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(fd)
        except OSError:
            pass
        finally:
            os.close(fd)

    def _cleanup(self) -> None:
        if self._file is not None:
            try:
                self._file.close()
            except OSError:
                pass
            self._file = None
        if self._tmp_path is not None:
            try:
                os.unlink(self._tmp_path)
            except FileNotFoundError:
                pass
            self._tmp_path = None


def atomic_write_bytes(
    path: Union[str, bytes, os.PathLike],
    data: bytes,
    *,
    mode: Optional[int] = None,
    fsync: bool = True,
) -> None:
    """Write *data* to *path* atomically.

    ``mode`` defaults to the existing file's permission bits, or ``0o666``
    (subject to umask) when the file does not exist yet.
    """
    with AtomicWriter(path, mode=mode, fsync=fsync) as f:
        f.write(data)


def atomic_write_text(
    path: Union[str, bytes, os.PathLike],
    text: str,
    *,
    encoding: str = "utf-8",
    errors: str = "strict",
    mode: Optional[int] = None,
    fsync: bool = True,
) -> None:
    """Encode *text* and write it to *path* atomically."""
    atomic_write_bytes(path, text.encode(encoding, errors), mode=mode, fsync=fsync)
