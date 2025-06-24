"""
Configuration settings for the Project Control Panel
"""

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

IGNORE_FILES = [
    ".coverage",
]

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
}

# Required files for each language
LANGUAGE_REQUIRED_FILES = {
    "python": ["requirements.txt"],
    "javascript": ["package.json", "package-lock.json"],
    "typescript": ["package.json", "package-lock.json"],
    "java": ["pom.xml"],
    "rust": [],  # No files need ensuring for Rust
}

# GUI Configuration
WINDOW_TITLE = "Project Control Panel"
MAIN_WINDOW_SIZE = "750x650"
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
    "sync": {"bg": "#16a085", "fg": "white"},
    "validate": {"bg": "#8e44ad", "fg": "white"},
    "build_docker": {"bg": "#2980b9", "fg": "white"},
    "close": {"bg": "#34495e", "fg": "white"},
    "copy": {"bg": "#34495e", "fg": "white"},
}
