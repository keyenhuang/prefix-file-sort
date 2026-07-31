"""
Unit tests for the core FileGrouper business logic.

These tests import the REAL FileGrouper from ``core`` (which is intentionally
tkinter-free), so they run in any environment - including headless CI runners -
without a display server or any GUI dependencies.
"""
import unittest
import tempfile
import shutil
import os
from pathlib import Path
import sys

# Ensure the project root is importable when run directly or via pytest.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import FileGrouper


class TestFileGrouper(unittest.TestCase):
    """Test cases for FileGrouper class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.source_path = Path(self.temp_dir)
        self.grouper = FileGrouper(self.source_path)

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_allowed_extensions_empty(self):
        """Test empty filter returns None."""
        result = FileGrouper.get_allowed_extensions("")
        self.assertIsNone(result)

    def test_get_allowed_extensions_single(self):
        """Test single extension parsing."""
        result = FileGrouper.get_allowed_extensions(".mp4")
        self.assertEqual(result, [".mp4"])

    def test_get_allowed_extensions_multiple(self):
        """Test multiple extensions parsing."""
        result = FileGrouper.get_allowed_extensions(".mp4, .mkv, .avi")
        self.assertEqual(result, [".mp4", ".mkv", ".avi"])

    def test_get_allowed_extensions_without_dot(self):
        """Test extensions without leading dot are normalized."""
        result = FileGrouper.get_allowed_extensions("mp4, mkv")
        self.assertEqual(result, [".mp4", ".mkv"])

    def test_get_filtered_files_empty(self):
        """Test with empty directory."""
        files = self.grouper.get_filtered_files("")
        self.assertEqual(files, [])

    def test_get_filtered_files_with_prefix(self):
        """Test filtering files with prefix."""
        # Create test files
        (self.source_path / "01-test.mkv").touch()
        (self.source_path / "02-test.mkv").touch()
        (self.source_path / "no-prefix.txt").touch()

        files = self.grouper.get_filtered_files("")
        # Only files with '-' in name are included
        names = [f.name for f in files]
        self.assertIn("01-test.mkv", names)
        self.assertIn("02-test.mkv", names)
        self.assertIn("no-prefix.txt", names)  # "no-prefix" contains "-"

    def test_get_filtered_files_with_extension_filter(self):
        """Test filtering by extension."""
        # Create test files
        (self.source_path / "01-test.mkv").touch()
        (self.source_path / "01-test.mp4").touch()
        (self.source_path / "02-test.avi").touch()

        files = self.grouper.get_filtered_files(".mkv, .mp4")
        self.assertEqual(len(files), 2)

        names = [f.name for f in files]
        self.assertIn("01-test.mkv", names)
        self.assertIn("01-test.mp4", names)
        self.assertNotIn("02-test.avi", names)

    def test_get_filtered_files_excludes_log(self):
        """Test that move_log.json is excluded."""
        # Create test files
        (self.source_path / "01-test.mkv").touch()
        (self.source_path / "move_log.json").touch()

        files = self.grouper.get_filtered_files("")
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].name, "01-test.mkv")

    def test_preview_groups_basic(self):
        """Test basic grouping by prefix."""
        # Create test files
        (self.source_path / "01-S01E01.mkv").touch()
        (self.source_path / "01-S01E02.mkv").touch()
        (self.source_path / "02-S02E01.mkv").touch()

        groups = self.grouper.preview_groups("", " episodes", False, [], True)

        self.assertEqual(len(groups), 2)
        self.assertIn("01 episodes", groups)
        self.assertIn("02 episodes", groups)
        self.assertEqual(len(groups["01 episodes"]), 2)
        self.assertEqual(len(groups["02 episodes"]), 1)

    def test_preview_groups_numbered_mode(self):
        """Test grouping with numbered custom mode."""
        # Create test files with prefixes 0 and 1
        (self.source_path / "0-S01E01.mkv").touch()
        (self.source_path / "1-S02E01.mkv").touch()

        custom_names = [" - First", " - Second"]
        groups = self.grouper.preview_groups("", "", True, custom_names, True)

        self.assertEqual(len(groups), 2)
        self.assertIn("00 - First", groups)
        self.assertIn("01 - Second", groups)

    def test_preview_groups_case_insensitive(self):
        """Test case-insensitive prefix grouping."""
        # Create test files
        (self.source_path / "ABC-file1.txt").touch()
        (self.source_path / "abc-file2.txt").touch()

        groups = self.grouper.preview_groups("", " files", False, [], False)

        # With case insensitive, they should be in the same group
        self.assertEqual(len(groups), 1)

    def test_preview_groups_case_sensitive(self):
        """Test case-sensitive prefix grouping."""
        # Create test files
        (self.source_path / "ABC-file1.txt").touch()
        (self.source_path / "abc-file2.txt").touch()

        groups = self.grouper.preview_groups("", " files", False, [], True)

        # With case sensitive, they should be in different groups
        self.assertEqual(len(groups), 2)

    def test_preview_groups_no_files(self):
        """Test preview with no matching files."""
        # Create a file without dash in name (no valid prefix)
        (self.source_path / "nopre.txt").touch()

        groups = self.grouper.preview_groups("", " files", False, [], True)
        self.assertEqual(len(groups), 0)


class TestFileGrouperEdgeCases(unittest.TestCase):
    """Edge case tests for FileGrouper."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.source_path = Path(self.temp_dir)
        self.grouper = FileGrouper(self.source_path)

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_prefix_with_only_numbers(self):
        """Test files with only numeric prefix."""
        (self.source_path / "123-file.txt").touch()

        groups = self.grouper.preview_groups("", " files", False, [], True)
        self.assertEqual(len(groups), 1)
        self.assertIn("123 files", groups)

    def test_prefix_with_special_chars(self):
        """Test files with special characters in prefix."""
        (self.source_path / "S01-E01.mp4").touch()

        groups = self.grouper.preview_groups("", " video", False, [], True)
        self.assertEqual(len(groups), 1)

    def test_empty_prefix_excluded(self):
        """Test that files with empty prefix are excluded."""
        (self.source_path / "-file1.txt").touch()
        (self.source_path / "prefix-file2.txt").touch()

        groups = self.grouper.preview_groups("", " files", False, [], True)
        self.assertEqual(len(groups), 1)

    def test_many_files_per_group(self):
        """Test grouping many files per prefix."""
        for i in range(10):
            (self.source_path / f"01-file{i}.txt").touch()

        groups = self.grouper.preview_groups("", " files", False, [], True)
        self.assertEqual(len(groups["01 files"]), 10)


class TestSortModes(unittest.TestCase):
    """Tests for the sort_mode parameter of preview_groups."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.source_path = Path(self.temp_dir)
        self.grouper = FileGrouper(self.source_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _make(self, name, size=0, mtime=None):
        p = self.source_path / name
        p.touch()
        if size:
            with open(p, "wb") as f:
                f.seek(size - 1)
                f.write(b"\0")
        if mtime is not None:
            os.utime(p, (mtime, mtime))
        return p

    def test_default_name_sort(self):
        """Default sort is alphabetical by prefix."""
        self._make("banana-x.txt")
        self._make("apple-x.txt")
        groups = self.grouper.preview_groups("", " g", False, [], True, "name")
        self.assertEqual(list(groups.keys()), ["apple g", "banana g"])

    def test_natural_sort(self):
        """Natural sort orders 2 before 10."""
        for i in [1, 2, 10]:
            self._make(f"{i}-file.txt")
        groups = self.grouper.preview_groups("", " g", False, [], True, "natural")
        self.assertEqual(list(groups.keys()), ["1 g", "2 g", "10 g"])

    def test_mtime_newest_first(self):
        self._make("old-x.txt", mtime=1000)
        self._make("new-x.txt", mtime=9999)
        groups = self.grouper.preview_groups("", " g", False, [], True, "mtime_newest")
        self.assertEqual(list(groups.keys())[0], "new g")

    def test_mtime_oldest_first(self):
        self._make("old-x.txt", mtime=1000)
        self._make("new-x.txt", mtime=9999)
        groups = self.grouper.preview_groups("", " g", False, [], True, "mtime_oldest")
        self.assertEqual(list(groups.keys())[0], "old g")

    def test_size_largest_first(self):
        self._make("big-x.txt", size=5000)
        self._make("small-x.txt", size=100)
        groups = self.grouper.preview_groups("", " g", False, [], True, "size_largest")
        self.assertEqual(list(groups.keys())[0], "big g")

    def test_size_smallest_first(self):
        self._make("big-x.txt", size=5000)
        self._make("small-x.txt", size=100)
        groups = self.grouper.preview_groups("", " g", False, [], True, "size_smallest")
        self.assertEqual(list(groups.keys())[0], "small g")


class TestExecuteAndUndo(unittest.TestCase):
    """Integration tests for execute_move and undo_last_move."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.source_path = Path(self.temp_dir)
        self.grouper = FileGrouper(self.source_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_execute_move_basic(self):
        """Files are moved into prefix-named folders."""
        (self.source_path / "01-a.mkv").touch()
        (self.source_path / "01-b.mkv").touch()
        (self.source_path / "02-c.mkv").touch()

        moved, skipped, renamed, errors = self.grouper.execute_move(
            "", " eps", False, [], True, "Skip")

        self.assertEqual(moved, 3)
        self.assertEqual(skipped, 0)
        self.assertTrue((self.source_path / "01 eps" / "01-a.mkv").exists())
        self.assertTrue((self.source_path / "02 eps" / "02-c.mkv").exists())

    def test_execute_move_conflict_skip(self):
        """Skip policy leaves the existing destination intact."""
        (self.source_path / "01-a.mkv").touch()
        target_folder = self.source_path / "01 eps"
        target_folder.mkdir()
        (target_folder / "01-a.mkv").write_text("existing")

        moved, skipped, renamed, errors = self.grouper.execute_move(
            "", " eps", False, [], True, "Skip")

        self.assertEqual(moved, 0)
        self.assertEqual(skipped, 1)
        self.assertEqual((target_folder / "01-a.mkv").read_text(), "existing")

    def test_execute_move_conflict_auto_rename(self):
        """Auto-Rename creates a uniquely named copy instead of overwriting."""
        (self.source_path / "01-a.mkv").touch()
        target_folder = self.source_path / "01 eps"
        target_folder.mkdir()
        (target_folder / "01-a.mkv").write_text("existing")

        moved, skipped, renamed, errors = self.grouper.execute_move(
            "", " eps", False, [], True, "Auto-Rename")

        self.assertEqual(moved, 1)
        self.assertEqual(renamed, 1)
        self.assertTrue((target_folder / "01-a.mkv").exists())
        self.assertTrue((target_folder / "01-a (1).mkv").exists())

    def test_undo_last_move_restores_files(self):
        """Undo moves files back and cleans up empty group folders."""
        (self.source_path / "01-a.mkv").touch()
        self.grouper.execute_move("", " eps", False, [], True, "Skip")
        self.assertTrue((self.source_path / "01 eps" / "01-a.mkv").exists())

        undone, remaining = self.grouper.undo_last_move()
        self.assertEqual(undone, 1)
        self.assertEqual(remaining, 0)
        self.assertTrue((self.source_path / "01-a.mkv").exists())
        self.assertFalse((self.source_path / "01 eps").exists())

    def test_undo_with_no_log(self):
        """Undo is a no-op when there is no move log."""
        undone, remaining = self.grouper.undo_last_move()
        self.assertEqual((undone, remaining), (0, 0))


if __name__ == '__main__':
    unittest.main()
