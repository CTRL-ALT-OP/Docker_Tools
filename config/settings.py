"""
Configuration settings for the Project Control Panel
"""

import contextlib
import os

# Directories to ignore during cleanup operations
IGNORE_DIRS = [
    "__pycache__",
    ".pytest_cache",
    "pytest",
    ".dist",
    "dist",
    ".trunk",
    ".benchmarks",
    "benchmarks",
    ".vscode",
    "vscode",
    ".venv",
    "venv",
    "htmlcov",
]

IGNORE_FILES = [".coverage"]

# Global dictionary for folder aliases
FOLDER_ALIASES = {
    "preedit": ["pre-edit", "original"],
    "postedit-beetle": ["post-edit", "da", "da_edit", "beetle", "beetle_edit"],
    "postedit-sonnet": ["post-edit2", "sonnet", "sonnet_edit"],
    "rewrite": ["correct-edit", "rewrite", "correct", "correct_edit"],
}

# CHANGE THIS TO THE ABSOLUTE PATH OF THE SOURCE DIRECTORY
SOURCE_DIR = os.path.join(os.getcwd(), "Example_source_dir")


# Language detection configuration for Docker files service
LANGUAGE_EXTENSIONS = {
    "python": [".py", ".pyw", ".pyi", ".pyx", ".pyd", ".pywz", ".pyz"],
    "javascript": [".js", ".jsx", ".mjs", ".cjs"],
    "typescript": [".ts", ".tsx", ".cts", ".mts"],
    "java": [".java", ".class"],
    "rust": [".rs"],
    "c": [".c", ".h", ".i", ".o", ".s", ".so"],
    "go": [".go"],
    "cpp": [".cpp", ".cxx", ".cc", ".c++", ".hpp", ".hxx", ".hh", ".h++"],
    "csharp": [".cs", ".csx"],
}

# Required files for each language
LANGUAGE_REQUIRED_FILES = {
    "python": ["requirements.txt"],
    "javascript": ["package.json", "package-lock.json"],
    "typescript": ["package.json", "package-lock.json"],
    "java": ["pom.xml"],
    "rust": [],
    "c": ["CMakeLists.txt"],
    "go": ["go.mod"],
    "cpp": ["CMakeLists.txt"],
    "csharp": [],
}

# GUI Configuration
WINDOW_TITLE = "Project Control Panel"
MAIN_WINDOW_SIZE = "800x650"
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
    "text": "#2c3e50",
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
    "file_manager": {"bg": "#2ecc71", "fg": "white"},
    "refresh": {"bg": "#27ae60", "fg": "white"},
    "sync": {"bg": "#16a085", "fg": "white"},
    "edit": {"bg": "#e67e22", "fg": "white"},
    "validate": {"bg": "#8e44ad", "fg": "white"},
    "build_docker": {"bg": "#2980b9", "fg": "white"},
    "close": {"bg": "#34495e", "fg": "white"},
    "copy": {"bg": "#34495e", "fg": "white"},
    "save": {"bg": "#27ae60", "fg": "white"},
    "cancel": {"bg": "#e74c3c", "fg": "white"},
    "secondary": {"bg": "#95a5a6", "fg": "white"},
    "info": {"bg": "#3498db", "fg": "white"},
}


# Dynamic Settings Override System
# Load user customizations from user_settings.json if it exists
import json
from pathlib import Path


def _apply_user_settings():
    """Apply user settings overrides from user_settings.json"""
    user_settings_file = Path(__file__).parent / "user_settings.json"

    if not user_settings_file.exists():
        return

    with contextlib.suppress(json.JSONDecodeError, FileNotFoundError, KeyError):
        with open(user_settings_file, "r", encoding="utf-8") as f:
            user_settings = json.load(f)

        # Get the current module's globals to modify settings
        current_globals = globals()

        for key, value in user_settings.items():
            if key.startswith("COLORS."):
                # Handle color overrides
                color_key = key.split(".", 1)[1]
                if (
                    "COLORS" in current_globals
                    and color_key in current_globals["COLORS"]
                ):
                    current_globals["COLORS"][color_key] = value
            elif key.startswith("FONTS."):
                # Handle font overrides
                font_key = key.split(".", 1)[1]
                if "FONTS" in current_globals and font_key in current_globals["FONTS"]:
                    # Convert back to tuple if needed
                    if isinstance(value, list):
                        value = tuple(value)
                    current_globals["FONTS"][font_key] = value
            elif key.startswith("BUTTON_STYLES."):
                # Handle button style overrides
                style_key = key.split(".", 1)[1]
                if (
                    "BUTTON_STYLES" in current_globals
                    and style_key in current_globals["BUTTON_STYLES"]
                ):
                    current_globals["BUTTON_STYLES"][style_key] = value
            elif key in current_globals:
                # Handle direct setting overrides
                current_globals[key] = value


# Apply user settings overrides
_apply_user_settings()
