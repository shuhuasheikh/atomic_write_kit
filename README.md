# atomic_write_kit

Write files atomically so readers never see a half-written file.

```python
from atomic_write_kit import atomic_write_bytes, atomic_write_text

atomic_write_bytes("config.bin", b"\x00\x01\x02")
atomic_write_text("notes.txt", "hello\n", encoding="utf-8")
```

The context manager form gives you a file object and performs the rename when the
block exits without an exception:

```python
from atomic_write_kit import AtomicWriter

with AtomicWriter("output.txt", mode=0o640) as f:
    f.write(b"first line\n")
    f.write(b"second line\n")
```

## Why this exists

A plain `open(path, "w")` truncates the destination before writing. A reader that
opens the file at the wrong moment sees an empty or partial file, and a crash
mid-write leaves the destination corrupted. This library writes to a temporary
file in the same directory and then calls `os.replace`, which is an atomic
rename on POSIX and Windows. The trade-off is that each write costs an extra
file creation and rename, plus an `fsync` of the file and its directory by
default. If you are writing many tiny files in a hot loop and can tolerate
non-durable results, pass `fsync=False` to skip the two sync calls while keeping
the atomic rename.

## Edge cases

Parent directories are not created. If the directory does not exist, the
`mkstemp` call raises `FileNotFoundError` before anything is written, and no
temporary file is created. Existing permission bits are preserved on overwrite;
new files get `0o666` masked by the process umask. The temporary file is always
removed if the write fails, so a crash during `write` does not leave a stray
`.atomic_write_kit-*.tmp` file in your directory.

## API

- `atomic_write_bytes(path, data, *, mode=None, fsync=True)`
- `atomic_write_text(path, text, *, encoding="utf-8", errors="strict", mode=None, fsync=True)`
- `AtomicWriter(path, *, mode=None, fsync=True)` — context manager yielding a
  binary file object.
