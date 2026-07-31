"""Theme configuration for prefix-file-sort."""

from typing import Dict, Any
import tkinter as tk


class Theme:
    """Theme configuration holder."""

    def __init__(self, name: str, colors: Dict[str, str]):
        self.name = name
        self.colors = colors

    def get(self, key: str, default: str = "") -> str:
        """Get a color value by key."""
        return self.colors.get(key, default)


# Light theme colors
LIGHT_THEME = Theme("light", {
    # Backgrounds
    "bg_primary": "#FFFFFF",
    "bg_secondary": "#F5F5F5",
    "bg_tertiary": "#E8E8E8",
    "bg_canvas": "#FAFAFA",

    # Text
    "text_primary": "#1A1A1A",
    "text_secondary": "#666666",
    "text_disabled": "#AAAAAA",
    "text_link": "#0066CC",

    # Accent colors
    "accent": "#0078D4",
    "accent_hover": "#106EBE",
    "accent_active": "#005A9E",

    # Buttons
    "btn_primary_bg": "#0078D4",
    "btn_primary_fg": "#FFFFFF",
    "btn_secondary_bg": "#F0F0F0",
    "btn_secondary_fg": "#333333",
    "btn_hover": "#E8E8E8",

    # Borders
    "border": "#CCCCCC",
    "border_focus": "#0078D4",

    # Status colors
    "success": "#28A745",
    "warning": "#FFC107",
    "error": "#DC3545",
    "info": "#17A2B8",

    # Log colors
    "log_info": "#333333",
    "log_success": "#28A745",
    "log_warning": "#FF9800",
    "log_error": "#DC3545",

    # Entry/Text
    "entry_bg": "#FFFFFF",
    "entry_fg": "#1A1A1A",
    "entry_insert": "#333333",

    # Scrollbar
    "scrollbar_bg": "#E0E0E0",
    "scrollbar_thumb": "#BDBDBD",

    # Progressbar
    "progressbar_bg": "#E8E8E8",
    "progressbar_fill": "#0078D4",

    # Combobox
    "combobox_bg": "#FFFFFF",
    "combobox_fg": "#1A1A1A",
})


# Dark theme colors
DARK_THEME = Theme("dark", {
    # Backgrounds
    "bg_primary": "#1E1E1E",
    "bg_secondary": "#252526",
    "bg_tertiary": "#2D2D2D",
    "bg_canvas": "#181818",

    # Text
    "text_primary": "#E0E0E0",
    "text_secondary": "#A0A0A0",
    "text_disabled": "#606060",
    "text_link": "#4DA3FF",

    # Accent colors
    "accent": "#0E639C",
    "accent_hover": "#1177BB",
    "accent_active": "#0D5A8C",

    # Buttons
    "btn_primary_bg": "#0E639C",
    "btn_primary_fg": "#FFFFFF",
    "btn_secondary_bg": "#3C3C3C",
    "btn_secondary_fg": "#E0E0E0",
    "btn_hover": "#404040",

    # Borders
    "border": "#3C3C3C",
    "border_focus": "#0E639C",

    # Status colors
    "success": "#4CAF50",
    "warning": "#FFB300",
    "error": "#EF5350",
    "info": "#29B6F6",

    # Log colors
    "log_info": "#CCCCCC",
    "log_success": "#4CAF50",
    "log_warning": "#FFB300",
    "log_error": "#EF5350",

    # Entry/Text
    "entry_bg": "#2D2D2D",
    "entry_fg": "#E0E0E0",
    "entry_insert": "#CCCCCC",

    # Scrollbar
    "scrollbar_bg": "#2D2D2D",
    "scrollbar_thumb": "#424242",

    # Progressbar
    "progressbar_bg": "#3C3C3C",
    "progressbar_fill": "#0E639C",

    # Combobox
    "combobox_bg": "#2D2D2D",
    "combobox_fg": "#E0E0E0",
})


# Available themes
THEMES = {
    "light": LIGHT_THEME,
    "dark": DARK_THEME,
}


class ThemeManager:
    """Manages application themes."""

    def __init__(self, theme_name: str = "light"):
        self._current_theme = THEMES.get(theme_name, LIGHT_THEME)

    @property
    def current_theme(self) -> Theme:
        return self._current_theme

    @property
    def theme_name(self) -> str:
        return self._current_theme.name

    def set_theme(self, theme_name: str) -> bool:
        """Set the current theme by name."""
        if theme_name in THEMES:
            self._current_theme = THEMES[theme_name]
            return True
        return False

    def get_color(self, key: str, default: str = "") -> str:
        """Get a color from the current theme."""
        return self._current_theme.get(key, default)

    def apply_to_widget(self, widget: tk.Widget) -> None:
        """Apply theme colors to a widget and its children."""
        theme = self._current_theme

        widget_class = widget.winfo_class()

        try:
            if widget_class in ("Frame", "Labelframe"):
                widget.config(bg=theme.get("bg_secondary"))
            elif widget_class == "Label":
                widget.config(
                    bg=widget.cget("bg") if widget.cget("bg") != "systemWindowBody" else theme.get("bg_primary"),
                    fg=theme.get("text_primary")
                )
            elif widget_class == "Button":
                widget.config(
                    bg=theme.get("btn_secondary_bg"),
                    fg=theme.get("btn_secondary_fg"),
                    activebackground=theme.get("btn_hover"),
                    relief="flat"
                )
            elif widget_class in ("Entry", "Text"):
                widget.config(
                    bg=theme.get("entry_bg"),
                    fg=theme.get("entry_fg"),
                    insertbackground=theme.get("entry_insert"),
                    relief="solid",
                    bd=1
                )
            elif widget_class == "Checkbutton":
                widget.config(
                    bg=widget.cget("bg") if widget.cget("bg") != "systemWindowBody" else theme.get("bg_primary"),
                    fg=theme.get("text_primary"),
                    selectcolor=theme.get("entry_bg")
                )
        except tk.TclError:
            pass  # Widget doesn't support this option


# Global theme manager
_theme_manager = ThemeManager()


def get_theme_manager() -> ThemeManager:
    """Get the global theme manager instance."""
    return _theme_manager


def set_theme(theme_name: str) -> bool:
    """Set the global theme."""
    return _theme_manager.set_theme(theme_name)


def get_current_theme_name() -> str:
    """Get the current theme name."""
    return _theme_manager.theme_name
