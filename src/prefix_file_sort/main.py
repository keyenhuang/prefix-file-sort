"""Main GUI application for prefix-file-sort built with CustomTkinter."""

import ctypes
import json
import os
import re
import sys
import threading
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any, Dict, List, Optional

import customtkinter as ctk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except Exception:
    HAS_DND = False

from prefix_file_sort.core import FileGrouper
from prefix_file_sort.i18n import I18n, get_i18n, set_language
from prefix_file_sort.themes import DARK_THEME, LIGHT_THEME, ThemeManager, get_theme_manager, set_theme

# Settings storage path (primary: user home directory; fallback: application directory)
APP_SETTINGS_FILE = os.path.join(Path.home(), ".prefix_file_sort_settings.json")
APP_SETTINGS_FILE_LOCAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".app_settings.json")

_INVALID_PATH_CHARS_RE = re.compile(r'[\\/:*?"<>|]')

SORT_MODES = [
    ("name", "sort_name"),
    ("natural", "sort_natural"),
    ("mtime_newest", "sort_mtime_newest"),
    ("mtime_oldest", "sort_mtime_oldest"),
    ("size_largest", "sort_size_largest"),
    ("size_smallest", "sort_size_smallest"),
]

CONFLICT_POLICIES = [
    ("Skip", "conflict_skip"),
    ("Overwrite", "conflict_overwrite"),
    ("Auto-Rename", "conflict_auto_rename"),
]

THEME_OPTIONS = [
    ("light", "theme_light"),
    ("dark", "theme_dark"),
    ("system", "theme_system"),
]


def _monospace_font_family() -> str:
    if sys.platform == "win32":
        return "Consolas"
    if sys.platform == "darwin":
        return "Menlo"
    return "DejaVu Sans Mono"


def load_settings() -> Dict[str, Any]:
    """Load application settings from file."""
    for settings_path in (APP_SETTINGS_FILE, APP_SETTINGS_FILE_LOCAL):
        try:
            if os.path.exists(settings_path):
                with open(settings_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
        except Exception:
            continue
    return {"theme": "dark", "language": "en"}


def save_settings(settings: Dict[str, Any]) -> None:
    """Save application settings to file."""
    for settings_path in (APP_SETTINGS_FILE, APP_SETTINGS_FILE_LOCAL):
        try:
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2)
                return
        except Exception:
            continue


if HAS_DND:
    class CTkWithDnD(ctk.CTk, TkinterDnD.DnDWrapper):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.TkdndVersion = TkinterDnD._require(self)
else:
    class CTkWithDnD(ctk.CTk):
        pass


class SettingsDialog:
    """Settings dialog for theme and language selection with instant UI update."""

    def __init__(self, parent, i18n: I18n, theme_mgr: ThemeManager, app):
        self.i18n = i18n
        self.theme_mgr = theme_mgr
        self.app = app
        self.settings = app.settings

        self.dialog = ctk.CTkToplevel(parent)
        self.dialog.title(i18n("settings_title"))
        self.dialog.geometry("440x300")
        self.dialog.resizable(False, False)

        # Do NOT call self.dialog.grab_set() as modal grabs during live theme/language switching cause event loop deadlocks on Windows.
        self.dialog.after(100, self._safe_focus)

        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.dialog.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.dialog.winfo_height()) // 2
        self.dialog.geometry(f"+{x}+{y}")

        self._create_widgets()

    def _safe_focus(self):
        try:
            if self.dialog.winfo_exists():
                self.dialog.focus_force()
        except Exception:
            pass

    def _theme_display_for_code(self, code: str) -> str:
        for c, key in THEME_OPTIONS:
            if c == code:
                return self.i18n(key)
        return self.i18n("theme_dark")

    def _theme_code_for_display(self, display: str) -> str:
        for code, key in THEME_OPTIONS:
            if self.i18n(key) == display:
                return code
        return "dark"

    def _create_widgets(self):
        i18n = self.i18n

        self.main_frame = ctk.CTkFrame(self.dialog, corner_radius=10)
        self.main_frame.pack(fill="both", expand=True, padx=15, pady=15)

        self.lbl_title = ctk.CTkLabel(
            self.main_frame,
            text=i18n("settings_title"),
            font=ctk.CTkFont(size=18, weight="bold"),
        )
        self.lbl_title.pack(anchor="w", padx=15, pady=(15, 10))

        # Language Selection
        self.lbl_lang = ctk.CTkLabel(self.main_frame, text=i18n("language"), font=ctk.CTkFont(size=13))
        self.lbl_lang.pack(anchor="w", padx=15, pady=(5, 2))

        current_lang = "English" if i18n.language == "en" else "中文"
        self.seg_lang = ctk.CTkSegmentedButton(
            self.main_frame,
            values=["English", "中文"],
            command=self._on_lang_change,
        )
        self.seg_lang.set(current_lang)
        self.seg_lang.pack(fill="x", padx=15, pady=(0, 15))

        # Theme Selection
        self.lbl_theme = ctk.CTkLabel(self.main_frame, text=i18n("theme"), font=ctk.CTkFont(size=13))
        self.lbl_theme.pack(anchor="w", padx=15, pady=(5, 2))

        current_theme_code = self.settings.get("theme", "dark").lower()
        if current_theme_code not in ("light", "dark", "system"):
            current_theme_code = "dark"
        theme_values = [i18n(k) for _, k in THEME_OPTIONS]
        self.seg_theme = ctk.CTkSegmentedButton(
            self.main_frame,
            values=theme_values,
            command=self._on_theme_change,
        )
        self.seg_theme.set(self._theme_display_for_code(current_theme_code))
        self.seg_theme.pack(fill="x", padx=15, pady=(0, 20))

        # Close Button
        self.btn_close = ctk.CTkButton(self.main_frame, text=i18n("close"), command=self.dialog.destroy, width=100)
        self.btn_close.pack(side="bottom", pady=(0, 15))

    def _on_lang_change(self, value: str):
        lang_code = "en" if value == "English" else "zh"
        self.i18n.language = lang_code
        self.settings["language"] = lang_code
        save_settings(self.settings)
        set_language(lang_code)

        # Asynchronously update UI labels to prevent event loop deadlock
        self.dialog.after(10, self._apply_lang_update)

    def _apply_lang_update(self):
        try:
            if self.dialog.winfo_exists():
                self.dialog.title(self.i18n("settings_title"))
                self.lbl_title.configure(text=self.i18n("settings_title"))
                self.lbl_lang.configure(text=self.i18n("language"))
                self.lbl_theme.configure(text=self.i18n("theme"))
                self.btn_close.configure(text=self.i18n("close"))
                current_theme_code = self.settings.get("theme", "dark").lower()
                self.seg_theme.configure(values=[self.i18n(k) for _, k in THEME_OPTIONS])
                self.seg_theme.set(self._theme_display_for_code(current_theme_code))
        except Exception:
            pass
        self.app.update_ui_language()

    def _on_theme_change(self, value: str):
        theme_code = self._theme_code_for_display(value)
        self.settings["theme"] = theme_code
        save_settings(self.settings)
        set_theme(theme_code)
        # Asynchronously schedule theme switch on next event loop tick
        self.dialog.after(10, lambda: self.app.apply_appearance_mode(theme_code))


class FileGrouperApp:
    """Main application GUI using CustomTkinter."""

    def __init__(self, master: CTkWithDnD):
        self.master = master
        self.settings = load_settings()
        self.i18n = get_i18n()
        self.theme_mgr = get_theme_manager()
        self._settings_dlg: Optional[SettingsDialog] = None

        lang = self.settings.get("language", "en")
        if lang not in ("en", "zh"):
            lang = "en"
        self.i18n.language = lang
        self._last_example_text = self.i18n("custom_folder_example")

        initial_theme = self.settings.get("theme", "dark")
        if initial_theme not in ("light", "dark", "system"):
            initial_theme = "dark"
        ctk.set_appearance_mode(initial_theme)
        set_theme(initial_theme if initial_theme in ("light", "dark") else "dark")

        self.source_path: Optional[Path] = None
        self.grouper: Optional[FileGrouper] = None

        self._conflict_policy_code = self.settings.get("conflict_policy", "Skip")
        if self._conflict_policy_code not in ("Skip", "Overwrite", "Auto-Rename"):
            self._conflict_policy_code = "Skip"

        self._sort_mode_code = self.settings.get("sort_mode", "name")
        if self._sort_mode_code not in {c for c, _ in SORT_MODES}:
            self._sort_mode_code = "name"

        self._is_busy = False
        self._can_execute = False
        self._status_key = "status_ready"
        self._status_kwargs: Dict[str, Any] = {}
        self._status_color: Optional[str] = None

        self.master.title(self.i18n("app_title"))
        self.master.geometry("980x760")
        self.master.minsize(820, 660)
        self.master.protocol("WM_DELETE_WINDOW", self._on_close)

        self.create_widgets()
        self._restore_saved_inputs()
        self._apply_log_theme()
        self.update_ui_language()
        self._refresh_button_states()

    def create_widgets(self):
        i18n = self.i18n
        mono_font = _monospace_font_family()

        # Main container
        self.container = ctk.CTkFrame(self.master, corner_radius=0, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=20, pady=15)

        # ----------------------------------------------------
        # Header Bar
        # ----------------------------------------------------
        header_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 10))

        title_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_frame.pack(side="left")

        self.lbl_app_title = ctk.CTkLabel(
            title_frame,
            text=i18n("app_title"),
            font=ctk.CTkFont(size=22, weight="bold"),
        )
        self.lbl_app_title.pack(anchor="w")

        # High-contrast Settings button in both Light & Dark modes
        self.btn_settings = ctk.CTkButton(
            header_frame,
            text="⚙ " + i18n("settings"),
            command=self.open_settings,
            width=110,
            fg_color=("#3B82F6", "#1F6AA5"),
            hover_color=("#2563EB", "#144E75"),
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.btn_settings.pack(side="right", anchor="ne")

        # ----------------------------------------------------
        # Source Folder Card
        # ----------------------------------------------------
        card_source = ctk.CTkFrame(self.container, corner_radius=10)
        card_source.pack(fill="x", pady=6)

        self.lbl_source = ctk.CTkLabel(
            card_source,
            text=i18n("source_folder"),
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.lbl_source.pack(anchor="w", padx=15, pady=(10, 4))

        src_input_frame = ctk.CTkFrame(card_source, fg_color="transparent")
        src_input_frame.pack(fill="x", padx=15, pady=(0, 12))

        self.entry_source = ctk.CTkEntry(
            src_input_frame,
            placeholder_text=i18n("drag_drop_hint"),
            font=ctk.CTkFont(size=12),
        )
        self.entry_source.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.entry_source.bind("<Return>", lambda _e: self._load_from_entry())

        self.btn_browse = ctk.CTkButton(
            src_input_frame,
            text=i18n("browse"),
            command=self.browse_folder,
            width=110,
        )
        self.btn_browse.pack(side="right")

        # Drag and Drop binding
        if HAS_DND:
            try:
                self.master.drop_target_register(DND_FILES)
                self.master.dnd_bind("<<Drop>>", self.on_drop)
            except Exception:
                pass

        # ----------------------------------------------------
        # Options & Robustness Card
        # ----------------------------------------------------
        card_options = ctk.CTkFrame(self.container, corner_radius=10)
        card_options.pack(fill="x", pady=6)

        opt_grid = ctk.CTkFrame(card_options, fg_color="transparent")
        opt_grid.pack(fill="x", padx=15, pady=12)
        opt_grid.columnconfigure(0, weight=1)
        opt_grid.columnconfigure(1, weight=1)

        # Left Column: Suffix, Delimiter & Extension Filter
        col_left = ctk.CTkFrame(opt_grid, fg_color="transparent")
        col_left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        suffix_delim_row = ctk.CTkFrame(col_left, fg_color="transparent")
        suffix_delim_row.pack(fill="x", pady=(0, 8))
        suffix_delim_row.columnconfigure(0, weight=1)
        suffix_delim_row.columnconfigure(1, weight=0)

        self.lbl_suffix = ctk.CTkLabel(
            suffix_delim_row,
            text=i18n("default_suffix"),
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.lbl_suffix.grid(row=0, column=0, sticky="w", pady=(0, 2))

        self.lbl_delimiter = ctk.CTkLabel(
            suffix_delim_row,
            text=i18n("delimiter"),
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.lbl_delimiter.grid(row=0, column=1, sticky="w", padx=(10, 0), pady=(0, 2))

        self.entry_suffix = ctk.CTkEntry(suffix_delim_row, font=ctk.CTkFont(size=12))
        self.entry_suffix.insert(0, "series")
        self.entry_suffix.grid(row=1, column=0, sticky="ew")

        self.entry_delimiter = ctk.CTkEntry(
            suffix_delim_row,
            width=75,
            placeholder_text=i18n("delimiter_hint"),
            font=ctk.CTkFont(size=12),
        )
        self.entry_delimiter.insert(0, "-")
        self.entry_delimiter.grid(row=1, column=1, sticky="ew", padx=(10, 0))

        self.lbl_filter = ctk.CTkLabel(
            col_left,
            text=i18n("file_filter"),
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.lbl_filter.pack(anchor="w", pady=(0, 2))
        self.entry_filter = ctk.CTkEntry(
            col_left,
            placeholder_text=i18n("file_filter_hint"),
            font=ctk.CTkFont(size=12),
        )
        self.entry_filter.pack(fill="x")

        # Right Column: Robustness Settings
        col_right = ctk.CTkFrame(opt_grid, corner_radius=8)
        col_right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        self.lbl_robustness = ctk.CTkLabel(
            col_right,
            text=i18n("robustness_settings"),
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.lbl_robustness.pack(anchor="w", padx=12, pady=(8, 6))

        robust_inner = ctk.CTkFrame(col_right, fg_color="transparent")
        robust_inner.pack(fill="x", padx=12, pady=(0, 8))

        self.lbl_conflict = ctk.CTkLabel(robust_inner, text=i18n("conflict_policy"), font=ctk.CTkFont(size=12))
        self.lbl_conflict.grid(row=0, column=0, sticky="w", pady=4)
        self.opt_conflict = ctk.CTkOptionMenu(
            robust_inner,
            values=[i18n(k) for _, k in CONFLICT_POLICIES],
            command=self._on_conflict_selected,
            width=150,
        )
        self.opt_conflict.grid(row=0, column=1, sticky="w", padx=(8, 0), pady=4)

        self.chk_case = ctk.CTkCheckBox(robust_inner, text=i18n("case_sensitive"), font=ctk.CTkFont(size=12))
        self.chk_case.select()
        self.chk_case.grid(row=1, column=0, columnspan=2, sticky="w", pady=4)

        self.lbl_sort = ctk.CTkLabel(robust_inner, text=i18n("sort_by"), font=ctk.CTkFont(size=12))
        self.lbl_sort.grid(row=2, column=0, sticky="w", pady=4)
        self.opt_sort = ctk.CTkOptionMenu(
            robust_inner,
            values=[i18n(k) for _, k in SORT_MODES],
            command=self._on_sort_selected,
            width=150,
        )
        self.opt_sort.grid(row=2, column=1, sticky="w", padx=(8, 0), pady=4)

        # ----------------------------------------------------
        # Numbered Custom Mode Card
        # ----------------------------------------------------
        card_numbered = ctk.CTkFrame(self.container, corner_radius=10)
        card_numbered.pack(fill="x", pady=6)

        num_inner = ctk.CTkFrame(card_numbered, fg_color="transparent")
        num_inner.pack(fill="x", padx=15, pady=10)

        self.chk_numbering = ctk.CTkCheckBox(
            num_inner,
            text=i18n("enable_numbered_mode"),
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.chk_numbering.pack(anchor="w", pady=(0, 4))

        self.lbl_custom = ctk.CTkLabel(num_inner, text=i18n("custom_folder_names"), font=ctk.CTkFont(size=12))
        self.lbl_custom.pack(anchor="w")

        self.lbl_custom_hint = ctk.CTkLabel(
            num_inner,
            text=i18n("custom_folder_hint"),
            font=ctk.CTkFont(size=11),
            text_color=("#666666", "#A0A0A0"),
        )
        self.lbl_custom_hint.pack(anchor="w", pady=(0, 4))

        self.txt_custom = ctk.CTkTextbox(num_inner, height=76, font=ctk.CTkFont(family=mono_font, size=12))
        self.txt_custom.pack(fill="x", pady=2)
        self.txt_custom.insert("1.0", i18n("custom_folder_example"))

        # ----------------------------------------------------
        # Action Buttons
        # ----------------------------------------------------
        btn_bar = ctk.CTkFrame(self.container, fg_color="transparent")
        btn_bar.pack(fill="x", pady=8)

        self.btn_preview = ctk.CTkButton(
            btn_bar,
            text=i18n("preview"),
            command=self.preview_groups,
            fg_color="#28a745",
            hover_color="#218838",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.btn_preview.pack(side="left", expand=True, fill="x", padx=(0, 6))

        self.btn_execute = ctk.CTkButton(
            btn_bar,
            text=i18n("execute"),
            command=self.execute_move,
            fg_color="#dc3545",
            hover_color="#c82333",
            state="disabled",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.btn_execute.pack(side="left", expand=True, fill="x", padx=6)

        self.btn_undo = ctk.CTkButton(
            btn_bar,
            text=i18n("undo"),
            command=self.undo_last_move,
            fg_color="#ffc107",
            hover_color="#e0a800",
            text_color="#1a1a1a",
            state="disabled",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.btn_undo.pack(side="left", expand=True, fill="x", padx=6)

        self.btn_export = ctk.CTkButton(
            btn_bar,
            text=i18n("export_log"),
            command=self.export_log,
            fg_color="#17a2b8",
            hover_color="#138496",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.btn_export.pack(side="left", expand=True, fill="x", padx=(6, 0))

        # ----------------------------------------------------
        # Progress Card
        # ----------------------------------------------------
        card_progress = ctk.CTkFrame(self.container, corner_radius=10)
        card_progress.pack(fill="x", pady=6)

        prog_inner = ctk.CTkFrame(card_progress, fg_color="transparent")
        prog_inner.pack(fill="x", padx=15, pady=8)

        self.lbl_progress = ctk.CTkLabel(prog_inner, text=i18n("progress_ready"), font=ctk.CTkFont(size=12))
        self.lbl_progress.pack(anchor="w", pady=(0, 4))

        self.progress_bar = ctk.CTkProgressBar(prog_inner)
        self.progress_bar.set(0.0)
        self.progress_bar.pack(fill="x")

        # ----------------------------------------------------
        # Activity Log Card
        # ----------------------------------------------------
        card_log = ctk.CTkFrame(self.container, corner_radius=10)
        card_log.pack(fill="both", expand=True, pady=6)

        log_inner = ctk.CTkFrame(card_log, fg_color="transparent")
        log_inner.pack(fill="both", expand=True, padx=15, pady=10)

        log_header = ctk.CTkFrame(log_inner, fg_color="transparent")
        log_header.pack(fill="x", pady=(0, 4))

        self.lbl_activity = ctk.CTkLabel(
            log_header,
            text=i18n("activity_log"),
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.lbl_activity.pack(side="left")

        self.btn_clear_log = ctk.CTkButton(
            log_header,
            text=i18n("clear_log"),
            command=self.clear_log,
            width=70,
            height=24,
            fg_color=("#E0E0E0", "#3C3C3C"),
            hover_color=("#CCCCCC", "#4E4E4E"),
            text_color=("#1A1A1A", "#E0E0E0"),
            font=ctk.CTkFont(size=11),
        )
        self.btn_clear_log.pack(side="right")

        self.txt_log = ctk.CTkTextbox(
            log_inner,
            font=ctk.CTkFont(family=mono_font, size=12),
            state="disabled",
        )
        self.txt_log.pack(fill="both", expand=True)

        # ----------------------------------------------------
        # Status Bar
        # ----------------------------------------------------
        self.lbl_status = ctk.CTkLabel(self.container, text=i18n("status_ready"), font=ctk.CTkFont(size=12), anchor="w")
        self.lbl_status.pack(fill="x", pady=(4, 0))

    def _restore_saved_inputs(self):
        if "default_suffix" in self.settings:
            self.entry_suffix.delete(0, "end")
            self.entry_suffix.insert(0, str(self.settings["default_suffix"]))

        if "delimiter" in self.settings and self.settings["delimiter"]:
            self.entry_delimiter.delete(0, "end")
            self.entry_delimiter.insert(0, str(self.settings["delimiter"]))

        if self.settings.get("file_filter"):
            self.entry_filter.delete(0, "end")
            self.entry_filter.insert(0, str(self.settings["file_filter"]))

        if "case_sensitive" in self.settings:
            if self.settings["case_sensitive"]:
                self.chk_case.select()
            else:
                self.chk_case.deselect()

        if self.settings.get("use_numbering"):
            self.chk_numbering.select()
        else:
            self.chk_numbering.deselect()

        last_folder = self.settings.get("last_folder", "")
        if last_folder and os.path.isdir(last_folder):
            self.load_folder(last_folder)

    def _collect_preferences(self) -> None:
        self.settings["default_suffix"] = self.entry_suffix.get().strip()
        self.settings["delimiter"] = self.entry_delimiter.get() or "-"
        self.settings["file_filter"] = self.entry_filter.get().strip()
        self.settings["conflict_policy"] = self._conflict_policy_code
        self.settings["sort_mode"] = self._sort_mode_code
        self.settings["case_sensitive"] = bool(self.chk_case.get())
        self.settings["use_numbering"] = bool(self.chk_numbering.get())
        if self.source_path:
            self.settings["last_folder"] = str(self.source_path)

    def _save_preferences(self) -> None:
        self._collect_preferences()
        save_settings(self.settings)

    def _on_close(self) -> None:
        try:
            self._save_preferences()
        except Exception:
            pass
        self.master.destroy()

    def apply_appearance_mode(self, theme_code: str) -> None:
        ctk.set_appearance_mode(theme_code)
        self.master.after(20, self._apply_log_theme)

    def _apply_log_theme(self) -> None:
        try:
            mode = ctk.get_appearance_mode().lower()
            theme = LIGHT_THEME if mode == "light" else DARK_THEME
            inner_textbox = getattr(self.txt_log, "_textbox", None)
            if inner_textbox is not None:
                inner_textbox.tag_config("INFO", foreground=theme.get("log_info"))
                inner_textbox.tag_config("SUCCESS", foreground=theme.get("log_success"))
                inner_textbox.tag_config("WARN", foreground=theme.get("log_warning"))
                inner_textbox.tag_config("ERROR", foreground=theme.get("log_error"))
        except Exception:
            pass

    def _set_status(self, key: str, color: Optional[str] = None, **kwargs) -> None:
        self._status_key = key
        self._status_kwargs = kwargs
        self._status_color = color
        cfg: Dict[str, Any] = {"text": self.i18n(key, **kwargs)}
        if color:
            cfg["text_color"] = color
        self.lbl_status.configure(**cfg)

    def update_ui_language(self):
        """Instantly update all UI labels, placeholders, and options when language changes."""
        i18n = self.i18n

        self.master.title(i18n("app_title"))
        self.lbl_app_title.configure(text=i18n("app_title"))
        self.btn_settings.configure(text="⚙ " + i18n("settings"))

        self.lbl_source.configure(text=i18n("source_folder"))
        self.entry_source.configure(placeholder_text=i18n("drag_drop_hint"))
        self.btn_browse.configure(text=i18n("browse"))

        self.lbl_suffix.configure(text=i18n("default_suffix"))
        self.lbl_delimiter.configure(text=i18n("delimiter"))
        self.entry_delimiter.configure(placeholder_text=i18n("delimiter_hint"))
        self.lbl_filter.configure(text=i18n("file_filter"))
        self.entry_filter.configure(placeholder_text=i18n("file_filter_hint"))

        self.lbl_robustness.configure(text=i18n("robustness_settings"))
        self.lbl_conflict.configure(text=i18n("conflict_policy"))
        self.chk_case.configure(text=i18n("case_sensitive"))
        self.lbl_sort.configure(text=i18n("sort_by"))

        # Update options menus
        conflict_vals = [i18n(k) for _, k in CONFLICT_POLICIES]
        self.opt_conflict.configure(values=conflict_vals)
        self.opt_conflict.set(i18n(self._key_for_policy(self._conflict_policy_code)))

        sort_vals = [i18n(k) for _, k in SORT_MODES]
        self.opt_sort.configure(values=sort_vals)
        self.opt_sort.set(i18n(self._key_for_sort(self._sort_mode_code)))

        self.chk_numbering.configure(text=i18n("enable_numbered_mode"))
        self.lbl_custom.configure(text=i18n("custom_folder_names"))
        self.lbl_custom_hint.configure(text=i18n("custom_folder_hint"))

        current_custom = self.txt_custom.get("1.0", "end").strip()
        new_example = i18n("custom_folder_example")
        if current_custom == self._last_example_text.strip():
            self.txt_custom.delete("1.0", "end")
            self.txt_custom.insert("1.0", new_example)
        self._last_example_text = new_example

        self.btn_preview.configure(text=i18n("preview"))
        self.btn_execute.configure(text=i18n("execute"))
        self.btn_undo.configure(text=i18n("undo"))
        self.btn_export.configure(text=i18n("export_log"))
        self.btn_clear_log.configure(text=i18n("clear_log"))

        if not self._is_busy:
            self.lbl_progress.configure(text=i18n("progress_ready"))
        self.lbl_activity.configure(text=i18n("activity_log"))
        self._set_status(self._status_key, self._status_color, **self._status_kwargs)

    def open_settings(self):
        if self._settings_dlg and hasattr(self._settings_dlg, "dialog") and self._settings_dlg.dialog.winfo_exists():
            self._settings_dlg.dialog.focus()
            return
        self._settings_dlg = SettingsDialog(self.master, self.i18n, self.theme_mgr, self)

    def clear_log(self):
        try:
            self.txt_log.configure(state="normal")
            self.txt_log.delete("1.0", "end")
            self.txt_log.configure(state="disabled")
        except Exception:
            pass

    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] [{level}] {message}\n"
        try:
            self.txt_log.configure(state="normal")
            inner_textbox = getattr(self.txt_log, "_textbox", None)
            if inner_textbox is not None and level in ("INFO", "SUCCESS", "WARN", "ERROR"):
                inner_textbox.insert("end", line, (level,))
            else:
                self.txt_log.insert("end", line)
            self.txt_log.see("end")
            self.txt_log.configure(state="disabled")
        except Exception:
            print(line, end="")

    def log_safe(self, message: str, level: str = "INFO"):
        try:
            self.master.after(0, self.log, message, level)
        except Exception:
            print(f"[{level}] {message}")

    def update_progress_safe(self, current: int, total: int, filename: str = ""):
        try:
            self.master.after(0, self.update_progress, current, total, filename)
        except Exception:
            pass

    def update_progress(self, current: int, total: int, filename: str = ""):
        if total > 0:
            ratio = min(1.0, max(0.0, current / total))
            self.progress_bar.set(ratio)
            percent = int(ratio * 100)
            if filename:
                display_name = filename if len(filename) < 40 else filename[:37] + "..."
                text = self.i18n("progress_file", current=current, total=total, percent=percent, filename=display_name)
            else:
                text = self.i18n("progress", current=current, total=total, percent=percent)
            self.lbl_progress.configure(text=text)

    def reset_progress(self):
        try:
            self.progress_bar.set(0.0)
            self.lbl_progress.configure(text=self.i18n("progress_ready"))
        except Exception:
            pass

    def _refresh_button_states(self):
        try:
            if self._is_busy:
                self.btn_browse.configure(state="disabled")
                self.btn_preview.configure(state="disabled")
                self.btn_export.configure(state="disabled")
                self.btn_execute.configure(state="disabled")
                self.btn_undo.configure(state="disabled")
                self.btn_clear_log.configure(state="disabled")
            else:
                self.btn_browse.configure(state="normal")
                self.btn_preview.configure(state="normal")
                self.btn_export.configure(state="normal")
                self.btn_clear_log.configure(state="normal")
                self.btn_execute.configure(state="normal" if self._can_execute else "disabled")
                can_undo = bool(self.grouper and self.grouper.log_path.exists())
                self.btn_undo.configure(state="normal" if can_undo else "disabled")
        except Exception:
            pass

    def export_log(self):
        if not self.source_path:
            messagebox.showwarning(self.i18n("no_folder_title"), self.i18n("no_folder_export"))
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = self.source_path / f"audit_log_{ts}.txt"
        try:
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(self.txt_log.get("1.0", "end"))
            messagebox.showinfo(
                self.i18n("export_success_title"),
                self.i18n("export_success_msg", path=str(log_file)),
            )
        except Exception as e:
            messagebox.showerror(self.i18n("export_failed_title"), str(e))

    def on_drop(self, event):
        try:
            items = self.master.tk.splitlist(event.data)
            candidate = items[0] if items else event.data.strip("{}").strip()
            if candidate and os.path.isdir(candidate):
                self.load_folder(candidate)
            else:
                messagebox.showwarning(self.i18n("invalid_drop_title"), self.i18n("invalid_drop_msg"))
        except Exception as e:
            messagebox.showerror(self.i18n("drop_error_title"), self.i18n("drop_error_msg", error=e))

    def browse_folder(self):
        folder = filedialog.askdirectory(title=self.i18n("select_source_folder"))
        if folder:
            self.load_folder(folder)

    def _load_from_entry(self) -> bool:
        entered = self.entry_source.get().strip()
        if not entered:
            return False
        return self.load_folder(entered)

    def load_folder(self, folder_path: str) -> bool:
        try:
            path = Path(folder_path).resolve()
            if not path.exists() or not path.is_dir():
                messagebox.showerror(self.i18n("error_title"), self.i18n("error_folder_not_exist"))
                return False
            self.source_path = path
            self.entry_source.delete(0, "end")
            self.entry_source.insert(0, str(self.source_path))
            self.grouper = FileGrouper(self.source_path)

            self.clear_log()
            self.reset_progress()
            self._can_execute = False
            self._refresh_button_states()

            self.log(self.i18n("info_folder_loaded", name=self.source_path.name), "INFO")
            self._set_status("status_loaded", color="#28a745", name=self.source_path.name)
            self._save_preferences()
            return True
        except Exception as e:
            messagebox.showerror(self.i18n("error_load_failed"), str(e))
            return False

    def get_custom_names(self) -> Optional[List[str]]:
        text = self.txt_custom.get("1.0", "end").strip()
        names = [line.strip() for line in text.splitlines() if line.strip()]
        for name in names:
            if _INVALID_PATH_CHARS_RE.search(name):
                messagebox.showwarning(
                    self.i18n("warn_invalid_name"),
                    self.i18n("warn_invalid_chars", name=name),
                )
                return None
        return names

    def _get_validated_inputs(self) -> Optional[Dict[str, Any]]:
        entered = self.entry_source.get().strip()
        if entered and (self.source_path is None or Path(entered).resolve() != self.source_path):
            if not self.load_folder(entered):
                return None

        if not self.source_path or not self.grouper:
            messagebox.showerror(self.i18n("error_title"), self.i18n("error_select_folder"))
            return None

        suffix = self.entry_suffix.get().strip()
        use_numbering = bool(self.chk_numbering.get())

        if not suffix and not use_numbering:
            messagebox.showerror(self.i18n("error_title"), self.i18n("error_suffix_required"))
            return None

        if suffix and _INVALID_PATH_CHARS_RE.search(suffix):
            messagebox.showwarning(self.i18n("warn_invalid_name"), self.i18n("warn_invalid_suffix"))
            return None

        custom_names = self.get_custom_names()
        if custom_names is None:
            return None

        delimiter = self.entry_delimiter.get()
        if not delimiter:
            delimiter = "-"
            self.entry_delimiter.delete(0, "end")
            self.entry_delimiter.insert(0, delimiter)

        return {
            "filter_text": self.entry_filter.get().strip(),
            "suffix": suffix,
            "delimiter": delimiter,
            "use_numbering": use_numbering,
            "custom_names": custom_names,
            "case_sensitive": bool(self.chk_case.get()),
            "conflict_policy": self._conflict_policy_code,
            "sort_mode": self._sort_mode_code,
        }

    @staticmethod
    def _key_for_policy(code: str) -> str:
        for c, key in CONFLICT_POLICIES:
            if c == code:
                return key
        return "conflict_skip"

    @staticmethod
    def _key_for_sort(code: str) -> str:
        for c, key in SORT_MODES:
            if c == code:
                return key
        return "sort_name"

    def _on_conflict_selected(self, display: str) -> None:
        for code, key in CONFLICT_POLICIES:
            if self.i18n(key) == display:
                self._conflict_policy_code = code
                self._save_preferences()
                return
        self._conflict_policy_code = "Skip"

    def _on_sort_selected(self, display: str) -> None:
        for code, key in SORT_MODES:
            if self.i18n(key) == display:
                self._sort_mode_code = code
                self._save_preferences()
                return
        self._sort_mode_code = "name"

    def preview_groups(self):
        params = self._get_validated_inputs()
        if params is None or not self.grouper:
            return

        self._save_preferences()
        self.clear_log()
        self.log(self.i18n("info_preview_start"), "INFO")

        groups = self.grouper.preview_groups(
            params["filter_text"],
            params["suffix"],
            params["use_numbering"],
            params["custom_names"],
            params["case_sensitive"],
            params["sort_mode"],
            delimiter=params["delimiter"],
        )

        total_files = sum(len(files) for files in groups.values())
        self.log(self.i18n("success_found", groups=len(groups), files=total_files), "SUCCESS")

        for folder_name, files in groups.items():
            self.log("\n→ " + self.i18n("target_folder", name=folder_name, count=len(files)), "INFO")
            for f in files[:6]:
                self.log(self.i18n("file_entry", name=f.name), "INFO")
            if len(files) > 6:
                self.log(self.i18n("more_files", count=len(files) - 6), "WARN")

        self.log(self.i18n("info_preview_complete"), "INFO")
        self._can_execute = total_files > 0
        self._refresh_button_states()

    def execute_move(self):
        params = self._get_validated_inputs()
        if params is None or not self.grouper:
            return

        groups = self.grouper.preview_groups(
            params["filter_text"],
            params["suffix"],
            params["use_numbering"],
            params["custom_names"],
            params["case_sensitive"],
            params["sort_mode"],
            delimiter=params["delimiter"],
        )
        total_files = sum(len(files) for files in groups.values())
        if total_files == 0:
            messagebox.showinfo(self.i18n("result_nothing"), self.i18n("result_nothing_desc"))
            return

        msg = self.i18n("confirm_move", files=total_files, groups=len(groups))
        if not messagebox.askyesno(self.i18n("confirm_move_title"), msg):
            return

        self._save_preferences()
        self._is_busy = True
        self._refresh_button_states()
        self.log(self.i18n("info_move_start"), "INFO")
        self.reset_progress()

        threading.Thread(
            target=self._execute_move_thread,
            args=(self.grouper, params),
            daemon=True,
        ).start()

    def _execute_move_thread(self, grouper: FileGrouper, params: Dict[str, Any]):
        try:
            moved, skipped, renamed, errors = grouper.execute_move(
                params["filter_text"],
                params["suffix"],
                params["use_numbering"],
                params["custom_names"],
                params["case_sensitive"],
                params["conflict_policy"],
                sort_mode=params["sort_mode"],
                progress_callback=self.update_progress_safe,
                log_callback=self.log_safe,
                delimiter=params["delimiter"],
                translate_func=self.i18n,
            )
            self.master.after(0, self._on_execute_complete, moved, skipped, renamed, errors)
        except Exception as e:
            self.log_safe(self.i18n("error_critical", error=e), "ERROR")
            self.master.after(0, self._on_worker_error)

    def _on_worker_error(self):
        self._is_busy = False
        self._refresh_button_states()
        self.reset_progress()

    def _on_execute_complete(self, moved: int, skipped: int, renamed: int, errors: int):
        self.log(
            self.i18n("success_summary", moved=moved, renamed=renamed, skipped=skipped, errors=errors),
            "SUCCESS" if errors == 0 else "WARN",
        )
        self.log(self.i18n("info_move_complete"), "INFO")

        self._set_status("status_move_complete", color="#28a745", moved=moved, renamed=renamed)
        self._is_busy = False
        self._can_execute = False
        self._refresh_button_states()
        self.reset_progress()

        parts = [self.i18n("result_success", count=moved)]
        if skipped > 0:
            parts.append(self.i18n("result_skipped", count=skipped))
        if errors > 0:
            parts.append(self.i18n("result_errors", count=errors))
        messagebox.showinfo(self.i18n("result_complete"), "\n".join(parts))

    def undo_last_move(self):
        if not self.grouper:
            return
        if not messagebox.askyesno(self.i18n("confirm_undo_title"), self.i18n("confirm_undo")):
            return

        self._is_busy = True
        self._refresh_button_states()
        self.log(self.i18n("info_undo_start"), "INFO")
        self.reset_progress()

        threading.Thread(target=self._undo_thread, args=(self.grouper,), daemon=True).start()

    def _undo_thread(self, grouper: FileGrouper):
        try:
            undone, remaining_logs = grouper.undo_last_move(
                progress_callback=self.update_progress_safe,
                log_callback=self.log_safe,
                translate_func=self.i18n,
            )
            self.master.after(0, self._on_undo_complete, undone, remaining_logs)
        except Exception as e:
            self.log_safe(self.i18n("error_critical_undo", error=e), "ERROR")
            self.master.after(0, self._on_worker_error)

    def _on_undo_complete(self, undone: int, remaining_logs: int):
        self.log(self.i18n("success_undo_summary", count=undone, remaining=remaining_logs), "SUCCESS")
        self.log(self.i18n("info_undo_complete"), "INFO")

        self._set_status("status_undo_complete", color="#28a745", count=undone)
        self._is_busy = False
        self._refresh_button_states()
        self.reset_progress()
        messagebox.showinfo(self.i18n("result_undo_success"), self.i18n("result_undo_desc", count=undone))


def main() -> None:
    """Entry point for the application."""
    if os.name == "nt":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

    if not HAS_DND:
        print(get_i18n()("dnd_not_available"))

    app_root = CTkWithDnD()

    for icon_name in ("app.ico", "icon.ico", "prefix_file_sort.ico"):
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), icon_name)
        if os.path.exists(icon_path):
            try:
                app_root.iconbitmap(icon_path)
                break
            except Exception:
                pass

    FileGrouperApp(app_root)
    app_root.mainloop()


if __name__ == "__main__":
    main()
