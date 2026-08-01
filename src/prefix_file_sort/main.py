"""Main GUI application for prefix-file-sort built with CustomTkinter."""

import os
import re
import json
import threading
import ctypes
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Set

import customtkinter as ctk
from tkinter import filedialog, messagebox

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    HAS_DND = True
except Exception:
    HAS_DND = False

from .core import FileGrouper
from .i18n import get_i18n, set_language, I18n
from .themes import get_theme_manager, set_theme, ThemeManager

# Settings storage path (primary: user home directory; fallback: application directory)
APP_SETTINGS_FILE = os.path.join(Path.home(), ".prefix_file_sort_settings.json")
APP_SETTINGS_FILE_LOCAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".app_settings.json")

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


def load_settings() -> Dict:
    """Load application settings from file."""
    for settings_path in (APP_SETTINGS_FILE, APP_SETTINGS_FILE_LOCAL):
        try:
            if os.path.exists(settings_path):
                with open(settings_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            continue
    return {"theme": "dark", "language": "en"}


def save_settings(settings: Dict) -> None:
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
        self.settings = load_settings()

        self.dialog = ctk.CTkToplevel(parent)
        self.dialog.title(i18n("settings_title"))
        self.dialog.geometry("440x300")
        self.dialog.resizable(False, False)

        # Do NOT call self.dialog.grab_set() as modal grabs during live theme/language switching cause event loop deadlocks on Windows.
        self.dialog.after(100, lambda: self._safe_focus())

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

    def _create_widgets(self):
        i18n = self.i18n

        self.main_frame = ctk.CTkFrame(self.dialog, corner_radius=10)
        self.main_frame.pack(fill="both", expand=True, padx=15, pady=15)

        self.lbl_title = ctk.CTkLabel(self.main_frame, text=i18n("settings_title"),
                                      font=ctk.CTkFont(size=18, weight="bold"))
        self.lbl_title.pack(anchor="w", padx=15, pady=(15, 10))

        # Language Selection
        self.lbl_lang = ctk.CTkLabel(self.main_frame, text=i18n("language"), font=ctk.CTkFont(size=13))
        self.lbl_lang.pack(anchor="w", padx=15, pady=(5, 2))

        current_lang = "English" if i18n.language == "en" else "中文"
        self.seg_lang = ctk.CTkSegmentedButton(self.main_frame, values=["English", "中文"],
                                                command=self._on_lang_change)
        self.seg_lang.set(current_lang)
        self.seg_lang.pack(fill="x", padx=15, pady=(0, 15))

        # Theme Selection
        self.lbl_theme = ctk.CTkLabel(self.main_frame, text=i18n("theme"), font=ctk.CTkFont(size=13))
        self.lbl_theme.pack(anchor="w", padx=15, pady=(5, 2))

        current_theme = self.settings.get("theme", "dark").capitalize()
        if current_theme not in ("Light", "Dark", "System"):
            current_theme = "Dark"
        self.seg_theme = ctk.CTkSegmentedButton(self.main_frame, values=["Light", "Dark", "System"],
                                                 command=self._on_theme_change)
        self.seg_theme.set(current_theme)
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
                self.lbl_title.configure(text=self.i18n("settings_title"))
                self.lbl_lang.configure(text=self.i18n("language"))
                self.lbl_theme.configure(text=self.i18n("theme"))
                self.btn_close.configure(text=self.i18n("close"))
        except Exception:
            pass
        self.app.update_ui_language()

    def _on_theme_change(self, value: str):
        theme_code = value.lower()
        self.settings["theme"] = theme_code
        save_settings(self.settings)
        set_theme(theme_code)
        # Asynchronously schedule theme switch on next event loop tick
        self.dialog.after(10, lambda: ctk.set_appearance_mode(theme_code))


class FileGrouperApp:
    """Main application GUI using CustomTkinter."""

    def __init__(self, master: CTkWithDnD):
        self.master = master
        self.settings = load_settings()
        self.i18n = get_i18n()
        self.theme_mgr = get_theme_manager()
        self._settings_dlg: Optional[SettingsDialog] = None

        self.i18n.language = self.settings.get("language", "en")
        initial_theme = self.settings.get("theme", "dark")
        ctk.set_appearance_mode(initial_theme)

        self.source_path: Optional[Path] = None
        self.grouper: Optional[FileGrouper] = None

        self._conflict_policy_code = "Skip"
        self._sort_mode_code = "name"

        self.master.title(self.i18n("app_title"))
        self.master.geometry("1080x880")
        self.master.minsize(960, 780)

        self.create_widgets()
        self.update_ui_language()

    def create_widgets(self):
        i18n = self.i18n

        # Main scrollable container
        self.container = ctk.CTkFrame(self.master, corner_radius=0, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=20, pady=15)

        # ----------------------------------------------------
        # Header Bar
        # ----------------------------------------------------
        header_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 10))

        title_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_frame.pack(side="left")

        self.lbl_app_title = ctk.CTkLabel(title_frame, text=i18n("app_title"),
                                           font=ctk.CTkFont(size=22, weight="bold"))
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
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.btn_settings.pack(side="right", anchor="ne")

        # ----------------------------------------------------
        # Source Folder Card
        # ----------------------------------------------------
        card_source = ctk.CTkFrame(self.container, corner_radius=10)
        card_source.pack(fill="x", pady=6)

        self.lbl_source = ctk.CTkLabel(card_source, text=i18n("source_folder"), font=ctk.CTkFont(size=13, weight="bold"))
        self.lbl_source.pack(anchor="w", padx=15, pady=(10, 4))

        src_input_frame = ctk.CTkFrame(card_source, fg_color="transparent")
        src_input_frame.pack(fill="x", padx=15, pady=(0, 12))

        self.entry_source = ctk.CTkEntry(src_input_frame, placeholder_text=i18n("drag_drop_hint"), font=ctk.CTkFont(size=12))
        self.entry_source.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.btn_browse = ctk.CTkButton(src_input_frame, text=i18n("browse"), command=self.browse_folder, width=110)
        self.btn_browse.pack(side="right")

        # Drag and Drop binding
        if HAS_DND:
            try:
                self.master.drop_target_register(DND_FILES)
                self.master.dnd_bind('<<Drop>>', self.on_drop)
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

        # Left Column: Suffix & Extension Filter
        col_left = ctk.CTkFrame(opt_grid, fg_color="transparent")
        col_left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        self.lbl_suffix = ctk.CTkLabel(col_left, text=i18n("default_suffix"), font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_suffix.pack(anchor="w", pady=(0, 2))
        self.entry_suffix = ctk.CTkEntry(col_left, font=ctk.CTkFont(size=12))
        self.entry_suffix.insert(0, "series")
        self.entry_suffix.pack(fill="x", pady=(0, 8))

        self.lbl_filter = ctk.CTkLabel(col_left, text=i18n("file_filter"), font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_filter.pack(anchor="w", pady=(0, 2))
        self.entry_filter = ctk.CTkEntry(col_left, placeholder_text=i18n("file_filter_hint"), font=ctk.CTkFont(size=12))
        self.entry_filter.pack(fill="x")

        # Right Column: Robustness Settings
        col_right = ctk.CTkFrame(opt_grid, corner_radius=8)
        col_right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        self.lbl_robustness = ctk.CTkLabel(col_right, text=i18n("robustness_settings"), font=ctk.CTkFont(size=13, weight="bold"))
        self.lbl_robustness.pack(anchor="w", padx=12, pady=(8, 6))

        robust_inner = ctk.CTkFrame(col_right, fg_color="transparent")
        robust_inner.pack(fill="x", padx=12, pady=(0, 8))

        self.lbl_conflict = ctk.CTkLabel(robust_inner, text=i18n("conflict_policy"), font=ctk.CTkFont(size=12))
        self.lbl_conflict.grid(row=0, column=0, sticky="w", pady=4)
        self.opt_conflict = ctk.CTkOptionMenu(robust_inner, values=[i18n(k) for _, k in CONFLICT_POLICIES],
                                               command=self._on_conflict_selected, width=150)
        self.opt_conflict.grid(row=0, column=1, sticky="w", padx=(8, 0), pady=4)

        self.chk_case = ctk.CTkCheckBox(robust_inner, text=i18n("case_sensitive"), font=ctk.CTkFont(size=12))
        self.chk_case.select()
        self.chk_case.grid(row=1, column=0, columnspan=2, sticky="w", pady=4)

        self.lbl_sort = ctk.CTkLabel(robust_inner, text=i18n("sort_by"), font=ctk.CTkFont(size=12))
        self.lbl_sort.grid(row=2, column=0, sticky="w", pady=4)
        self.opt_sort = ctk.CTkOptionMenu(robust_inner, values=[i18n(k) for _, k in SORT_MODES],
                                          command=self._on_sort_selected, width=150)
        self.opt_sort.grid(row=2, column=1, sticky="w", padx=(8, 0), pady=4)

        # ----------------------------------------------------
        # Numbered Custom Mode Card
        # ----------------------------------------------------
        card_numbered = ctk.CTkFrame(self.container, corner_radius=10)
        card_numbered.pack(fill="x", pady=6)

        num_inner = ctk.CTkFrame(card_numbered, fg_color="transparent")
        num_inner.pack(fill="x", padx=15, pady=10)

        self.chk_numbering = ctk.CTkCheckBox(num_inner, text=i18n("enable_numbered_mode"),
                                              font=ctk.CTkFont(size=13, weight="bold"))
        self.chk_numbering.pack(anchor="w", pady=(0, 4))

        self.lbl_custom = ctk.CTkLabel(num_inner, text=i18n("custom_folder_names"), font=ctk.CTkFont(size=12))
        self.lbl_custom.pack(anchor="w")

        self.lbl_custom_hint = ctk.CTkLabel(num_inner, text=i18n("custom_folder_hint"), font=ctk.CTkFont(size=11),
                                                 text_color="gray")
        self.lbl_custom_hint.pack(anchor="w", pady=(0, 4))

        self.txt_custom = ctk.CTkTextbox(num_inner, height=80, font=ctk.CTkFont(family="Consolas", size=12))
        self.txt_custom.pack(fill="x", pady=2)
        self.txt_custom.insert("1.0", i18n("custom_folder_example"))

        # ----------------------------------------------------
        # Action Buttons
        # ----------------------------------------------------
        btn_bar = ctk.CTkFrame(self.container, fg_color="transparent")
        btn_bar.pack(fill="x", pady=8)

        self.btn_preview = ctk.CTkButton(btn_bar, text=i18n("preview"), command=self.preview_groups,
                                         fg_color="#28a745", hover_color="#218838", font=ctk.CTkFont(size=13, weight="bold"))
        self.btn_preview.pack(side="left", expand=True, fill="x", padx=(0, 6))

        self.btn_execute = ctk.CTkButton(btn_bar, text=i18n("execute"), command=self.execute_move,
                                         fg_color="#dc3545", hover_color="#c82333", state="disabled",
                                         font=ctk.CTkFont(size=13, weight="bold"))
        self.btn_execute.pack(side="left", expand=True, fill="x", padx=6)

        self.btn_undo = ctk.CTkButton(btn_bar, text=i18n("undo"), command=self.undo_last_move,
                                      fg_color="#ffc107", hover_color="#e0a800", text_color="#1a1a1a", state="disabled",
                                      font=ctk.CTkFont(size=13, weight="bold"))
        self.btn_undo.pack(side="left", expand=True, fill="x", padx=6)

        self.btn_export = ctk.CTkButton(btn_bar, text=i18n("export_log"), command=self.export_log,
                                        fg_color="#17a2b8", hover_color="#138496",
                                        font=ctk.CTkFont(size=13, weight="bold"))
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

        self.lbl_activity = ctk.CTkLabel(log_inner, text=i18n("activity_log"), font=ctk.CTkFont(size=13, weight="bold"))
        self.lbl_activity.pack(anchor="w", pady=(0, 4))

        self.txt_log = ctk.CTkTextbox(log_inner, font=ctk.CTkFont(family="Consolas", size=12))
        self.txt_log.pack(fill="both", expand=True)

        # ----------------------------------------------------
        # Status Bar
        # ----------------------------------------------------
        self.lbl_status = ctk.CTkLabel(self.container, text=i18n("status_ready"), font=ctk.CTkFont(size=12), anchor="w")
        self.lbl_status.pack(fill="x", pady=(4, 0))

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

        self.btn_preview.configure(text=i18n("preview"))
        self.btn_execute.configure(text=i18n("execute"))
        self.btn_undo.configure(text=i18n("undo"))
        self.btn_export.configure(text=i18n("export_log"))

        self.lbl_progress.configure(text=i18n("progress_ready"))
        self.lbl_activity.configure(text=i18n("activity_log"))
        self.lbl_status.configure(text=i18n("status_ready"))

    def open_settings(self):
        if self._settings_dlg and hasattr(self._settings_dlg, "dialog") and self._settings_dlg.dialog.winfo_exists():
            self._settings_dlg.dialog.focus()
            return
        self._settings_dlg = SettingsDialog(self.master, self.i18n, self.theme_mgr, self)

    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prefix = f"[{timestamp}] [{level}] "
        try:
            self.txt_log.insert("end", prefix + message + "\n")
            self.txt_log.see("end")
        except Exception:
            print(prefix + message)

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
            ratio = current / total
            self.progress_bar.set(ratio)
            percent = int(ratio * 100)
            text = f"Progress: {current}/{total} ({percent}%)"
            if filename:
                display_name = filename if len(filename) < 40 else filename[:37] + "..."
                text += f" - {display_name}"
            self.lbl_progress.configure(text=text)

    def reset_progress(self):
        try:
            self.progress_bar.set(0.0)
            self.lbl_progress.configure(text=self.i18n("progress_ready"))
        except Exception:
            pass

    def set_buttons_state(self, state="normal"):
        try:
            self.btn_browse.configure(state=state)
            self.btn_preview.configure(state=state)
            self.btn_export.configure(state=state)
            if self.btn_execute.cget("state") != "disabled":
                self.btn_execute.configure(state=state)
            if self.btn_undo.cget("state") != "disabled":
                self.btn_undo.configure(state=state)
        except Exception:
            pass

    def export_log(self):
        if not self.source_path:
            messagebox.showwarning("No folder", "Please load a folder before exporting the log.")
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = self.source_path / f"audit_log_{ts}.txt"
        try:
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(self.txt_log.get("1.0", "end"))
            messagebox.showinfo("Success", f"Audit log exported to:\n{log_file}")
        except Exception as e:
            messagebox.showerror("Export Failed", str(e))

    def on_drop(self, event):
        try:
            path_raw = event.data
            path = path_raw.strip('{}').strip()
            if path and os.path.isdir(path):
                self.load_folder(path)
            else:
                messagebox.showwarning("Invalid Drop", "Please drop a valid folder.")
        except Exception as e:
            messagebox.showerror("Drop Error", f"Failed to load folder: {e}")

    def browse_folder(self):
        folder = filedialog.askdirectory(title="Select Source Folder")
        if folder:
            self.load_folder(folder)

    def load_folder(self, folder_path: str):
        try:
            path = Path(folder_path).resolve()
            if not path.exists() or not path.is_dir():
                messagebox.showerror("Error", "Folder does not exist!")
                return
            self.source_path = path
            self.entry_source.delete(0, "end")
            self.entry_source.insert(0, str(self.source_path))
            self.grouper = FileGrouper(self.source_path)

            self.txt_log.delete("1.0", "end")
            self.reset_progress()

            undo_state = "normal" if self.grouper.log_path.exists() else "disabled"
            self.btn_undo.configure(state=undo_state)
            self.btn_execute.configure(state="disabled")

            self.log(f"Folder loaded: {self.source_path.name}", "INFO")
            self.lbl_status.configure(text=f"Loaded: {self.source_path.name}", text_color="#28a745")
        except Exception as e:
            messagebox.showerror("Load Failed", str(e))

    def get_custom_names(self) -> List[str]:
        text = self.txt_custom.get("1.0", "end").strip()
        names = [line.strip() for line in text.splitlines() if line.strip()]
        invalid_chars = r'[\\/:\\*?"<>|]'
        for name in names:
            if re.search(invalid_chars, name):
                messagebox.showwarning("Invalid Name", f"Folder name '{name}' contains invalid characters")
                return []
        return names

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
                return
        self._conflict_policy_code = "Skip"

    def _on_sort_selected(self, display: str) -> None:
        for code, key in SORT_MODES:
            if self.i18n(key) == display:
                self._sort_mode_code = code
                return
        self._sort_mode_code = "name"

    def preview_groups(self):
        if not self.source_path or not self.grouper:
            messagebox.showerror("Error", "Please select a folder first!")
            return

        suffix = self.entry_suffix.get().strip()
        use_numbering = bool(self.chk_numbering.get())
        custom_names = self.get_custom_names()
        case_sensitive = bool(self.chk_case.get())

        if not suffix and not use_numbering:
            messagebox.showerror("Error", "Please enter a Default Suffix or enable Numbered Custom Mode!")
            return

        self.txt_log.delete("1.0", "end")
        self.log(self.i18n("info_preview_start"), "INFO")

        filter_text = self.entry_filter.get().strip()
        groups = self.grouper.preview_groups(filter_text, suffix, use_numbering, custom_names, case_sensitive, self._sort_mode_code)

        total_files = sum(len(files) for files in groups.values())
        self.log(self.i18n("success_found", groups=len(groups), files=total_files), "SUCCESS")

        for folder_name, files in groups.items():
            self.log(f"\n→ Target Folder: {folder_name}  ({len(files)} files)", "INFO")
            for f in files[:6]:
                self.log(f"   └─ {f.name}", "INFO")
            if len(files) > 6:
                self.log(f"   ... and {len(files) - 6} more files", "WARN")

        self.log(self.i18n("info_preview_complete"), "INFO")
        self.btn_execute.configure(state="normal" if total_files > 0 else "disabled")

    def execute_move(self):
        if not self.source_path or not self.grouper:
            return

        suffix = self.entry_suffix.get().strip()
        use_numbering = bool(self.chk_numbering.get())
        custom_names = self.get_custom_names()
        case_sensitive = bool(self.chk_case.get())
        filter_text = self.entry_filter.get().strip()

        groups = self.grouper.preview_groups(filter_text, suffix, use_numbering, custom_names, case_sensitive, self._sort_mode_code)
        total_files = sum(len(files) for files in groups.values())
        if total_files == 0:
            messagebox.showinfo("Nothing to do", "No files matched the filter/prefix criteria.")
            return

        msg = f"You are about to move {total_files} files into {len(groups)} folders.\n\nContinue?"
        if not messagebox.askyesno("Confirm", msg):
            return

        self.set_buttons_state("disabled")
        self.log(self.i18n("info_move_start"), "INFO")
        self.reset_progress()

        threading.Thread(target=self._execute_move_thread, daemon=True).start()

    def _execute_move_thread(self):
        try:
            filter_text = self.entry_filter.get().strip()
            suffix = self.entry_suffix.get().strip()
            use_numbering = bool(self.chk_numbering.get())
            custom_names = self.get_custom_names()
            case_sensitive = bool(self.chk_case.get())
            conflict_policy = self._conflict_policy_code
            sort_mode = self._sort_mode_code

            moved, skipped, renamed, errors = self.grouper.execute_move(
                filter_text, suffix, use_numbering, custom_names, case_sensitive, conflict_policy,
                sort_mode=sort_mode,
                progress_callback=self.update_progress_safe,
                log_callback=self.log_safe
            )

            self.master.after(0, self._on_execute_complete, moved, skipped, renamed, errors)
        except Exception as e:
            self.log_safe(f"Critical error during move: {e}", "ERROR")
            self.master.after(0, self.set_buttons_state, "normal")

    def _on_execute_complete(self, moved, skipped, renamed, errors):
        self.log(self.i18n("success_summary", moved=moved, renamed=renamed, skipped=skipped, errors=errors), "SUCCESS")
        self.log(self.i18n("info_move_complete"), "INFO")

        self.lbl_status.configure(text=f"Move completed (Moved {moved}, Renamed {renamed})", text_color="#28a745")
        self.btn_undo.configure(state="normal")
        self.set_buttons_state("normal")
        self.reset_progress()

        msg = f"Successfully grouped {moved + renamed} files.\n"
        if skipped > 0:
            msg += f"Skipped {skipped} conflicts.\n"
        if errors > 0:
            msg += f"Errors on {errors} files (check log)."
        messagebox.showinfo("Operation Complete", msg)

    def undo_last_move(self):
        if not self.grouper:
            return
        if not messagebox.askyesno("Confirm", "Undo the LAST batch of moves?"):
            return

        self.set_buttons_state("disabled")
        self.log(self.i18n("info_undo_start"), "INFO")
        self.reset_progress()

        threading.Thread(target=self._undo_thread, daemon=True).start()

    def _undo_thread(self):
        try:
            undone, remaining_logs = self.grouper.undo_last_move(
                progress_callback=self.update_progress_safe,
                log_callback=self.log_safe
            )
            self.master.after(0, self._on_undo_complete, undone, remaining_logs)
        except Exception as e:
            self.log_safe(f"Critical error during undo: {e}", "ERROR")
            self.master.after(0, self.set_buttons_state, "normal")

    def _on_undo_complete(self, undone, remaining_logs):
        self.log(self.i18n("success_undo_summary", count=undone, remaining=remaining_logs), "SUCCESS")
        self.log(self.i18n("info_undo_complete"), "INFO")

        self.lbl_status.configure(text=f"Undo completed ({undone} files restored)", text_color="#28a745")

        self.set_buttons_state("normal")
        self.btn_undo.configure(state="normal" if remaining_logs > 0 else "disabled")
        self.reset_progress()
        messagebox.showinfo("Undo Success", f"Successfully restored {undone} files.\nCleaned up residual empty folders.")


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
        print("Warning: tkinterdnd2 not available; drag-and-drop disabled. Install with: pip install tkinterdnd2")

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
