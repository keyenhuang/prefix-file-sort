"""Core business logic for prefix-file-sort.

This module is intentionally free of any GUI (tkinter) dependencies so that the
file-grouping logic can be unit-tested and executed in headless environments
such as CI runners without a display server.

The :class:`FileGrouper` class encapsulates prefix detection, grouping,
conflict-aware moving, and undo functionality.
"""
import os
import re
import time
import json
import uuid
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple


class FileGrouper:
    """Core business logic for file grouping."""

    def __init__(self, source_path: Path):
        self.source_path = source_path
        self.log_path = source_path / "move_log.json"

    @staticmethod
    def get_allowed_extensions(filter_text: str) -> Optional[List[str]]:
        exts = [ext.strip().lower() for ext in filter_text.split(',') if ext.strip()]
        cleaned = []
        for e in exts:
            if not e.startswith('.'):
                e = '.' + e
            cleaned.append(e)
        return cleaned if cleaned else None

    def get_filtered_files(self, filter_text: str) -> List[Path]:
        allowed = self.get_allowed_extensions(filter_text)
        files = []
        try:
            for item in self.source_path.iterdir():
                if (item.is_file() and
                        item.name != "move_log.json" and
                        '-' in item.name):
                    if allowed is None or item.suffix.lower() in allowed:
                        files.append(item)
        except Exception:
            return []
        return files

    @staticmethod
    def _natural_key(value: str) -> List:
        """Sort key that orders embedded numbers numerically (natural sort)."""
        return [int(part) if part.isdigit() else part.lower()
                for part in re.split(r"(\d+)", value)]

    def _sort_group_keys(self, temp_groups: Dict[str, Dict], sort_mode: str) -> List[str]:
        """Return group keys ordered according to ``sort_mode``.

        Modes:
          - ``name``           : plain alphabetical (default, backward compatible)
          - ``natural``        : natural sort (``2`` before ``10``)
          - ``mtime_newest``   : group with the newest file first
          - ``mtime_oldest``   : group with the oldest file first
          - ``size_largest``   : group with the largest total size first
          - ``size_smallest``  : group with the smallest total size first
        """
        keys = list(temp_groups.keys())
        if sort_mode == "natural":
            return sorted(keys, key=self._natural_key)
        if sort_mode in ("mtime_newest", "mtime_oldest"):
            def mtime_key(k: str) -> float:
                try:
                    return max((f.stat().st_mtime for f in temp_groups[k]["files"]
                                if f.exists()), default=0.0)
                except OSError:
                    return 0.0
            return sorted(keys, key=mtime_key, reverse=(sort_mode == "mtime_newest"))
        if sort_mode in ("size_largest", "size_smallest"):
            def size_key(k: str) -> int:
                try:
                    return sum(f.stat().st_size for f in temp_groups[k]["files"]
                               if f.exists())
                except OSError:
                    return 0
            return sorted(keys, key=size_key, reverse=(sort_mode == "size_largest"))
        return sorted(keys)

    def preview_groups(self, filter_text: str, suffix: str, use_numbering: bool,
                       custom_names: List[str], case_sensitive: bool,
                       sort_mode: str = "name") -> Dict[str, List[Path]]:
        files = self.get_filtered_files(filter_text)
        temp_groups: Dict[str, Dict] = {}

        for item in files:
            prefix = item.name.split('-', 1)[0].strip()
            if not prefix:
                continue
            group_key = prefix if case_sensitive else prefix.lower()
            if group_key not in temp_groups:
                temp_groups[group_key] = {"display_prefix": prefix, "files": []}
            temp_groups[group_key]["files"].append(item)

        sorted_keys = self._sort_group_keys(temp_groups, sort_mode)
        final_groups: Dict[str, List[Path]] = {}

        for i, key in enumerate(sorted_keys):
            display_prefix = temp_groups[key]["display_prefix"]

            if use_numbering:
                try:
                    target_idx = int(display_prefix)
                    if target_idx < 0 or target_idx > 9999:
                        target_idx = i
                except (ValueError, OverflowError):
                    target_idx = i

                if custom_names and 0 <= target_idx < len(custom_names):
                    folder_name = f"{target_idx:02d}{custom_names[target_idx]}"
                else:
                    folder_name = f"{target_idx:02d} - {display_prefix}{suffix}"
            else:
                folder_name = f"{display_prefix}{suffix}"

            base_folder_name = folder_name
            counter = 1
            while folder_name in final_groups:
                folder_name = f"{base_folder_name}_{counter}"
                counter += 1

            final_groups[folder_name] = temp_groups[key]["files"]

        return final_groups
    def _get_unique_path(self, target_folder: Path, original_name: str) -> Path:
        base, ext = os.path.splitext(original_name)
        counter = 1
        new_path = target_folder / original_name
        while new_path.exists():
            new_path = target_folder / f"{base} ({counter}){ext}"
            counter += 1
        return new_path

    def execute_move(self, filter_text: str, suffix: str, use_numbering: bool,
                     custom_names: List[str], case_sensitive: bool,
                     conflict_policy: str, sort_mode: str = "name",
                     progress_callback=None, log_callback=None) -> Tuple[int, int, int, int]:

        groups = self.preview_groups(filter_text, suffix, use_numbering, custom_names,
                                     case_sensitive, sort_mode)
        if not groups:
            return 0, 0, 0, 0

        existing_log = self._load_log()
        batch_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        moved_count = 0
        skipped_count = 0
        renamed_count = 0
        error_count = 0
        total = sum(len(files) for files in groups.values())
        current = 0

        for folder_name, file_list in groups.items():
            target_folder = self.source_path / folder_name
            try:
                target_folder.mkdir(exist_ok=True)
            except Exception as e:
                if log_callback:
                    log_callback(f"Failed to create folder {target_folder}: {e}", "ERROR")
                error_count += len(file_list)
                continue

            for file_path in file_list:
                if not file_path.exists():
                    if log_callback:
                        log_callback(f"Source file missing (skipped): {file_path.name}", "WARN")
                    skipped_count += 1
                    continue

                current += 1
                if progress_callback:
                    progress_callback(current, total, file_path.name)
                dst_path = target_folder / file_path.name

                if dst_path.exists():
                    if conflict_policy == "Skip":
                        skipped_count += 1
                        if log_callback:
                            log_callback(f"Skipped (Conflict): {file_path.name}", "WARN")
                        continue
                    elif conflict_policy == "Overwrite":
                        try:
                            os.remove(dst_path)
                            if log_callback:
                                log_callback(f"Overwriting: {file_path.name}", "WARN")
                        except OSError as e:
                            error_count += 1
                            if log_callback:
                                log_callback(f"Failed to overwrite {dst_path.name}: {e}", "ERROR")
                            continue
                    elif conflict_policy == "Auto-Rename":
                        dst_path = self._get_unique_path(target_folder, file_path.name)
                        renamed_count += 1
                        if log_callback:
                            log_callback(f"Auto-Renamed to: {dst_path.name}", "INFO")

                try:
                    shutil.move(str(file_path), str(dst_path))
                except Exception as e:
                    error_count += 1
                    if log_callback:
                        log_callback(f"Move error for {file_path.name}: {e}", "ERROR")
                    continue

                entry = {
                    "batch_id": batch_id,
                    "original": str(file_path.resolve()),
                    "moved_to": str(dst_path.resolve()),
                    "group": folder_name,
                    "extension": file_path.suffix.lower(),
                    "timestamp": datetime.now().isoformat()
                }

                existing_log.append(entry)

                try:
                    self._save_log(existing_log)
                    moved_count += 1
                except Exception as e:
                    try:
                        shutil.move(str(dst_path), str(Path(entry["original"])))
                        error_count += 1
                        existing_log.pop()
                        if log_callback:
                            log_callback(
                                f"Move rolled back due to log save failure for {dst_path.name}: {e}",
                                "ERROR")
                    except Exception as e2:
                        if log_callback:
                            log_callback(
                                f"CRITICAL: Log save failed and rollback failed for "
                                f"{dst_path.name}: {e} / {e2}", "ERROR")

        return moved_count, skipped_count, renamed_count, error_count
    def undo_last_move(self, progress_callback=None, log_callback=None) -> Tuple[int, int]:
        if not self.log_path.exists():
            return 0, 0

        log_data = self._load_log()
        if not log_data:
            return 0, 0

        last_batch_id = log_data[-1].get("batch_id")
        to_undo = []
        to_keep = []

        for item in log_data:
            if last_batch_id is None or item.get("batch_id") == last_batch_id:
                to_undo.append(item)
            else:
                to_keep.append(item)

        undone_count = 0
        total = len(to_undo)
        folders_to_cleanup: Set[Path] = set()

        for i, item in enumerate(reversed(to_undo)):
            if progress_callback:
                progress_callback(i + 1, total, Path(item["moved_to"]).name)

            dst = Path(item["moved_to"])
            original = Path(item["original"])

            if dst.exists():
                try:
                    original.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(dst), str(original))
                    undone_count += 1
                    folders_to_cleanup.add(dst.parent)
                except Exception as e:
                    if log_callback:
                        log_callback(f"Undo error for {dst.name}: {e}", "ERROR")
                    to_keep.append(item)
            else:
                if log_callback:
                    log_callback(f"File missing for undo: {dst.name}", "WARN")

        try:
            self._save_log(to_keep)
        except Exception as e:
            if log_callback:
                log_callback(f"Failed to update log after undo: {e}", "ERROR")

        self._cleanup_all_empty_group_folders(folders_to_cleanup, log_callback)

        return undone_count, len(to_keep)

    def _cleanup_all_empty_group_folders(self, known_folders: Set[Path], log_callback):
        candidates: Set[Path] = set()
        if known_folders:
            candidates.update(known_folders)

        try:
            for folder in self.source_path.iterdir():
                if not folder.is_dir():
                    continue
                name = folder.name
                if len(name) >= 2 and name[0].isdigit() and name[1].isdigit():
                    candidates.add(folder)
        except Exception:
            pass

        ignored_files = {'.ds_store', 'thumbs.db', 'desktop.ini'}

        for folder in candidates:
            if not folder.is_dir():
                continue

            try:
                is_conceptually_empty = True

                for item in folder.iterdir():
                    if item.is_dir():
                        is_conceptually_empty = False
                        break
                    if (item.name.lower() not in ignored_files
                            and not item.name.startswith('~$')
                            and not item.name.startswith('._')):
                        is_conceptually_empty = False
                        break

                if is_conceptually_empty:
                    for _ in range(3):
                        shutil.rmtree(folder, ignore_errors=True)
                        if not folder.exists():
                            if log_callback:
                                log_callback(f"Cleaned up empty folder: {folder.name}", "INFO")
                            break
                        time.sleep(0.1)
            except Exception as e:
                if log_callback:
                    log_callback(f"Cleanup failed for {folder.name}: {e}", "WARN")

    def _load_log(self) -> List[dict]:
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return []

    def _save_log(self, data: List[dict]):
        try:
            if data:
                with open(self.log_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
            elif self.log_path.exists():
                self.log_path.unlink(missing_ok=True)
        except Exception:
            raise


