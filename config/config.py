"""
Unified Configuration Management System
Centralizes all application settings with validation, type checking, and environment support
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union, List, Type
from dataclasses import dataclass, field, fields
from enum import Enum
import contextlib


class Environment(Enum):
    """Application environments"""

    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"


class ConfigValidationError(Exception):
    """Raised when configuration validation fails"""

    pass


@dataclass
class GuiConfig:
    """GUI-related configuration"""

    # Window settings
    window_title: str = "Project Control Panel"
    main_window_size: str = "800x650"
    output_window_size: str = "800x600"
    git_window_size: str = "900x500"

    # Colors
    colors: Dict[str, str] = field(
        default_factory=lambda: {
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
    )

    # Fonts
    fonts: Dict[str, tuple] = field(
        default_factory=lambda: {
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
    )

    # Button styles
    button_styles: Dict[str, Dict[str, str]] = field(
        default_factory=lambda: {
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
    )


@dataclass
class ProjectConfig:
    """Project-related configuration"""

    # Source directory
    source_dir: str = field(
        default_factory=lambda: os.path.join(os.getcwd(), "Example_source_dir")
    )

    # Cleanup settings
    ignore_dirs: List[str] = field(
        default_factory=lambda: [
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
    )

    ignore_files: List[str] = field(default_factory=lambda: [".coverage"])

    # Folder aliases for project types
    folder_aliases: Dict[str, List[str]] = field(
        default_factory=lambda: {
            "preedit": ["pre-edit", "original"],
            "postedit-beetle": ["post-edit", "da", "da_edit", "beetle", "beetle_edit"],
            "postedit-sonnet": ["post-edit2", "sonnet", "sonnet_edit"],
            "rewrite": ["correct-edit", "rewrite", "correct", "correct_edit"],
        }
    )


@dataclass
class LanguageConfig:
    """Programming language detection and configuration"""

    # File extensions for language detection
    extensions: Dict[str, List[str]] = field(
        default_factory=lambda: {
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
    )

    # Required files for each language
    required_files: Dict[str, List[str]] = field(
        default_factory=lambda: {
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
    )

    # Language aliases
    aliases: Dict[str, str] = field(
        default_factory=lambda: {
            "js": "javascript",
            "ts": "typescript",
            "py": "python",
            "rs": "rust",
            "cs": "csharp",
            "c++": "cpp",
            "cxx": "cpp",
        }
    )


@dataclass
class CommandConfig:
    """System commands configuration"""

    # Platform-specific commands organized by category
    commands: Dict[str, Dict] = field(
        default_factory=lambda: {
            # File operations
            "FILE_OPEN_COMMANDS": {
                "windows": ["start", "{file_path}"],
                "darwin": ["open", "{file_path}"],
                "linux": ["xdg-open", "{file_path}"],
            },
            # Archive operations
            "ARCHIVE_COMMANDS": {
                "create": {
                    "windows": [
                        "powershell",
                        "-Command",
                        "Compress-Archive -Path ./* -DestinationPath ./{archive_name} -Force",
                    ],
                    "linux": [
                        "zip",
                        "-r",
                        "{archive_name}",
                        ".",
                        "-x",
                        "{archive_name}",
                    ],
                    "darwin": [
                        "zip",
                        "-r",
                        "{archive_name}",
                        ".",
                        "-x",
                        "{archive_name}",
                    ],
                },
            },
            # Docker commands
            "DOCKER_COMMANDS": {
                "build_script": "./build_docker.sh {tag}",
                "run_tests": "docker run --rm {tag} ./run_tests.sh",
                "version": ["docker", "--version"],
                "info": ["docker", "info"],
                "images": ["docker", "images", "-q", "{image_name}"],
                "run": ["docker", "run", "--rm", "{image_name}"],
                "rmi": ["docker", "rmi", "{image_name}"],
                "compose_up": ["docker", "compose", "up", "--build"],
            },
            # Git commands
            "GIT_COMMANDS": {
                "version": ["git", "--version"],
                "init": ["git", "init", "--quiet"],
                "rev_parse_git_dir": ["git", "rev-parse", "--git-dir"],
                "rev_parse_head": ["git", "rev-parse", "HEAD"],
                "branch_show_current": ["git", "branch", "--show-current"],
                "status_porcelain": ["git", "status", "--porcelain"],
                "remote_check": ["git", "remote"],
                "log": [
                    "git",
                    "log",
                    "--oneline",
                    "--pretty=format:%h|%P|%an|%ad|%s",
                    "--date=short",
                    "--all",
                ],
                "checkout": ["git", "checkout", "{commit}"],
                "force_checkout": ["git", "checkout", "--force", "{commit}"],
                "fetch": ["git", "fetch", "--all"],
                "clone": ["git", "clone", "{repo_url}", "{project_name}"],
            },
            # Test commands
            "TEST_COMMANDS": {
                "pytest": ["python", "-m", "pytest"],
                "pytest_verbose": ["python", "-m", "pytest", "-v"],
                "pytest_with_coverage": ["python", "-m", "pytest", "--cov"],
            },
            # System commands
            "SYSTEM_COMMANDS": {
                "pwd": {"windows": ["cd"], "unix": ["pwd"]},
            },
            # Shell commands
            "SHELL_COMMANDS": {
                "bash": "bash",
                "powershell": "powershell",
                "bash_execute": ["bash", "-c", "{command}"],
                "powershell_execute": ["powershell", "-Command", "{command}"],
            },
            # File system commands
            "FILE_SYSTEM_COMMANDS": {
                "list_dir": {
                    "windows": ["dir", "/b", "{dir_path}"],
                    "linux": ["ls", "-1", "{dir_path}"],
                    "darwin": ["ls", "-1", "{dir_path}"],
                },
                "check_file_exists": {
                    "windows": ["if", "exist", "{file_path}", "echo", "exists"],
                    "linux": ["test", "-f", "{file_path}"],
                    "darwin": ["test", "-f", "{file_path}"],
                },
                "copy_file": {
                    "windows": ["copy", "{source_path}", "{target_path}"],
                    "linux": ["cp", "{source_path}", "{target_path}"],
                    "darwin": ["cp", "{source_path}", "{target_path}"],
                },
                "create_dir": {
                    "windows": ["mkdir", "{dir_path}"],
                    "linux": ["mkdir", "-p", "{dir_path}"],
                    "darwin": ["mkdir", "-p", "{dir_path}"],
                },
            },
        }
    )

    # Platform-specific executable paths
    bash_paths: Dict[str, List[str]] = field(
        default_factory=lambda: {
            "windows": [
                r"C:\Program Files\Git\bin\bash.exe",
                r"C:\Program Files (x86)\Git\bin\bash.exe",
                r"C:\Git\bin\bash.exe",
            ],
        }
    )

    # Error messages by platform
    error_messages: Dict[str, Dict[str, str]] = field(
        default_factory=lambda: {
            "windows": {
                "bash_not_found": "NOTE: Make sure Git for Windows is installed and accessible.",
                "powershell_failed": "NOTE: PowerShell command failed.",
            },
            "linux": {
                "bash_not_found": "NOTE: Make sure bash is available in your PATH.",
                "zip_not_found": "NOTE: Make sure zip is installed.",
            },
            "darwin": {
                "bash_not_found": "NOTE: Make sure bash is available in your PATH.",
                "zip_not_found": "NOTE: Make sure zip is installed.",
            },
        }
    )


@dataclass
class TestConfig:
    """Testing configuration"""

    # Test command templates
    command_templates: Dict[str, str] = field(
        default_factory=lambda: {
            "python": "pytest -vv -s {test_paths}",
            "javascript": "npm test {test_paths}",
            "typescript": "npm run build && npm test {test_paths}",
            "java": "mvn test -Dtest={test_paths}",
            "rust": "cargo test {test_paths}",
            "c": "ctest --verbose -R {test_paths}",
            "cpp": "ctest --verbose -R {test_paths}",
            "csharp": "dotnet test {test_paths}",
            "go": "go test {test_paths}",
        }
    )

    # Default commands when no paths specified
    default_commands: Dict[str, str] = field(
        default_factory=lambda: {
            "python": "pytest -vv -s tests/",
            "javascript": "npm test",
            "typescript": "npm run build && npm test",
            "java": "mvn test",
            "rust": "cargo test",
            "c": "ctest --verbose",
            "cpp": "ctest --verbose",
            "csharp": "dotnet test",
            "go": "go test",
        }
    )

    # Test file patterns
    file_patterns: Dict[str, List[str]] = field(
        default_factory=lambda: {
            "python": ["test_*.py", "*_test.py"],
            "javascript": ["*.test.js", "*.spec.js"],
            "typescript": ["*.test.ts", "*.spec.ts", "*.test.tsx", "*.spec.tsx"],
            "java": ["*Test.java", "*Tests.java"],
            "rust": ["*_test.rs", "test_*.rs"],
            "c": ["test_*.c", "*_test.c", "test_*.cpp", "*_test.cpp"],
            "cpp": ["test_*.c", "*_test.c", "test_*.cpp", "*_test.cpp"],
            "csharp": ["*Test.cs", "*Tests.cs"],
            "go": ["*_test.go"],
        }
    )

    # Test directories
    directories: Dict[str, List[str]] = field(
        default_factory=lambda: {
            "python": ["tests/"],
            "javascript": ["tests/", "test/", "__tests__/", "src/"],
            "typescript": ["tests/", "test/", "__tests__/", "src/"],
            "java": ["src/test/java/", "test/"],
            "rust": ["tests/", "src/"],
            "c": ["tests/", "test/"],
            "cpp": ["tests/", "test/"],
            "csharp": ["tests/", "test/"],
            "go": ["./"],
        }
    )


@dataclass
class ServiceConfig:
    """Service-specific configuration"""

    # Timeout settings
    default_timeout: float = 30.0
    docker_timeout: float = 300.0
    git_timeout: float = 60.0
    validation_timeout: float = 1800.0  # 30 minutes

    # Retry settings
    default_retry_count: int = 3
    network_retry_count: int = 5

    # Async settings
    max_concurrent_operations: int = 5
    task_queue_size: int = 100

    # Validation settings
    validation_url: str = "http://localhost:8080"
    max_parallel_archives: int = 3
    auto_cleanup: bool = True


@dataclass
class UnifiedConfig:
    """Main configuration container"""

    # Sub-configurations
    gui: GuiConfig = field(default_factory=GuiConfig)
    project: ProjectConfig = field(default_factory=ProjectConfig)
    language: LanguageConfig = field(default_factory=LanguageConfig)
    commands: CommandConfig = field(default_factory=CommandConfig)
    test: TestConfig = field(default_factory=TestConfig)
    service: ServiceConfig = field(default_factory=ServiceConfig)

    # Environment settings
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = True
    log_level: str = "INFO"

    # Application metadata
    version: str = "1.0.0"
    config_version: str = "1.0"


class ConfigManager:
    """Manages configuration loading, validation, and access"""

    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path(__file__).parent
        self.config: Optional[UnifiedConfig] = None
        self.logger = logging.getLogger("ConfigManager")

        # Load configuration
        self._load_config()

    def _load_config(self):
        """Load configuration from files and environment"""
        # Start with default configuration
        self.config = UnifiedConfig()

        # Apply user overrides
        self._apply_user_overrides()

        # Apply environment overrides
        self._apply_environment_overrides()

        # Validate configuration
        self._validate_config()

    def _apply_user_overrides(self):
        """Apply user settings from user_settings.json"""
        user_settings_file = self.config_dir / "user_settings.json"

        if not user_settings_file.exists():
            return

        try:
            with open(user_settings_file, "r", encoding="utf-8") as f:
                user_settings = json.load(f)

            self._apply_settings_dict(user_settings)
            self.logger.info("Applied user settings overrides")

        except (json.JSONDecodeError, FileNotFoundError) as e:
            self.logger.warning(f"Could not load user settings: {e}")

    def _apply_environment_overrides(self):
        """Apply environment-specific overrides"""
        # Environment from environment variable
        env_name = os.getenv("PROJECT_ENV", "development").lower()
        try:
            self.config.environment = Environment(env_name)
        except ValueError:
            self.logger.warning(f"Unknown environment '{env_name}', using development")
            self.config.environment = Environment.DEVELOPMENT

        # Debug mode
        if os.getenv("DEBUG") is not None:
            self.config.debug = os.getenv("DEBUG").lower() in ("true", "1", "yes", "on")

        # Log level
        if os.getenv("LOG_LEVEL"):
            self.config.log_level = os.getenv("LOG_LEVEL").upper()

        # Source directory
        if os.getenv("SOURCE_DIR"):
            self.config.project.source_dir = os.getenv("SOURCE_DIR")

        # Validation URL
        if os.getenv("VALIDATION_URL"):
            self.config.service.validation_url = os.getenv("VALIDATION_URL")

    def _apply_settings_dict(self, settings: Dict[str, Any]):
        """Apply settings from a dictionary using dot notation"""
        for key, value in settings.items():
            self._set_nested_value(self.config, key, value)

    def _set_nested_value(self, obj: Any, key_path: str, value: Any):
        """Set a nested value using dot notation (e.g., 'gui.colors.success')"""
        keys = key_path.split(".")
        current = obj

        # Navigate to the parent object
        for key in keys[:-1]:
            if isinstance(current, dict):
                if key in current:
                    current = current[key]
                else:
                    self.logger.warning(
                        f"Unknown config path: {'.'.join(keys[:keys.index(key)+1])}"
                    )
                    return
            elif hasattr(current, key):
                current = getattr(current, key)
            else:
                self.logger.warning(
                    f"Unknown config path: {'.'.join(keys[:keys.index(key)+1])}"
                )
                return

        # Set the final value
        final_key = keys[-1]

        if isinstance(current, dict):
            # Handle dictionary assignment
            if final_key in current:
                # Handle special cases for complex types
                if isinstance(current[final_key], dict) and isinstance(value, dict):
                    # Merge dictionaries
                    current[final_key].update(value)
                elif isinstance(current[final_key], tuple) and isinstance(value, list):
                    # Convert list to tuple for font settings
                    current[final_key] = tuple(value)
                else:
                    current[final_key] = value
            else:
                self.logger.warning(f"Unknown config key: {key_path}")
        elif hasattr(current, final_key):
            # Handle object attribute assignment
            if isinstance(getattr(current, final_key), dict) and isinstance(
                value, dict
            ):
                # Merge dictionaries
                current_dict = getattr(current, final_key)
                current_dict.update(value)
            elif isinstance(getattr(current, final_key), tuple) and isinstance(
                value, list
            ):
                # Convert list to tuple for font settings
                setattr(current, final_key, tuple(value))
            else:
                setattr(current, final_key, value)
        else:
            self.logger.warning(f"Unknown config key: {key_path}")

    def _validate_config(self):
        """Validate the loaded configuration"""
        try:
            # Validate paths exist
            if not Path(self.config.project.source_dir).exists():
                self.logger.warning(
                    f"Source directory does not exist: {self.config.project.source_dir}"
                )

            # Validate color format (basic check)
            for name, color in self.config.gui.colors.items():
                if not (color.startswith("#") or color in ["white", "black"]):
                    self.logger.warning(f"Invalid color format for {name}: {color}")

            # Validate timeouts are positive
            if self.config.service.default_timeout <= 0:
                raise ConfigValidationError("Default timeout must be positive")

            self.logger.info("Configuration validation completed")

        except Exception as e:
            self.logger.error(f"Configuration validation failed: {e}")
            raise ConfigValidationError(f"Invalid configuration: {e}")

    def get_config(self) -> UnifiedConfig:
        """Get the current configuration"""
        if self.config is None:
            raise RuntimeError("Configuration not loaded")
        return self.config

    def reload_config(self):
        """Reload configuration from files"""
        self._load_config()

    def save_user_settings(self, settings: Dict[str, Any]):
        """Save user settings to user_settings.json"""
        user_settings_file = self.config_dir / "user_settings.json"

        try:
            with open(user_settings_file, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2)

            # Reload configuration
            self.reload_config()
            self.logger.info("User settings saved and configuration reloaded")

        except Exception as e:
            self.logger.error(f"Failed to save user settings: {e}")
            raise


# Global configuration manager instance
_config_manager: Optional[ConfigManager] = None


def initialize_config(config_dir: Optional[Path] = None) -> ConfigManager:
    """Initialize the global configuration manager"""
    global _config_manager
    _config_manager = ConfigManager(config_dir)
    return _config_manager


def get_config() -> UnifiedConfig:
    """Get the current configuration"""
    if _config_manager is None:
        # Auto-initialize with default settings
        initialize_config()
    return _config_manager.get_config()


def get_config_manager() -> ConfigManager:
    """Get the configuration manager"""
    if _config_manager is None:
        initialize_config()
    return _config_manager


def reload_config():
    """Reload configuration from files"""
    if _config_manager is not None:
        _config_manager.reload_config()


# Convenience functions for common access patterns
def get_gui_config() -> GuiConfig:
    """Get GUI configuration"""
    return get_config().gui


def get_project_config() -> ProjectConfig:
    """Get project configuration"""
    return get_config().project


def get_command_config() -> CommandConfig:
    """Get command configuration"""
    return get_config().commands


def get_service_config() -> ServiceConfig:
    """Get service configuration"""
    return get_config().service
