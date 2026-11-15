import os
import stat
import tempfile
import unittest

from atomic_write_kit import AtomicWriter, atomic_write_bytes, atomic_write_text


class AtomicWriteTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = os.path.join(self.dir.name, "target.txt")

    def test_bytes_roundtrip(self):
        atomic_write_bytes(self.path, b"hello\x00world")
        with open(self.path, "rb") as f:
            self.assertEqual(f.read(), b"hello\x00world")

    def test_text_roundtrip(self):
        atomic_write_text(self.path, "caf\u00e9\n")
        with open(self.path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "caf\u00e9\n")

    def test_overwrite_replaces_old_content(self):
        atomic_write_bytes(self.path, b"old")
        atomic_write_bytes(self.path, b"new")
        with open(self.path, "rb") as f:
            self.assertEqual(f.read(), b"new")

    def test_no_temporary_files_left_behind(self):
        atomic_write_bytes(self.path, b"data")
        leftovers = [n for n in os.listdir(self.dir.name) if n.startswith(".atomic_write_kit-")]
        self.assertEqual(leftovers, [])

    def test_exception_leaves_original_untouched_and_no_temp(self):
        atomic_write_bytes(self.path, b"original")
        with self.assertRaises(RuntimeError):
            with AtomicWriter(self.path) as f:
                f.write(b"partial")
                raise RuntimeError("boom")
        with open(self.path, "rb") as f:
            self.assertEqual(f.read(), b"original")
        leftovers = [n for n in os.listdir(self.dir.name) if n.startswith(".atomic_write_kit-")]
        self.assertEqual(leftovers, [])

    def test_explicit_mode_is_applied(self):
        atomic_write_bytes(self.path, b"x", mode=0o640)
        self.assertEqual(stat.S_IMODE(os.stat(self.path).st_mode), 0o640)

    def test_existing_mode_is_preserved(self):
        atomic_write_bytes(self.path, b"x", mode=0o600)
        atomic_write_bytes(self.path, b"y")
        self.assertEqual(stat.S_IMODE(os.stat(self.path).st_mode), 0o600)

    def test_creates_missing_parent_directory_is_not_supported(self):
        # The library deliberately does not create parent directories; the
        # error should surface rather than being swallowed.
        missing = os.path.join(self.dir.name, "nope", "file.txt")
        with self.assertRaises(FileNotFoundError):
            atomic_write_bytes(missing, b"data")

    def test_atomic_writer_context_manager_returns_writable_binary_file(self):
        with AtomicWriter(self.path) as f:
            self.assertTrue(hasattr(f, "write"))
            f.write(b"via context")
        with open(self.path, "rb") as f:
            self.assertEqual(f.read(), b"via context")

    def test_fsync_false_still_writes(self):
        atomic_write_bytes(self.path, b"no-fsync", fsync=False)
        with open(self.path, "rb") as f:
            self.assertEqual(f.read(), b"no-fsync")

    def test_text_encoding_error_is_raised(self):
        with self.assertRaises(UnicodeEncodeError):
            atomic_write_text(self.path, "\ud800", encoding="ascii")


if __name__ == "__main__":
    unittest.main()
