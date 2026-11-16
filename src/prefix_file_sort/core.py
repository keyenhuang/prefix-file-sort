"""Core business logic for prefix-file-sort.

This module is intentionally free of any GUI (tkinter) dependencies so that the
file-grouping logic can be unit-tested and executed in headless environments
such as CI runners without a display server.

The :class:`FileGrouper` class encapsulates prefix detection, grouping,
conflict-aware moving, and undo functionality.
"""
import errno
import json
import os
import re
import shutil
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple


_INVALID_FOLDER_CHARS_RE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
_WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

_DEFAULT_MESSAGES: Dict[str, str] = {
    "warn_source_missing": "Source file missing (skipped): {name}",
    "warn_skipped": "Skipped (Conflict): {name}",
    "warn_overwrite": "Overwriting: {name}",
    "warn_file_missing": "File missing for undo: {name}",
    "warn_undo_conflict": "Skipped undo (destination already exists): {name}",
    "warn_cleanup_failed": "Cleanup failed for {name}: {error}",
    "warn_cleaned_folder": "Cleaned up empty folder: {name}",
    "error_create_folder": "Failed to create folder {name}: {error}",
    "error_overwrite": "Failed to overwrite {name}: {error}",
    "error_move": "Move error for {name}: {error}",
    "error_dst_is_dir": "Destination is an existing folder (skipped): {name}",
    "error_rollback": "CRITICAL: Log save failed and rollback failed for {name}: {error1} / {error2}",
    "error_undo": "Undo error for {name}: {error}",
    "error_log_save": "Failed to update log after undo: {error}",
    "error_log_save_move": "Move rolled back due to log save failure for {name}: {error}",
    "info_auto_renamed": "Auto-Renamed to: {name}",
}


def _default_translate(key: str, **kwargs) -> str:
    template = _DEFAULT_MESSAGES.get(key, key)
    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, ValueError):
            return template
    return template


class FileGrouper:
    """Core business logic for file grouping."""

    LOG_FILENAME = "move_log.json"

    def __init__(self, source_path: Path):
        self.source_path = source_path
        self.log_path = source_path / self.LOG_FILENAME

    @staticmethod
    def get_allowed_extensions(filter_text: str) -> Optional[List[str]]:
        exts = [ext.strip().lower() for ext in filter_text.split(",") if ext.strip()]
        cleaned = []
        for e in exts:
            if not e.startswith("."):
                e = "." + e
            cleaned.append(e)
        return cleaned if cleaned else None

    @staticmethod
    def sanitize_folder_name(name: str) -> str:
        """Sanitize a folder name so it cannot escape source_path or fail OS rules."""
        cleaned = _INVALID_FOLDER_CHARS_RE.sub("_", name).strip().rstrip(".")
        if cleaned in ("", ".", ".."):
            return "_group"
        stem = cleaned.split(".", 1)[0].upper()
        if stem in _WINDOWS_RESERVED_NAMES:
            cleaned = f"_{cleaned}"
        return cleaned

    def get_filtered_files(self, filter_text: str, delimiter: str = "-") -> List[Path]:
        allowed = self.get_allowed_extensions(filter_text)
        sep = delimiter if delimiter else "-"
        files: List[Path] = []
        try:
            for item in self.source_path.iterdir():
                if (
                    item.is_file()
                    and item.name != self.LOG_FILENAME
                    and not item.name.startswith(f".{self.LOG_FILENAME}")
                    and sep in item.name
                ):
                    if allowed is None or item.suffix.lower() in allowed:
                        files.append(item)
        except OSError:
            return []
        files.sort(key=lambda p: p.name.lower())
        return files

    @staticmethod
    def _natural_key(value: str) -> List:
        """Sort key that orders embedded numbers numerically (natural sort)."""
        return [
            int(part) if part.isdigit() else part.lower()
            for part in re.split(r"(\d+)", value)
        ]

    @staticmethod
    def _safe_stat(path: Path) -> Optional[os.stat_result]:
        try:
            return path.stat()
        except OSError:
            return None

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
                mtimes = [
                    st.st_mtime
                    for f in temp_groups[k]["files"]
                    for st in (self._safe_stat(f),)
                    if st is not None
                ]
                return max(mtimes) if mtimes else 0.0

            return sorted(keys, key=mtime_key, reverse=(sort_mode == "mtime_newest"))
        if sort_mode in ("size_largest", "size_smallest"):
            def size_key(k: str) -> int:
                return sum(
                    st.st_size
                    for f in temp_groups[k]["files"]
                    for st in (self._safe_stat(f),)
                    if st is not None
                )

            return sorted(keys, key=size_key, reverse=(sort_mode == "size_largest"))
        return sorted(keys)

    def preview_groups(
        self,
        filter_text: str,
        suffix: str,
        use_numbering: bool,
        custom_names: List[str],
        case_sensitive: bool,
        sort_mode: str = "name",
        delimiter: str = "-",
    ) -> Dict[str, List[Path]]:
        sep = delimiter if delimiter else "-"
        files = self.get_filtered_files(filter_text, delimiter=sep)
        temp_groups: Dict[str, Dict] = {}

        for item in files:
            prefix = item.name.split(sep, 1)[0].strip()
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

            folder_name = self.sanitize_folder_name(folder_name)

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

    def _move_with_overwrite(self, src_path: Path, dst_path: Path) -> None:
        """Atomically overwrite ``dst_path`` with ``src_path`` when possible."""
        try:
            os.replace(str(src_path), str(dst_path))
        except OSError as exc:
            if exc.errno != errno.EXDEV:
                raise
            # Cross-device fallback: back up destination before moving
            backup_path = dst_path.with_name(f".{dst_path.name}.{uuid.uuid4().hex[:6]}.bak")
            shutil.move(str(dst_path), str(backup_path))
            try:
                shutil.move(str(src_path), str(dst_path))
            except Exception:
                try:
                    shutil.move(str(backup_path), str(dst_path))
                except Exception:
                    pass
                raise
            try:
                backup_path.unlink(missing_ok=True)
            except OSError:
                pass

    def _flush_log_batch(
        self,
        existing_log: List[dict],
        pending_batch: List[Tuple[dict, Path, Path, bool]],
        translate_func: Callable[..., str],
        log_callback,
    ) -> Tuple[int, int, int]:
        """Persist ``existing_log`` and roll back ``pending_batch`` if saving fails.

        Returns ``(committed_moved, committed_renamed, error_count)``.
        """
        if not pending_batch:
            return 0, 0, 0

        try:
            self._save_log(existing_log)
            moved = len(pending_batch)
            renamed = sum(1 for _, _, _, was_renamed in pending_batch if was_renamed)
            pending_batch.clear()
            return moved, renamed, 0
        except Exception as e:
            errors = 0
            for entry, original_path, dst_path, _ in reversed(pending_batch):
                existing_log.pop()
                try:
                    shutil.move(str(dst_path), str(original_path))
                    errors += 1
                    if log_callback:
                        log_callback(
                            translate_func("error_log_save_move", name=dst_path.name, error=e),
                            "ERROR",
                        )
                except Exception as e2:
                    errors += 1
                    if log_callback:
                        log_callback(
                            translate_func("error_rollback", name=dst_path.name, error1=e, error2=e2),
                            "ERROR",
                        )
            pending_batch.clear()
            return 0, 0, errors

    def execute_move(
        self,
        filter_text: str,
        suffix: str,
        use_numbering: bool,
        custom_names: List[str],
        case_sensitive: bool,
        conflict_policy: str,
        sort_mode: str = "name",
        progress_callback=None,
        log_callback=None,
        delimiter: str = "-",
        translate_func: Optional[Callable[..., str]] = None,
        log_flush_interval: int = 25,
    ) -> Tuple[int, int, int, int]:
        t = translate_func or _default_translate
        flush_interval = max(1, log_flush_interval)

        groups = self.preview_groups(
            filter_text,
            suffix,
            use_numbering,
            custom_names,
            case_sensitive,
            sort_mode,
            delimiter=delimiter,
        )
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
        pending_batch: List[Tuple[dict, Path, Path, bool]] = []

        for folder_name, file_list in groups.items():
            target_folder = self.source_path / folder_name
            try:
                target_folder.mkdir(exist_ok=True)
            except Exception as e:
                if log_callback:
                    log_callback(t("error_create_folder", name=target_folder, error=e), "ERROR")
                error_count += len(file_list)
                current += len(file_list)
                if progress_callback:
                    progress_callback(current, total, folder_name)
                continue

            for file_path in file_list:
                current += 1
                if progress_callback:
                    progress_callback(current, total, file_path.name)

                if not file_path.exists():
                    if log_callback:
                        log_callback(t("warn_source_missing", name=file_path.name), "WARN")
                    skipped_count += 1
                    continue

                dst_path = target_folder / file_path.name
                was_renamed = False
                overwrote = False

                if dst_path.exists():
                    if dst_path.is_dir():
                        error_count += 1
                        if log_callback:
                            log_callback(t("error_dst_is_dir", name=dst_path.name), "ERROR")
                        continue
                    if conflict_policy == "Skip":
                        skipped_count += 1
                        if log_callback:
                            log_callback(t("warn_skipped", name=file_path.name), "WARN")
                        continue
                    elif conflict_policy == "Overwrite":
                        overwrote = True
                        if log_callback:
                            log_callback(t("warn_overwrite", name=file_path.name), "WARN")
                    elif conflict_policy == "Auto-Rename":
                        dst_path = self._get_unique_path(target_folder, file_path.name)
                        was_renamed = True
                        if log_callback:
                            log_callback(t("info_auto_renamed", name=dst_path.name), "INFO")

                original_resolved = file_path.resolve()
                dst_resolved = dst_path.resolve()

                try:
                    if overwrote:
                        self._move_with_overwrite(file_path, dst_path)
                    else:
                        shutil.move(str(file_path), str(dst_path))
                except Exception as e:
                    error_count += 1
                    err_key = "error_overwrite" if overwrote else "error_move"
                    if log_callback:
                        log_callback(t(err_key, name=file_path.name, error=e), "ERROR")
                    continue

                entry = {
                    "batch_id": batch_id,
                    "original": str(original_resolved),
                    "moved_to": str(dst_resolved),
                    "group": folder_name,
                    "extension": file_path.suffix.lower(),
                    "timestamp": datetime.now().isoformat(),
                }
                existing_log.append(entry)
                pending_batch.append((entry, original_resolved, dst_resolved, was_renamed))

                if len(pending_batch) >= flush_interval:
                    m, r, err = self._flush_log_batch(existing_log, pending_batch, t, log_callback)
                    moved_count += m
                    renamed_count += r
                    error_count += err

        if pending_batch:
            m, r, err = self._flush_log_batch(existing_log, pending_batch, t, log_callback)
            moved_count += m
            renamed_count += r
            error_count += err

        return moved_count, skipped_count, renamed_count, error_count

    def _is_inside_source(self, folder: Path) -> bool:
        """Return True if ``folder`` is a strict descendant of ``self.source_path``."""
        try:
            src_resolved = str(self.source_path.resolve())
            fld_resolved = str(folder.resolve())
            return fld_resolved != src_resolved and os.path.commonpath([src_resolved, fld_resolved]) == src_resolved
        except (OSError, ValueError):
            return False

    def undo_last_move(
        self,
        progress_callback=None,
        log_callback=None,
        translate_func: Optional[Callable[..., str]] = None,
    ) -> Tuple[int, int]:
        t = translate_func or _default_translate

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
        failed_undo: List[dict] = []

        for i, item in enumerate(reversed(to_undo)):
            if progress_callback:
                progress_callback(i + 1, total, Path(item["moved_to"]).name)

            dst = Path(item["moved_to"])
            original = Path(item["original"])

            if dst.exists():
                if original.exists():
                    if log_callback:
                        log_callback(t("warn_undo_conflict", name=original.name), "WARN")
                    failed_undo.append(item)
                    continue
                try:
                    original.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(dst), str(original))
                    undone_count += 1
                    if self._is_inside_source(dst.parent):
                        folders_to_cleanup.add(dst.parent)
                except Exception as e:
                    if log_callback:
                        log_callback(t("error_undo", name=dst.name, error=e), "ERROR")
                    failed_undo.append(item)
            else:
                if log_callback:
                    log_callback(t("warn_file_missing", name=dst.name), "WARN")
                if self._is_inside_source(dst.parent):
                    folders_to_cleanup.add(dst.parent)

        if failed_undo:
            to_keep.extend(reversed(failed_undo))

        try:
            self._save_log(to_keep)
        except Exception as e:
            if log_callback:
                log_callback(t("error_log_save", error=e), "ERROR")

        self._cleanup_all_empty_group_folders(folders_to_cleanup, log_callback, t)

        return undone_count, len(to_keep)

    def _cleanup_all_empty_group_folders(
        self,
        known_folders: Set[Path],
        log_callback,
        translate_func: Optional[Callable[..., str]] = None,
    ):
        t = translate_func or _default_translate
        ignored_files = {".ds_store", "thumbs.db", "desktop.ini"}

        for folder in known_folders:
            if not folder.is_dir() or not self._is_inside_source(folder):
                continue

            try:
                is_conceptually_empty = True

                for item in folder.iterdir():
                    if item.is_dir():
                        is_conceptually_empty = False
                        break
                    if (
                        item.name.lower() not in ignored_files
                        and not item.name.startswith("~$")
                        and not item.name.startswith("._")
                    ):
                        is_conceptually_empty = False
                        break

                if is_conceptually_empty:
                    for _ in range(3):
                        shutil.rmtree(folder, ignore_errors=True)
                        if not folder.exists():
                            if log_callback:
                                log_callback(t("warn_cleaned_folder", name=folder.name), "INFO")
                            break
                        time.sleep(0.1)
            except Exception as e:
                if log_callback:
                    log_callback(t("warn_cleanup_failed", name=folder.name, error=e), "WARN")

    def _load_log(self) -> List[dict]:
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return []

    def _save_log(self, data: List[dict]) -> None:
        if data:
            tmp_path = self.source_path / f".{self.LOG_FILENAME}.{uuid.uuid4().hex[:6]}.tmp"
            try:
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(str(tmp_path), str(self.log_path))
            except Exception:
                try:
                    tmp_path.unlink(missing_ok=True)
                except OSError:
                    pass
                raise
        elif self.log_path.exists():
            self.log_path.unlink(missing_ok=True)
