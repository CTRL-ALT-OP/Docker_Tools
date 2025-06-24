"""
GUI utilities for common operations
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
from typing import Callable, Optional, Dict, Any

from config.settings import COLORS, FONTS, BUTTON_STYLES


class GuiUtils:
    """Utility class for common GUI operations"""

    @staticmethod
    def create_styled_button(
        parent, text: str, command: Callable, style: str = "close", **kwargs
    ) -> tk.Button:
        """Create a button with predefined styling"""
        button_style = BUTTON_STYLES.get(style, BUTTON_STYLES["close"])

        default_config = {
            "text": text,
            "command": command,
            "font": FONTS["button"],
            "relief": "flat",
            "padx": 10,
            "pady": 4,
            **button_style,
        } | kwargs
        return tk.Button(parent, **default_config)

    @staticmethod
    def create_styled_label(
        parent, text: str, font_key: str = "info", color_key: str = "muted", **kwargs
    ) -> tk.Label:
        """Create a label with predefined styling"""
        default_config = {
            "text": text,
            "font": FONTS[font_key],
            "bg": COLORS["background"],
            "fg": COLORS[color_key],
        } | kwargs
        return tk.Label(parent, **default_config)

    @staticmethod
    def create_styled_frame(parent, bg_color: str = "background", **kwargs) -> tk.Frame:
        """Create a frame with predefined styling"""
        default_config = {"bg": COLORS[bg_color]} | kwargs
        return tk.Frame(parent, **default_config)

    @staticmethod
    def center_window(window, width: int, height: int):
        """Center a window on screen"""
        window.update_idletasks()
        x = (window.winfo_screenwidth() // 2) - (width // 2)
        y = (window.winfo_screenheight() // 2) - (height // 2)
        window.geometry(f"{width}x{height}+{x}+{y}")

    @staticmethod
    def create_scrollable_frame(parent) -> tuple[tk.Canvas, tk.Frame, ttk.Scrollbar]:
        """Create a scrollable frame setup"""
        # Canvas and scrollbar for scrolling
        canvas = tk.Canvas(parent, bg=COLORS["background"])
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = GuiUtils.create_styled_frame(canvas)

        scrollable_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Bind mousewheel to canvas
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        return canvas, scrollable_frame, scrollbar

    @staticmethod
    def create_console_text_area(parent) -> scrolledtext.ScrolledText:
        """Create a console-style text area"""
        return scrolledtext.ScrolledText(
            parent,
            font=FONTS["console"],
            bg=COLORS["terminal_input_bg"],
            fg=COLORS["terminal_text"],
            insertbackground="white",
            wrap=tk.WORD,
            state=tk.NORMAL,
        )
