import os
import re
import json
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from tkinter.ttk import Progressbar, Combobox
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    HAS_DND = True
except Exception:
    HAS_DND = False
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Set

# Core business logic (tkinter-free, importable in headless/CI environments)
from core import FileGrouper

# Internationalization and theming
from i18n import get_i18n, set_language, I18n
from themes import get_theme_manager, set_theme, ThemeManager, THEMES

# Settings storage
APP_SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".app_settings.json")

# Sort mode options: (internal_code, i18n_key). Internal codes are stable and
# are consumed by core.FileGrouper; the i18n key provides the localized label.
SORT_MODES = [
    ("name", "sort_name"),
    ("natural", "sort_natural"),
    ("mtime_newest", "sort_mtime_newest"),
    ("mtime_oldest", "sort_mtime_oldest"),
    ("size_largest", "sort_size_largest"),
    ("size_smallest", "sort_size_smallest"),
]

# Conflict policy options: (internal_code, i18n_key). Internal codes are the
# stable English strings that core.FileGrouper compares against; the i18n key
# provides the localized label shown in the UI. Keeping the two decoupled means
# the conflict policy keeps working correctly after switching the UI language.
CONFLICT_POLICIES = [
    ("Skip", "conflict_skip"),
    ("Overwrite", "conflict_overwrite"),
    ("Auto-Rename", "conflict_auto_rename"),
]


def load_settings() -> Dict:
    """Load application settings from file."""
    try:
        if os.path.exists(APP_SETTINGS_FILE):
            with open(APP_SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {"theme": "light", "language": "en"}


def save_settings(settings: Dict) -> None:
    """Save application settings to file."""
    try:
        with open(APP_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except Exception:
        pass


class SettingsDialog:
    """Settings dialog for theme and language selection."""

    def __init__(self, parent, i18n: I18n, theme_mgr: ThemeManager, app):
        self.i18n = i18n
        self.theme_mgr = theme_mgr
        self.app = app
        self.settings = load_settings()

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(i18n("settings_title"))
        self.dialog.geometry("400x250")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.dialog.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.dialog.winfo_height()) // 2
        self.dialog.geometry(f"+{x}+{y}")

        self._create_widgets()

    def _create_widgets(self):
        theme = self.theme_mgr.current_theme
        i18n = self.i18n

        frame = tk.Frame(self.dialog, padx=20, pady=20, bg=theme.get("bg_primary"))
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text=i18n("language"), font=("Arial", 11),
                 bg=theme.get("bg_primary"), fg=theme.get("text_primary")).pack(anchor="w", pady=(0, 5))

        self.lang_var = tk.StringVar(value=i18n.language)
        lang_frame = tk.Frame(frame, bg=theme.get("bg_primary"))
        lang_frame.pack(fill="x", pady=(0, 15))

        for lang_code, lang_name in i18n.available_languages.items():
            tk.Radiobutton(lang_frame, text=lang_name, variable=self.lang_var, value=lang_code,
                           font=("Arial", 10), bg=theme.get("bg_primary"),
                           fg=theme.get("text_primary"), selectcolor=theme.get("accent"),
                           command=self._on_lang_change).pack(side="left", padx=(0, 15))

        tk.Label(frame, text=i18n("theme"), font=("Arial", 11),
                 bg=theme.get("bg_primary"), fg=theme.get("text_primary")).pack(anchor="w", pady=(0, 5))

        self.theme_var = tk.StringVar(value=theme.name)
        theme_frame = tk.Frame(frame, bg=theme.get("bg_primary"))
        theme_frame.pack(fill="x", pady=(0, 20))

        theme_options = [("light", i18n("theme_light")), ("dark", i18n("theme_dark"))]

        for theme_code, theme_name in theme_options:
            tk.Radiobutton(theme_frame, text=theme_name, variable=self.theme_var, value=theme_code,
                           font=("Arial", 10), bg=theme.get("bg_primary"),
                           fg=theme.get("text_primary"), selectcolor=theme.get("accent"),
                           command=self._on_theme_change).pack(side="left", padx=(0, 15))

        btn_frame = tk.Frame(frame, bg=theme.get("bg_primary"))
        btn_frame.pack(side="bottom", pady=(10, 0))

        tk.Button(btn_frame, text=i18n("close"), command=self.dialog.destroy, width=10,
                  bg=theme.get("btn_secondary_bg"), fg=theme.get("btn_secondary_fg"), relief="flat").pack()

    def _on_lang_change(self):
        new_lang = self.lang_var.get()
        self.i18n.language = new_lang
        self.settings["language"] = new_lang
        save_settings(self.settings)
        set_language(new_lang)

    def _on_theme_change(self):
        new_theme = self.theme_var.get()
        self.theme_mgr.set_theme(new_theme)
        self.settings["theme"] = new_theme
        save_settings(self.settings)
        set_theme(new_theme)
        self.app.apply_theme_update()


class FileGrouperApp:
    """Main application GUI with theme and i18n support."""

    def __init__(self, master):
        self.master = master
        self.settings = load_settings()
        self.i18n = get_i18n()
        self.theme_mgr = get_theme_manager()

        self.i18n.language = self.settings.get("language", "en")
        self.theme_mgr.set_theme(self.settings.get("theme", "light"))

        self.source_var = tk.StringVar()
        self.suffix_var = tk.StringVar(value="series")
        self.filter_var = tk.StringVar(value="")
        self.numbering_var = tk.BooleanVar(value=False)
        self.case_sensitive_var = tk.BooleanVar(value=True)
        # Conflict policy / sort mode: the widget variables hold the localized
        # *display* label, while these plain attributes hold the stable internal
        # code that core.FileGrouper consumes. This decoupling keeps behavior
        # correct when the UI language is switched at runtime (the combobox is
        # rebuilt with new labels, but the selected policy/mode is preserved).
        self._conflict_policy_code = "Skip"
        self._sort_mode_code = "name"
        self.conflict_policy_var = tk.StringVar(value=self.i18n("conflict_skip"))
        self.sort_mode_var = tk.StringVar(value=self.i18n("sort_name"))

        self.source_path: Optional[Path] = None
        self.grouper: Optional[FileGrouper] = None
        self._widgets = {}

        self._apply_theme_to_window()
        self.master.title(self.i18n("app_title"))
        try:
            self.master.geometry("1024x820")
        except Exception:
            pass
        self.master.resizable(True, True)

        self.create_widgets()

    def _apply_theme_to_window(self):
        theme = self.theme_mgr.current_theme
        try:
            self.master.configure(bg=theme.get("bg_primary"))
        except Exception:
            pass

    def create_widgets(self):
        theme = self.theme_mgr.current_theme
        i18n = self.i18n

        self._widgets['title'] = tk.Label(self.master, text=i18n("app_title"), font=("Arial", 18, "bold"),
                                          bg=theme.get("bg_primary"), fg=theme.get("text_primary"))
        self._widgets['title'].pack(pady=12)

        # Settings button
        settings_btn_frame = tk.Frame(self.master, bg=theme.get("bg_primary"))
        settings_btn_frame.pack(fill="x", padx=20)
        tk.Frame(settings_btn_frame, bg=theme.get("bg_primary")).pack(side="right")
        self._widgets['settings_btn'] = tk.Button(settings_btn_frame, text="⚙ " + i18n("settings"),
                                                   command=self.open_settings, bg=theme.get("btn_secondary_bg"),
                                                   fg=theme.get("btn_secondary_fg"), relief="flat", padx=10)
        self._widgets['settings_btn'].pack(side="right")

        # Source folder
        source_frame = tk.Frame(self.master, bg=theme.get("bg_primary"))
        source_frame.pack(fill="x", padx=20, pady=5)
        self._widgets['source_label'] = tk.Label(source_frame, text=i18n("source_folder"), font=("Arial", 10),
                                                 bg=theme.get("bg_primary"), fg=theme.get("text_primary"))
        self._widgets['source_label'].pack(anchor="w")
        self._widgets['folder_entry'] = tk.Entry(source_frame, textvariable=self.source_var, font=("Arial", 10),
                                                  bg=theme.get("entry_bg"), fg=theme.get("entry_fg"),
                                                  insertbackground=theme.get("entry_insert"), relief="solid", bd=1)
        self._widgets['folder_entry'].pack(fill="x", pady=2)

        # Options
        options_frame = tk.Frame(self.master, bg=theme.get("bg_primary"))
        options_frame.pack(fill="x", padx=20, pady=5)

        left_opt = tk.Frame(options_frame, bg=theme.get("bg_primary"))
        left_opt.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self._widgets['suffix_label'] = tk.Label(left_opt, text=i18n("default_suffix"), font=("Arial", 10),
                                                 bg=theme.get("bg_primary"), fg=theme.get("text_primary"))
        self._widgets['suffix_label'].pack(anchor="w")
        self._widgets['suffix_entry'] = tk.Entry(left_opt, textvariable=self.suffix_var, font=("Arial", 10),
                                                  bg=theme.get("entry_bg"), fg=theme.get("entry_fg"),
                                                  insertbackground=theme.get("entry_insert"), relief="solid", bd=1)
        self._widgets['suffix_entry'].pack(fill="x", pady=(0, 8))

        self._widgets['filter_label'] = tk.Label(left_opt, text=i18n("file_filter"), font=("Arial", 10),
                                                 bg=theme.get("bg_primary"), fg=theme.get("text_primary"))
        self._widgets['filter_label'].pack(anchor="w")
        self._widgets['filter_entry'] = tk.Entry(left_opt, textvariable=self.filter_var, font=("Arial", 10),
                                                  bg=theme.get("entry_bg"), fg=theme.get("entry_fg"),
                                                  insertbackground=theme.get("entry_insert"), relief="solid", bd=1)
        self._widgets['filter_entry'].pack(fill="x")

        # Robustness settings
        right_opt = tk.LabelFrame(options_frame, text=i18n("robustness_settings"), font=("Arial", 9, "bold"),
                                  bg=theme.get("bg_secondary"), fg=theme.get("text_primary"), padx=10, pady=5)
        right_opt.pack(side="right", fill="both", expand=True)

        self._widgets['conflict_label'] = tk.Label(right_opt, text=i18n("conflict_policy"), font=("Arial", 9),
                                                  bg=theme.get("bg_secondary"), fg=theme.get("text_primary"))
        self._widgets['conflict_label'].grid(row=0, column=0, sticky="w", pady=2)

        conflict_values = [self.i18n(key) for _, key in CONFLICT_POLICIES]
        self._widgets['conflict_cb'] = Combobox(right_opt, textvariable=self.conflict_policy_var,
                                                values=conflict_values, state="readonly", width=15)
        self._widgets['conflict_cb'].grid(row=0, column=1, sticky="w", padx=5, pady=2)
        self._widgets['conflict_cb'].set(self.i18n(self._key_for_policy(self._conflict_policy_code)))
        self._widgets['conflict_cb'].bind('<<ComboboxSelected>>', self._on_conflict_selected)

        self._widgets['case_cb'] = tk.Checkbutton(right_opt, text=i18n("case_sensitive"),
                                                  variable=self.case_sensitive_var, font=("Arial", 9),
                                                  bg=theme.get("bg_secondary"), fg=theme.get("text_primary"),
                                                  selectcolor=theme.get("entry_bg"))
        self._widgets['case_cb'].grid(row=1, column=0, columnspan=2, sticky="w", pady=2)

        self._widgets['sort_label'] = tk.Label(right_opt, text=i18n("sort_by"), font=("Arial", 9),
                                               bg=theme.get("bg_secondary"), fg=theme.get("text_primary"))
        self._widgets['sort_label'].grid(row=2, column=0, sticky="w", pady=2)
        sort_values = [self.i18n(key) for _, key in SORT_MODES]
        self._widgets['sort_cb'] = Combobox(right_opt, textvariable=self.sort_mode_var,
                                            values=sort_values, state="readonly", width=15)
        self._widgets['sort_cb'].grid(row=2, column=1, sticky="w", padx=5, pady=2)
        self._widgets['sort_cb'].set(self.i18n(self._key_for_sort(self._sort_mode_code)))
        self._widgets['sort_cb'].bind('<<ComboboxSelected>>', self._on_sort_selected)

        # Numbered mode
        numbered_frame = tk.Frame(self.master, bg=theme.get("bg_primary"))
        numbered_frame.pack(fill="x", padx=20, pady=(10, 5))
        self._widgets['numbering_cb'] = tk.Checkbutton(numbered_frame, text=i18n("enable_numbered_mode"),
                                                      variable=self.numbering_var, font=("Arial", 10, "bold"),
                                                      bg=theme.get("bg_primary"), fg=theme.get("text_primary"),
                                                      selectcolor=theme.get("entry_bg"))
        self._widgets['numbering_cb'].pack(anchor="w")

        custom_frame = tk.Frame(self.master, bg=theme.get("bg_primary"))
        custom_frame.pack(fill="x", padx=20, pady=0)
        self._widgets['custom_label'] = tk.Label(custom_frame, text=i18n("custom_folder_names"), font=("Arial", 9),
                                                bg=theme.get("bg_primary"), fg=theme.get("text_primary"))
        self._widgets['custom_label'].pack(anchor="w")
        self._widgets['custom_hint'] = tk.Label(custom_frame, text=i18n("custom_folder_hint"), font=("Arial", 8),
                                               bg=theme.get("bg_primary"), fg=theme.get("text_secondary"))
        self._widgets['custom_hint'].pack(anchor="w")
        self._widgets['custom_text'] = scrolledtext.ScrolledText(custom_frame, height=4, font=("Consolas", 10),
                                                                  bg=theme.get("entry_bg"), fg=theme.get("entry_fg"))
        self._widgets['custom_text'].pack(fill="x", pady=2)
        self.custom_names_text = self._widgets['custom_text']
        self._widgets['custom_text'].insert(tk.END, i18n("custom_folder_example"))

        # Drag and drop
        if HAS_DND:
            try:
                self.master.drop_target_register(DND_FILES)
                self.master.dnd_bind('<<Drop>>', self.on_drop)
            except Exception:
                pass

        # Buttons
        btn_frame = tk.Frame(self.master, bg=theme.get("bg_primary"))
        btn_frame.pack(pady=10)

        self._widgets['browse_btn'] = tk.Button(btn_frame, text=i18n("browse"), command=self.browse_folder, width=12,
                                                bg=theme.get("btn_secondary_bg"), fg=theme.get("btn_secondary_fg"), relief="flat")
        self._widgets['browse_btn'].pack(side="left", padx=5)

        self._widgets['preview_btn'] = tk.Button(btn_frame, text=i18n("preview"), command=self.preview_groups, width=15,
                                                 bg=theme.get("success"), fg="white")
        self._widgets['preview_btn'].pack(side="left", padx=5)

        self._widgets['execute_btn'] = tk.Button(btn_frame, text=i18n("execute"), command=self.execute_move, width=15,
                                                  bg=theme.get("error"), fg="white", state="disabled")
        self._widgets['execute_btn'].pack(side="left", padx=5)

        self._widgets['undo_btn'] = tk.Button(btn_frame, text=i18n("undo"), command=self.undo_last_move, width=15,
                                               bg=theme.get("warning"), fg="white", state="disabled")
        self._widgets['undo_btn'].pack(side="left", padx=5)

        self._widgets['export_btn'] = tk.Button(btn_frame, text="Export", command=self.export_log, width=12,
                                                 bg=theme.get("accent"), fg="white")
        self._widgets['export_btn'].pack(side="left", padx=5)

        # Progress
        progress_frame = tk.Frame(self.master, bg=theme.get("bg_primary"))
        progress_frame.pack(fill="x", padx=20, pady=5)
        self._widgets['progress_label'] = tk.Label(progress_frame, text=i18n("progress_ready"), font=("Arial", 9),
                                                   bg=theme.get("bg_primary"), fg=theme.get("text_primary"))
        self._widgets['progress_label'].pack(anchor="w")
        self.progress_label = self._widgets['progress_label']

        self._widgets['progress_bar'] = Progressbar(progress_frame, mode='determinate', length=800)
        self._widgets['progress_bar'].pack(fill="x", pady=2)
        self.progress_bar = self._widgets['progress_bar']

        # Log
        self._widgets['log_label'] = tk.Label(self.master, text=i18n("activity_log"), font=("Arial", 10, "bold"),
                                               bg=theme.get("bg_primary"), fg=theme.get("text_primary"))
        self._widgets['log_label'].pack(anchor="w", padx=20, pady=(5, 0))

        log_bg = theme.get("bg_canvas") if theme.name == "dark" else "#1e1e1e"
        log_fg = theme.get("log_info")
        self._widgets['preview_text'] = scrolledtext.ScrolledText(self.master, height=15, font=("Consolas", 10),
                                                                  bg=log_bg, fg=log_fg)
        self._widgets['preview_text'].pack(fill="both", expand=True, padx=20, pady=5)
        self.preview_text = self._widgets['preview_text']

        # Status
        self._widgets['status_label'] = tk.Label(self.master, text=i18n("status_ready"),
                                                   fg=theme.get("text_secondary"), anchor="w",
                                                   bg=theme.get("bg_primary"))
        self._widgets['status_label'].pack(fill="x", padx=20, pady=5)
        self.status_label = self._widgets['status_label']

        self._setup_log_tags()

        # Store button references for state management
        self.execute_btn = self._widgets['execute_btn']
        self.undo_btn = self._widgets['undo_btn']

    def _setup_log_tags(self):
        theme = self.theme_mgr.current_theme
        try:
            self.preview_text.tag_config("info", foreground=theme.get("log_info"))
            self.preview_text.tag_config("success", foreground=theme.get("log_success"), font=("Consolas", 10, "bold"))
            self.preview_text.tag_config("warn", foreground=theme.get("log_warning"))
            self.preview_text.tag_config("error", foreground=theme.get("log_error"), font=("Consolas", 10, "bold"))
        except Exception:
            pass

    def open_settings(self):
        SettingsDialog(self.master, self.i18n, self.theme_mgr, self)

    def apply_theme_update(self):
        self._apply_theme_to_window()
        for widget in self.master.winfo_children():
            try:
                widget.destroy()
            except Exception:
                pass
        self._widgets.clear()
        self.create_widgets()
        self.reset_progress()

    def log_safe(self, message: str, level: str = "INFO"):
        try:
            self.master.after(0, self.log, message, level)
        except Exception:
            print(f"{level}: {message}")

    def update_progress_safe(self, current: int, total: int, filename: str = ""):
        try:
            self.master.after(0, self.update_progress, current, total, filename)
        except Exception:
            pass

    def set_buttons_state(self, state="normal"):
        try:
            self._widgets['browse_btn'].config(state=state)
            self._widgets['preview_btn'].config(state=state)
            if self._widgets['execute_btn']['state'] != 'disabled':
                self._widgets['execute_btn'].config(state=state)
            if self._widgets['undo_btn']['state'] != 'disabled':
                self._widgets['undo_btn'].config(state=state)
            self._widgets['export_btn'].config(state=state)
        except Exception:
            pass

    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prefix = f"[{timestamp}] {level}: "
        tag = level.lower()
        try:
            self.preview_text.insert(tk.END, prefix + message + "\n", tag)
            self.preview_text.see(tk.END)
        except Exception:
            print(prefix + message)

    def export_log(self):
        if not self.source_path:
            messagebox.showwarning("No folder", "Please load a folder before exporting the log.")
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = self.source_path / f"audit_log_{ts}.txt"
        try:
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(self.preview_text.get(1.0, tk.END))
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
            self.source_var.set(str(self.source_path))
            self.grouper = FileGrouper(self.source_path)

            self.preview_text.delete(1.0, tk.END)
            self.reset_progress()

            undo_state = "normal" if self.grouper.log_path.exists() else "disabled"
            self._widgets['undo_btn'].config(state=undo_state)
            self._widgets['execute_btn'].config(state="disabled")

            self.log(f"Folder loaded: {self.source_path.name}", "INFO")
            self.status_label.config(text=f"Loaded: {self.source_path.name}", fg="green")
        except Exception as e:
            messagebox.showerror("Load Failed", str(e))

    def reset_progress(self):
        try:
            self.progress_bar['value'] = 0
            self.progress_label.config(text=self.i18n("progress_ready"))
        except Exception:
            pass

    def update_progress(self, current: int, total: int, filename: str = ""):
        if total > 0:
            percent = int((current / total) * 100)
            self.progress_bar['value'] = percent
            text = f"Progress: {current}/{total} ({percent}%)"
            if filename:
                display_name = filename if len(filename) < 40 else filename[:37] + "..."
                text += f" - {display_name}"
            self.progress_label.config(text=text)

    def get_custom_names(self) -> List[str]:
        text = self.custom_names_text.get(1.0, tk.END).strip()
        names = [line.strip() for line in text.splitlines() if line.strip()]
        invalid_chars = r'[\\/:\\*?"<>|]'
        for name in names:
            if re.search(invalid_chars, name):
                messagebox.showwarning("Invalid Name", f"Folder name '{name}' contains invalid characters")
                return []
        return names

    @staticmethod
    def _key_for_policy(code: str) -> str:
        """Return the i18n key for a conflict-policy internal code."""
        for c, key in CONFLICT_POLICIES:
            if c == code:
                return key
        return "conflict_skip"

    @staticmethod
    def _key_for_sort(code: str) -> str:
        """Return the i18n key for a sort-mode internal code."""
        for c, key in SORT_MODES:
            if c == code:
                return key
        return "sort_name"

    def _on_conflict_selected(self, _event) -> None:
        """Sync the stable conflict-policy code when the user picks a label."""
        display = self.conflict_policy_var.get()
        for code, key in CONFLICT_POLICIES:
            if self.i18n(key) == display:
                self._conflict_policy_code = code
                return
        self._conflict_policy_code = "Skip"

    def _on_sort_selected(self, _event) -> None:
        """Sync the stable sort-mode code when the user picks a label."""
        display = self.sort_mode_var.get()
        for code, key in SORT_MODES:
            if self.i18n(key) == display:
                self._sort_mode_code = code
                return
        self._sort_mode_code = "name"

    def _get_conflict_policy(self) -> str:
        """Return the stable internal conflict-policy code (language-independent)."""
        return self._conflict_policy_code

    def _get_sort_mode(self) -> str:
        """Return the stable internal sort-mode code (language-independent)."""
        return self._sort_mode_code

    def preview_groups(self):
        if not self.source_path or not self.grouper:
            messagebox.showerror("Error", "Please select a folder first!")
            return

        suffix = self.suffix_var.get().strip()
        use_numbering = self.numbering_var.get()
        custom_names = self.get_custom_names()
        case_sensitive = self.case_sensitive_var.get()

        if not suffix and not use_numbering:
            messagebox.showerror("Error", "Please enter a Default Suffix or enable Numbered Custom Mode!")
            return

        self.preview_text.delete(1.0, tk.END)
        self.log(self.i18n("info_preview_start"), "INFO")

        groups = self.grouper.preview_groups(self.filter_var.get(), suffix, use_numbering, custom_names, case_sensitive, self._get_sort_mode())

        total_files = sum(len(files) for files in groups.values())
        self.log(self.i18n("success_found", groups=len(groups), files=total_files), "SUCCESS")

        for folder_name, files in groups.items():
            self.log(f"\n→ Target Folder: {folder_name}  ({len(files)} files)", "INFO")
            for f in files[:6]:
                self.log(f"   └─ {f.name}", "INFO")
            if len(files) > 6:
                self.log(f"   ... and {len(files) - 6} more files", "WARN")

        self.log(self.i18n("info_preview_complete"), "INFO")
        self._widgets['execute_btn'].config(state="normal" if total_files > 0 else "disabled")

    def execute_move(self):
        if not self.source_path or not self.grouper:
            return

        suffix = self.suffix_var.get().strip()
        use_numbering = self.numbering_var.get()
        custom_names = self.get_custom_names()
        case_sensitive = self.case_sensitive_var.get()
        groups = self.grouper.preview_groups(self.filter_var.get(), suffix, use_numbering, custom_names, case_sensitive, self._get_sort_mode())
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
            filter_text = self.filter_var.get()
            suffix = self.suffix_var.get().strip()
            use_numbering = self.numbering_var.get()
            custom_names = self.get_custom_names()
            case_sensitive = self.case_sensitive_var.get()
            conflict_policy = self._get_conflict_policy()
            sort_mode = self._get_sort_mode()

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

        self.status_label.config(text=f"Move completed (Moved {moved}, Renamed {renamed})", fg="green")
        self._widgets['undo_btn'].config(state="normal")
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

        self.status_label.config(text=f"Undo completed ({undone} files restored)", fg="green")

        self.set_buttons_state("normal")
        self._widgets['undo_btn'].config(state="normal" if remaining_logs > 0 else "disabled")
        self.reset_progress()
        messagebox.showinfo("Undo Success", f"Successfully restored {undone} files.\nCleaned up residual empty folders.")


def main() -> None:
    """Entry point for the application (used by pyproject.toml [project.scripts])."""
    if not HAS_DND:
        print("Warning: tkinterdnd2 not available; drag-and-drop disabled. Install with: pip install tkinterdnd2")
    root = TkinterDnD.Tk() if HAS_DND else tk.Tk()
    FileGrouperApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
