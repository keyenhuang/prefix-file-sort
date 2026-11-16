"""Internationalization module for prefix-file-sort."""

import os
import json
from pathlib import Path
from typing import Dict, Callable

# Translation dictionaries
TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "en": {
        # App
        "app_title": "File Grouper",

        # Source folder
        "source_folder": "Source Folder:",
        "browse": "Browse...",
        "drag_drop_hint": "Drag & drop a folder here",

        # Options
        "default_suffix": "Default Suffix:",
        "delimiter": "Delimiter:",
        "delimiter_hint": "-",
        "file_filter": "File Filter (e.g. .jpg, .xlsx):",
        "file_filter_hint": "Leave empty to process all files",

        # Settings
        "robustness_settings": "Robustness Settings",
        "conflict_policy": "Conflict Policy:",
        "conflict_skip": "Skip",
        "conflict_overwrite": "Overwrite",
        "conflict_auto_rename": "Auto-Rename",
        "case_sensitive": "Prefix Case Sensitive",
        "sort_by": "Sort by:",
        "sort_name": "Name (A-Z)",
        "sort_natural": "Natural order",
        "sort_mtime_newest": "Newest first",
        "sort_mtime_oldest": "Oldest first",
        "sort_size_largest": "Largest first",
        "sort_size_smallest": "Smallest first",

        # Numbered mode
        "enable_numbered_mode": "Enable Numbered Custom Mode",
        "custom_folder_names": "Custom Folder Names (one per line):",
        "custom_folder_hint": "If prefix is numeric (e.g., '05-'), it uses corresponding row name.",
        "custom_folder_example": "Season 01\nSeason 02\nSeason 03\nSeason 04\nSeason 05",

        # Buttons
        "preview": "Preview Groups",
        "execute": "Execute Move",
        "undo": "Undo Last Move",
        "export_log": "Export Log",
        "settings": "Settings",

        # Settings dialog
        "settings_title": "Settings",
        "language": "Language:",
        "theme": "Theme:",
        "theme_light": "Light",
        "theme_dark": "Dark",
        "theme_system": "System",
        "close": "Close",
        "save": "Save",

        # Activity log
        "activity_log": "Activity Log",
        "clear_log": "Clear",

        # Progress
        "progress_ready": "Progress: Ready",
        "progress": "Progress: {current}/{total} ({percent}%)",
        "progress_file": "Progress: {current}/{total} ({percent}%) - {filename}",

        # Status
        "status_ready": "Ready",
        "status_loaded": "Loaded: {name}",
        "status_move_complete": "Move completed (Moved {moved}, Renamed {renamed})",
        "status_undo_complete": "Undo completed ({count} files restored)",

        # Messages
        "error_select_folder": "Please select a folder first!",
        "error_suffix_required": "Please enter a Default Suffix or enable Numbered Custom Mode!",
        "error_folder_not_exist": "Folder does not exist!",
        "error_load_failed": "Load Failed",

        "info_folder_loaded": "Folder loaded: {name}",
        "info_preview_start": "=== PREVIEW START ===",
        "info_preview_complete": "=== PREVIEW COMPLETE ===",
        "info_move_start": "=== MOVE OPERATION START ===",
        "info_move_complete": "=== MOVE OPERATION COMPLETE ===",
        "info_undo_start": "=== UNDO OPERATION START ===",
        "info_undo_complete": "=== UNDO OPERATION COMPLETE ===",

        "success_found": "Found {groups} groups with {files} files",
        "success_summary": "SUMMARY: Moved {moved} | Auto-Renamed {renamed} | Skipped {skipped} | Errors {errors}",
        "success_undo_summary": "SUMMARY: Restored {count} files | {remaining} records remaining",

        # Target folder
        "target_folder": "Target Folder: {name}  ({count} files)",
        "file_entry": "   └─ {name}",
        "more_files": "   ... and {count} more files",

        # Confirmations
        "confirm_move": "You are about to move {files} files into {groups} folders.\n\nContinue?",
        "confirm_move_title": "Confirm",
        "confirm_undo": "Undo the LAST batch of moves?",
        "confirm_undo_title": "Confirm",

        # Results
        "result_success": "Successfully grouped {count} files.",
        "result_skipped": "Skipped {count} conflicts.",
        "result_errors": "Errors on {count} files (check log).",
        "result_nothing": "Nothing to do",
        "result_nothing_desc": "No files matched the filter/prefix criteria.",
        "result_complete": "Operation Complete",
        "result_undo_success": "Undo Success",
        "result_undo_desc": "Successfully restored {count} files.\nCleaned up residual empty folders.",

        # Warnings
        "warn_source_missing": "Source file missing (skipped): {name}",
        "warn_skipped": "Skipped (Conflict): {name}",
        "warn_overwrite": "Overwriting: {name}",
        "warn_file_missing": "File missing for undo: {name}",
        "warn_undo_conflict": "Skipped undo (destination already exists): {name}",
        "warn_invalid_name": "Invalid Name",
        "warn_invalid_chars": "Folder name '{name}' contains invalid characters",
        "warn_invalid_suffix": "Default suffix contains invalid filename characters",
        "warn_cleanup_failed": "Cleanup failed for {name}: {error}",
        "warn_cleaned_folder": "Cleaned up empty folder: {name}",

        # Errors
        "error_title": "Error",
        "error_create_folder": "Failed to create folder {name}: {error}",
        "error_overwrite": "Failed to overwrite {name}: {error}",
        "error_move": "Move error for {name}: {error}",
        "error_dst_is_dir": "Destination is an existing folder (skipped): {name}",
        "error_rollback": "CRITICAL: Log save failed and rollback failed for {name}: {error1} / {error2}",
        "error_undo": "Undo error for {name}: {error}",
        "error_log_save": "Failed to update log after undo: {error}",
        "error_critical": "Critical error during move: {error}",
        "error_critical_undo": "Critical error during undo: {error}",
        "error_log_save_move": "Move rolled back due to log save failure for {name}: {error}",

        # Dialogs / Export / Browse
        "select_source_folder": "Select Source Folder",
        "no_folder_title": "No Folder",
        "no_folder_export": "Please load a folder before exporting the log.",
        "export_success_title": "Success",
        "export_success_msg": "Audit log exported to:\n{path}",
        "export_failed_title": "Export Failed",
        "invalid_drop_title": "Invalid Drop",
        "invalid_drop_msg": "Please drop a valid folder.",
        "drop_error_title": "Drop Error",
        "drop_error_msg": "Failed to load folder: {error}",

        # Info logs
        "info_auto_renamed": "Auto-Renamed to: {name}",

        # Drag and drop
        "dnd_not_available": "Warning: tkinterdnd2 not available; drag-and-drop disabled. Install with: pip install tkinterdnd2",
    },

    "zh": {
        # App
        "app_title": "文件分组器",

        # Source folder
        "source_folder": "源文件夹：",
        "browse": "浏览...",
        "drag_drop_hint": "拖放文件夹到此处",

        # Options
        "default_suffix": "默认后缀：",
        "delimiter": "分隔符：",
        "delimiter_hint": "-",
        "file_filter": "文件过滤器（例如 .jpg, .xlsx）：",
        "file_filter_hint": "留空处理所有文件",

        # Settings
        "robustness_settings": "稳健性设置",
        "conflict_policy": "冲突策略：",
        "conflict_skip": "跳过",
        "conflict_overwrite": "覆盖",
        "conflict_auto_rename": "自动重命名",
        "case_sensitive": "前缀区分大小写",
        "sort_by": "排序方式：",
        "sort_name": "名称（A-Z）",
        "sort_natural": "自然排序",
        "sort_mtime_newest": "最新优先",
        "sort_mtime_oldest": "最旧优先",
        "sort_size_largest": "最大优先",
        "sort_size_smallest": "最小优先",

        # Numbered mode
        "enable_numbered_mode": "启用编号自定义模式",
        "custom_folder_names": "自定义文件夹名称（每行一个）：",
        "custom_folder_hint": "如果前缀是数字（例如 '05-'），将使用对应行的名称。",
        "custom_folder_example": "第 1 季\n第 2 季\n第 3 季\n第 4 季\n第 5 季",

        # Buttons
        "preview": "预览分组",
        "execute": "执行移动",
        "undo": "撤销上一步",
        "export_log": "导出日志",
        "settings": "设置",

        # Settings dialog
        "settings_title": "设置",
        "language": "语言：",
        "theme": "主题：",
        "theme_light": "浅色",
        "theme_dark": "深色",
        "theme_system": "跟随系统",
        "close": "关闭",
        "save": "保存",

        # Activity log
        "activity_log": "活动日志",
        "clear_log": "清空",

        # Progress
        "progress_ready": "进度：就绪",
        "progress": "进度：{current}/{total} ({percent}%)",
        "progress_file": "进度：{current}/{total} ({percent}%) - {filename}",

        # Status
        "status_ready": "就绪",
        "status_loaded": "已加载：{name}",
        "status_move_complete": "移动完成（已移动 {moved}，已重命名 {renamed}）",
        "status_undo_complete": "撤销完成（已恢复 {count} 个文件）",

        # Messages
        "error_select_folder": "请先选择一个文件夹！",
        "error_suffix_required": "请输入默认后缀或启用编号自定义模式！",
        "error_folder_not_exist": "文件夹不存在！",
        "error_load_failed": "加载失败",

        "info_folder_loaded": "已加载文件夹：{name}",
        "info_preview_start": "=== 预览开始 ===",
        "info_preview_complete": "=== 预览完成 ===",
        "info_move_start": "=== 移动操作开始 ===",
        "info_move_complete": "=== 移动操作完成 ===",
        "info_undo_start": "=== 撤销操作开始 ===",
        "info_undo_complete": "=== 撤销操作完成 ===",

        "success_found": "发现 {groups} 个分组，共 {files} 个文件",
        "success_summary": "摘要：已移动 {moved} | 自动重命名 {renamed} | 已跳过 {skipped} | 错误 {errors}",
        "success_undo_summary": "摘要：已恢复 {count} 个文件 | 剩余 {remaining} 条记录",

        # Target folder
        "target_folder": "目标文件夹：{name}  ({count} 个文件)",
        "file_entry": "   └─ {name}",
        "more_files": "   ... 还有 {count} 个文件",

        # Confirmations
        "confirm_move": "您将移动 {files} 个文件到 {groups} 个文件夹中。\n\n是否继续？",
        "confirm_move_title": "确认",
        "confirm_undo": "撤销上一次的批量移动？",
        "confirm_undo_title": "确认",

        # Results
        "result_success": "成功分组 {count} 个文件。",
        "result_skipped": "已跳过 {count} 个冲突文件。",
        "result_errors": "{count} 个文件出错（请查看日志）。",
        "result_nothing": "无需操作",
        "result_nothing_desc": "没有文件匹配过滤器/前缀条件。",
        "result_complete": "操作完成",
        "result_undo_success": "撤销成功",
        "result_undo_desc": "成功恢复 {count} 个文件。\n已清理残余空文件夹。",

        # Warnings
        "warn_source_missing": "源文件缺失（已跳过）：{name}",
        "warn_skipped": "已跳过（冲突）：{name}",
        "warn_overwrite": "正在覆盖：{name}",
        "warn_file_missing": "撤销时文件缺失：{name}",
        "warn_undo_conflict": "跳过撤销（原路径已存在同名文件）：{name}",
        "warn_invalid_name": "无效名称",
        "warn_invalid_chars": "文件夹名称 '{name}' 包含无效字符",
        "warn_invalid_suffix": "默认后缀包含无效的文件名字符",
        "warn_cleanup_failed": "清理失败 {name}：{error}",
        "warn_cleaned_folder": "已清理空文件夹：{name}",

        # Errors
        "error_title": "错误",
        "error_create_folder": "创建文件夹失败 {name}：{error}",
        "error_overwrite": "覆盖失败 {name}：{error}",
        "error_move": "移动错误 {name}：{error}",
        "error_dst_is_dir": "目标路径是已存在的文件夹（已跳过）：{name}",
        "error_rollback": "严重错误：日志保存失败且回滚失败 {name}：{error1} / {error2}",
        "error_undo": "撤销错误 {name}：{error}",
        "error_log_save": "撤销后更新日志失败：{error}",
        "error_critical": "移动过程中的严重错误：{error}",
        "error_critical_undo": "撤销过程中的严重错误：{error}",
        "error_log_save_move": "因日志保存失败而回滚 {name}：{error}",

        # Dialogs / Export / Browse
        "select_source_folder": "选择源文件夹",
        "no_folder_title": "未选择文件夹",
        "no_folder_export": "导出日志前请先加载文件夹。",
        "export_success_title": "导出成功",
        "export_success_msg": "审计日志已导出至：\n{path}",
        "export_failed_title": "导出失败",
        "invalid_drop_title": "无效拖放",
        "invalid_drop_msg": "请拖放一个有效的文件夹。",
        "drop_error_title": "拖放错误",
        "drop_error_msg": "加载文件夹失败：{error}",

        # Info logs
        "info_auto_renamed": "已自动重命名为：{name}",

        # Drag and drop
        "dnd_not_available": "警告：tkinterdnd2 不可用，拖放功能已禁用。请运行：pip install tkinterdnd2",
    }
}


class I18n:
    """Internationalization handler."""

    def __init__(self, language: str = "en"):
        self._language = language

    @property
    def language(self) -> str:
        return self._language

    @language.setter
    def language(self, value: str):
        if value in TRANSLATIONS:
            self._language = value

    @property
    def available_languages(self) -> Dict[str, str]:
        return {
            "en": "English",
            "zh": "中文"
        }

    def t(self, key: str, **kwargs) -> str:
        """Translate a key with optional keyword arguments."""
        text = TRANSLATIONS.get(self._language, TRANSLATIONS["en"]).get(
            key,
            TRANSLATIONS["en"].get(key, key)
        )
        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, ValueError):
                return text
        return text

    def __call__(self, key: str, **kwargs) -> str:
        """Shorthand for t()."""
        return self.t(key, **kwargs)


# Global instance
_i18n = I18n()


def get_i18n() -> I18n:
    """Get the global i18n instance."""
    return _i18n


def set_language(lang: str) -> None:
    """Set the global language."""
    _i18n.language = lang
