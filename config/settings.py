"""
Configuration settings for the Project Control Panel
"""

# Directories to ignore during cleanup operations
IGNORE_DIRS = [
    "__pycache__",
    ".pytest_cache",
    "pytest",
    ".dist",
    "dist",
    ".trunk",
]

# Global dictionary for folder aliases
FOLDER_ALIASES = {
    "preedit": ["pre-edit", "original"],
    "da_postedit": ["post-edit", "da", "da_edit"],
    "sonnet_postedit": ["post-edit2", "sonnet", "sonnet_edit"],
    "rewrite": ["correct-edit", "rewrite", "correct", "correct_edit"],
}

SOURCE_DIR = "D:\\General_Dockerized"

# GUI Configuration
WINDOW_TITLE = "Project Control Panel"
MAIN_WINDOW_SIZE = "800x600"
OUTPUT_WINDOW_SIZE = "800x600"
GIT_WINDOW_SIZE = "900x500"

# GUI Colors
COLORS = {
    "background": "#f0f0f0",
    "terminal_bg": "#2c3e50",
    "terminal_text": "#ffffff",
    "terminal_input_bg": "#1e1e1e",
    "success": "#27ae60",
    "error": "#e74c3c",
    "warning": "#f39c12",
    "info": "#3498db",
    "secondary": "#34495e",
    "muted": "#7f8c8d",
    "white": "white",
    "project_header": "#2c3e50",
}

# GUI Fonts
FONTS = {
    "title": ("Arial", 16, "bold"),
    "header": ("Arial", 14, "bold"),
    "project_name": ("Arial", 12, "bold"),
    "button": ("Arial", 9, "bold"),
    "button_large": ("Arial", 10, "bold"),
    "info": ("Arial", 9),
    "console": ("Consolas", 9),
    "console_title": ("Consolas", 12, "bold"),
    "console_status": ("Consolas", 10, "bold"),
    "mono": ("Consolas", 10),
}

# Button Styles
BUTTON_STYLES = {
    "cleanup": {"bg": "#e74c3c", "fg": "white"},
    "archive": {"bg": "#3498db", "fg": "white"},
    "docker": {"bg": "#9b59b6", "fg": "white"},
    "git": {"bg": "#f39c12", "fg": "white"},
    "refresh": {"bg": "#27ae60", "fg": "white"},
    "close": {"bg": "#34495e", "fg": "white"},
    "copy": {"bg": "#34495e", "fg": "white"},
}
