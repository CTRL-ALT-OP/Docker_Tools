"""
Refactored Project Control Panel - Main Application with Improved Async Architecture
"""

import os
import time
import asyncio
import tkinter as tk
import logging
import re
from tkinter import messagebox, ttk
from pathlib import Path
from typing import List, Dict, Any

from config.config import get_config

# Cache config values for efficiency
_config = get_config()
WINDOW_TITLE = _config.gui.window_title
MAIN_WINDOW_SIZE = _config.gui.main_window_size
COLORS = _config.gui.colors
FONTS = _config.gui.fonts
SOURCE_DIR = _config.project.source_dir

from services.project_service import ProjectService
from services.project_group_service import ProjectGroupService, ProjectGroup
from services.file_service import FileService
from services.git_service import GitService
from services.docker_service import DockerService
from services.sync_service import SyncService
from services.validation_service import ValidationService
from services.docker_files_service import DockerFilesService
from services.file_monitor_service import file_monitor
from gui import (
    MainWindow,
    AddProjectWindow,
)
from utils.async_utils import (
    task_manager,
    shutdown_all,
    TkinterAsyncBridge,
)
from models.project import Project
from services.web_integration_service import WebIntegration
from core.callback_handler import CallbackHandler
from core.operation_manager import OperationManager

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ProjectControlPanel:
    """Main Project Control Panel application with improved async architecture"""

    def __init__(self, root_dir: str = "."):
        self.root_dir = Path(root_dir).resolve()

        # Initialize services (all now async-capable)
        self.project_service = ProjectService(root_dir)
        self.project_group_service = ProjectGroupService(self.project_service)
        self.file_service = FileService()
        self.git_service = GitService()
        self.docker_service = DockerService()
        self.sync_service = SyncService()
        self.validation_service = ValidationService()
        self.docker_files_service = DockerFilesService()

        # Initialize GUI
        self.main_window = MainWindow(root_dir)
        self.window = self.main_window.window  # For backward compatibility

        # Initialize unified callback handler
        self.callback_handler = CallbackHandler(self.window, control_panel=self)

        # Initialize async bridge for GUI coordination
        self.async_bridge = TkinterAsyncBridge(self.window, task_manager)

        # Initialize operation manager with all services
        services = {
            "project_service": self.project_service,
            "file_service": self.file_service,
            "git_service": self.git_service,
            "docker_service": self.docker_service,
            "sync_service": self.sync_service,
            "validation_service": self.validation_service,
            "docker_files_service": self.docker_files_service,
            "async_bridge": self.async_bridge,
        }
        self.operation_manager = OperationManager(
            services=services,
            callback_handler=self.callback_handler,
            window=self.window,
            control_panel=self,
        )

        # Initialize web interface integration
        self.web_integration = WebIntegration(self)

        # Set up proper event loop for async operations
        self._setup_async_integration()

        # Set up GUI callbacks
        self._setup_gui_callbacks()

        # Set up synchronization callbacks
        self._setup_synchronization_callbacks()

        # Set up proper cleanup on window close
        self.main_window.setup_window_protocol(self._on_window_close)

        # Create GUI and load projects
        self.main_window.create_gui()
        self.load_projects()

        # Setup improved async event processing
        self._setup_async_processing()

        # Start web interface
        self._start_web_interface()

    def _setup_synchronization_callbacks(self):
        """Set up callbacks for synchronization between web and desktop interfaces"""

        def on_project_selection_change(group_name: str):
            """Handle project selection changes from any source"""
            # Update the desktop GUI dropdown to reflect changes
            self.window.after(0, lambda: self._update_desktop_dropdown(group_name))

        # Register callback with the project group service
        self.project_group_service.add_selection_callback(on_project_selection_change)

    def _update_desktop_dropdown(self, group_name: str):
        """Update the desktop GUI dropdown to reflect current selection"""
        try:
            # Get current group names
            group_names = self.project_group_service.get_group_names()
            current_group_name = self.project_group_service.get_current_group_name()

            # Update the dropdown
            self.main_window.update_project_selector(group_names, current_group_name)

            # Update the displayed content
            self.populate_current_project()

            logger.info(f"Desktop GUI updated to show project: {group_name}")

        except Exception as e:
            logger.error(f"Error updating desktop GUI dropdown: {e}")

    def _start_web_interface(self):
        """Start the web interface"""
        try:
            self.web_integration.start_web_server(port=5000, debug=False)
            logger.info("Web interface started successfully")
        except Exception as e:
            logger.error(f"Failed to start web interface: {e}")

    def _setup_async_integration(self):
        """Set up async integration with tkinter"""
        try:
            # Set up event loop for async operations
            task_manager.setup_event_loop()
            logger.info("Async integration setup complete")
        except Exception as e:
            logger.error("Failed to setup async integration: %s", e)
            # Continue without async support

    def _setup_gui_callbacks(self):
        """Set up GUI event callbacks"""
        callbacks = {
            "on_project_selected": self.on_project_selected,
            "refresh_projects": self.refresh_projects,
            "open_add_project_window": self.open_add_project_window,
            "open_settings_window": self.open_settings_window,
            "cleanup_project": self.cleanup_project,
            "archive_project": self.archive_project,
            "docker_build_and_test": self.docker_build_and_test,
            "git_view": self.git_view,
            "sync_run_tests_from_pre_edit": self.sync_run_tests_from_pre_edit,
            "edit_run_tests": self.edit_run_tests,
            "validate_project_group": self.validate_project_group,
            "build_docker_files_for_project_group": self.build_docker_files_for_project_group,
            "git_checkout_all": self.git_checkout_all,
        }
        self.main_window.set_callbacks(callbacks)

    def _setup_async_processing(self):
        """Setup improved async event processing with better timing"""

        def process_async_events():
            """Process async events and schedule next processing"""
            try:
                # Get task statistics for monitoring
                stats = task_manager.get_task_stats()

                # Log task statistics periodically (every 10 seconds)
                current_time = time.time()
                if not hasattr(self, "_last_stats_log"):
                    self._last_stats_log = current_time

                if current_time - self._last_stats_log > 10:
                    if stats["running"] > 0:
                        logger.debug(
                            "Async task stats - Running: %d, Total: %d",
                            stats["running"],
                            stats["total"],
                        )
                    self._last_stats_log = current_time

                # Warn if too many tasks are running
                if stats["running"] > 20:
                    logger.warning(
                        "High number of running async tasks: %d", stats["running"]
                    )

            except Exception as e:
                logger.exception("Error processing async events")
            finally:
                # Schedule next processing - using adaptive timing
                # More frequent processing when tasks are active
                interval = 25 if task_manager.get_task_count() > 0 else 100
                self.window.after(interval, process_async_events)

        # Start the processing loop
        process_async_events()

    def _on_window_close(self):
        """Handle window close event with proper cleanup"""
        logger.info("Application shutdown initiated")
        try:
            # Stop web server
            if hasattr(self, "web_integration"):
                self.web_integration.stop_web_server()
            # Stop file monitoring
            file_monitor.stop_all_monitoring()
            # Cancel any pending async operations with timeout
            shutdown_all(timeout=3.0)  # Shorter timeout for better UX
        except Exception as e:
            logger.exception("Error during shutdown cleanup")
        finally:
            # Destroy the window
            self.window.destroy()

    def load_projects(self):
        """Load and populate project groups"""
        self.project_group_service.load_project_groups()
        self.update_project_selector()
        self.populate_current_project()

    def update_project_selector(self):
        """Update the project selector dropdown with available projects"""
        group_names = self.project_group_service.get_group_names()
        current_group_name = self.project_group_service.get_current_group_name()

        # Update the main window's project selector
        self.main_window.update_project_selector(group_names, current_group_name)

        # Set default if no current group but groups exist
        if not current_group_name and group_names:
            self.project_group_service.set_current_group_by_name(group_names[0])

    def on_project_selected(self, event=None):
        """Handle project selection from dropdown"""
        selected_name = self.main_window.get_selected_project()
        if selected_name and self.project_group_service.set_current_group_by_name(
            selected_name
        ):
            self.populate_current_project()

    def populate_current_project(self):
        """Populate the GUI with the current project group"""
        # Clear existing content
        self.main_window.clear_content()

        current_group = self.project_group_service.get_current_group()

        if not current_group:
            self.main_window.show_no_projects_message()
            return

        # Create project header
        self.main_window.create_project_header(current_group)

        # Create project actions frame
        self.main_window.create_project_actions_frame(current_group)

        # Display all versions of the current project
        versions = current_group.get_all_versions()

        if not versions:
            self.main_window.show_no_versions_message()
            return

        # Group versions for better display
        for i, project in enumerate(versions):
            if i > 0:  # Add spacing between versions
                self.main_window.add_version_spacing()

            self.main_window.create_version_section(project, self.project_service)

    def cleanup_project(self, project: Project):
        """Execute project cleanup operation"""
        self.operation_manager.cleanup_project(project)

    def _update_status(self, message: str, level: str):
        """Standard progress callback for async operations"""
        color_map = {
            "info": COLORS["info"],
            "warning": COLORS["warning"],
            "success": COLORS["success"],
            "error": COLORS["error"],
        }
        color = color_map.get(level, COLORS["info"])

        # Update GUI status safely from any thread
        self.window.after(0, lambda: self._safe_status_update(message, color))

    def _safe_status_update(self, message: str, color: str):
        """Safely update status in GUI thread"""
        # This would update a status bar or label in the GUI
        # Only log significant status changes, not all progress messages
        if any(
            keyword in message.lower()
            for keyword in ["completed", "failed", "error", "started", "finished"]
        ):
            logger.info(f"Status: {message} ({color})")

    def archive_project(self, project: Project):
        """Execute project archive operation"""
        self.operation_manager.archive_project(project)

    def docker_build_and_test(self, project: Project):
        """Execute Docker build and test operation"""
        self.operation_manager.docker_build_and_test(project)

    def git_view(self, project: Project):
        """Execute git view operation"""
        self.operation_manager.git_view(project)

    def checkout_commit_callback(
        self, project_path, project_name, commit_hash, git_window
    ):
        """Handle commit checkout with proper async pattern"""
        self.operation_manager.checkout_commit_callback(
            project_path, project_name, commit_hash, git_window
        )

    def git_checkout_all(self, project_group: ProjectGroup):
        """Execute git checkout all operation"""
        self.operation_manager.git_checkout_all(project_group)

    def sync_run_tests_from_pre_edit(self, project_group: ProjectGroup):
        """Execute sync run tests operation"""
        self.operation_manager.sync_run_tests_from_pre_edit(project_group)

    def edit_run_tests(self, project_group: ProjectGroup):
        """Open the edit run_tests.sh window"""
        self.operation_manager.edit_run_tests(project_group)

    def validate_project_group(self, project_group: ProjectGroup):
        """Execute project group validation operation"""
        self.operation_manager.validate_project_group(project_group)

    def build_docker_files_for_project_group(self, project_group: ProjectGroup):
        """Execute Docker files build operation"""
        self.operation_manager.build_docker_files_for_project_group(project_group)

    def _extract_validation_id(self, raw_output: str) -> str:
        """
        Extract the validation ID from the validation output
        Returns the ID string or empty string if not found
        """
        import re

        # Look for the validation ID in the format "UNIQUE VALIDATION ID: xxxxxxxxx"
        pattern = r"UNIQUE VALIDATION ID:\s*([a-f0-9]+)"
        if match := re.search(pattern, raw_output, re.IGNORECASE):
            return match[1]

        # Fallback: look for the ID in the box format (standalone hex string)
        # Look for lines that contain only hexadecimal characters (the ID in the box)
        lines = raw_output.split("\n")
        for line in lines:
            line = line.strip()
            # Remove any container prefixes like "codebase-validator  | "
            clean_line = re.sub(r"^.*\|\s*", "", line).strip()
            # Check if it's a hex string of reasonable length (validation IDs are typically 16 chars)
            if re.match(r"^[a-f0-9]{8,32}$", clean_line):
                return clean_line

        return ""

    def open_add_project_window(self):
        """Open the add project window"""
        add_project_window = AddProjectWindow(self.window, self.add_project)
        add_project_window.create_window()

    def open_settings_window(self):
        """Open the settings window"""
        from gui.popup_windows import SettingsWindow

        settings_window = SettingsWindow(
            self.window, self.apply_settings, self.reset_settings
        )
        settings_window.create_window()

    def reset_settings(self):
        """Reset settings to defaults by removing user customizations"""
        try:
            from pathlib import Path

            user_settings_file = Path("config/user_settings.json")

            if user_settings_file.exists():
                user_settings_file.unlink()  # Delete the file

            # Show restart message
            result = messagebox.askquestion(
                "Settings Reset",
                "All settings have been reset to defaults.\n\nThe application needs to restart to apply the changes.\n\nRestart now?",
                icon="question",
            )

            if result == "yes":
                # Restart the application
                self._restart_application()
            else:
                messagebox.showinfo(
                    "Settings Reset",
                    "Settings have been reset to defaults. Please restart the application to see the changes.",
                )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to reset settings: {str(e)}")

    def apply_settings(self, new_settings: Dict[str, Any]):
        """Apply new settings and restart the application"""
        try:
            # Save settings to the config file
            self._save_settings_to_file(new_settings)

            # Show restart message
            result = messagebox.askquestion(
                "Settings Applied",
                "Settings have been saved successfully.\n\nThe application needs to restart to apply the new settings.\n\nRestart now?",
                icon="question",
            )

            if result == "yes":
                # Restart the application
                self._restart_application()
            else:
                messagebox.showinfo(
                    "Settings Saved",
                    "Settings have been saved. Please restart the application manually to apply the changes.",
                )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to apply settings: {str(e)}")

    def _save_settings_to_file(self, settings: Dict[str, Any]):
        """Save user settings to user_settings.json (overrides only)"""
        import json
        from pathlib import Path

        # Path to user settings file
        user_settings_file = Path("config/user_settings.json")

        # Load existing user settings or create empty dict
        user_settings = {}
        if user_settings_file.exists():
            try:
                with open(user_settings_file, "r", encoding="utf-8") as f:
                    user_settings = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                user_settings = {}

        # Add metadata
        user_settings["_comment"] = (
            "User customizations for Docker Tools - this file is not tracked by git"
        )
        user_settings["_instructions"] = (
            "This file contains only the settings you have customized. Default settings come from the unified config system"
        )

        # Get original default values from the unified config system
        default_settings = self._load_original_defaults()

        # Helper function to get nested default value using dot notation
        def get_default_value(key_path: str):
            """Get default value using dot notation path like 'gui.colors.background'"""
            # Convert unified config path to old settings attribute path
            if key_path.startswith("gui.colors."):
                color_key = key_path.split(".", 2)[2]
                return default_settings.COLORS.get(color_key)
            elif key_path.startswith("gui.fonts."):
                font_key = key_path.split(".", 2)[2]
                return default_settings.FONTS.get(font_key)
            elif key_path.startswith("gui.button_styles."):
                style_key = key_path.split(".", 2)[2]
                return default_settings.BUTTON_STYLES.get(style_key)
            elif key_path == "project.source_dir":
                return default_settings.SOURCE_DIR
            elif key_path == "gui.window_title":
                return default_settings.WINDOW_TITLE
            elif key_path == "gui.main_window_size":
                return default_settings.MAIN_WINDOW_SIZE
            elif key_path == "gui.output_window_size":
                return default_settings.OUTPUT_WINDOW_SIZE
            elif key_path == "gui.git_window_size":
                return default_settings.GIT_WINDOW_SIZE
            elif key_path == "project.ignore_dirs":
                return default_settings.IGNORE_DIRS
            elif key_path == "project.ignore_files":
                return default_settings.IGNORE_FILES
            elif key_path == "project.folder_aliases":
                return default_settings.FOLDER_ALIASES
            elif key_path == "language.extensions":
                return default_settings.LANGUAGE_EXTENSIONS
            elif key_path == "language.required_files":
                return default_settings.LANGUAGE_REQUIRED_FILES
            else:
                return None

        # Only save settings that differ from defaults
        for key, value in settings.items():
            # Skip metadata keys
            if key.startswith("_"):
                continue

            default_value = get_default_value(key)

            # Convert tuples to lists for JSON serialization
            if isinstance(value, tuple):
                value = list(value)
            if isinstance(default_value, tuple):
                default_value = list(default_value)

            # Only save if different from default
            if value != default_value:
                user_settings[key] = value
            elif key in user_settings:
                # Remove setting if it matches default (user reset it)
                del user_settings[key]

        # Save the user settings
        with open(user_settings_file, "w", encoding="utf-8") as f:
            json.dump(user_settings, f, indent=4, ensure_ascii=False)

    def _load_original_defaults(self):
        """Load original default settings from the unified config system WITHOUT user overrides"""
        from config.config import (
            UnifiedConfig,
            GuiConfig,
            ProjectConfig,
            LanguageConfig,
            CommandConfig,
            TestConfig,
            ServiceConfig,
        )

        # Create truly pristine config instances by bypassing the ConfigManager
        # This ensures we get the actual defaults without user overrides applied
        default_config = UnifiedConfig(
            gui=GuiConfig(),
            project=ProjectConfig(),
            language=LanguageConfig(),
            commands=CommandConfig(),
            test=TestConfig(),
            service=ServiceConfig(),
        )

        # Create a mock settings module with the same structure as the old settings.py
        class DefaultSettings:
            def __init__(self, config):
                # Map the unified config structure to the old settings.py format
                self.SOURCE_DIR = config.project.source_dir
                self.WINDOW_TITLE = config.gui.window_title
                self.MAIN_WINDOW_SIZE = config.gui.main_window_size
                self.OUTPUT_WINDOW_SIZE = config.gui.output_window_size
                self.GIT_WINDOW_SIZE = config.gui.git_window_size
                self.COLORS = config.gui.colors
                self.FONTS = config.gui.fonts
                self.BUTTON_STYLES = config.gui.button_styles
                self.IGNORE_DIRS = config.project.ignore_dirs
                self.IGNORE_FILES = config.project.ignore_files
                self.FOLDER_ALIASES = config.project.folder_aliases
                self.LANGUAGE_EXTENSIONS = config.language.extensions
                self.LANGUAGE_REQUIRED_FILES = config.language.required_files

        return DefaultSettings(default_config)

    def _restart_application(self):
        """Restart the application"""
        import sys
        import subprocess
        import os
        from pathlib import Path

        try:
            # Get the command to restart the application
            python_executable = sys.executable
            script_path = Path(sys.argv[0]).resolve()  # Make path absolute
            current_dir = Path.cwd()

            # Close current window and stop monitoring
            file_monitor.stop_all_monitoring()
            self.window.destroy()

            # Small delay to ensure cleanup
            import time

            time.sleep(0.5)

            # Restart using subprocess with proper configuration
            if os.name == "nt":  # Windows
                # Use DETACHED_PROCESS to fully detach from parent process (IDE-friendly)
                # Combined with CREATE_NO_WINDOW to avoid console window
                subprocess.Popen(
                    [python_executable, str(script_path)],
                    cwd=str(current_dir),
                    creationflags=subprocess.DETACHED_PROCESS
                    | subprocess.CREATE_NO_WINDOW,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                )
            else:  # Unix-like systems
                # Use start_new_session to detach from parent process
                subprocess.Popen(
                    [python_executable, str(script_path)],
                    cwd=str(current_dir),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True,
                )

            # Exit current process
            sys.exit(0)

        except Exception as e:
            # If restart fails, show an error and just exit
            messagebox.showerror(
                "Restart Failed",
                f"Could not restart the application automatically.\n\n"
                f"Error: {str(e)}\n\n"
                f"Please restart manually by running:\n{python_executable} {script_path}",
            )
            sys.exit(1)

    def add_project(self, repo_url: str, project_name: str):
        """Add a new project by cloning it into all subdirectories"""
        self.operation_manager.add_project(repo_url, project_name)

    def refresh_projects(self):
        """Refresh the project list"""
        # Clear existing widgets using MainWindow's interface
        self.main_window.clear_content()

        # Repopulate
        self.load_projects()

    def update_terminal_output(self, output: str, append: bool = True):
        """Update terminal output for web interface"""
        with self._terminal_output_lock:
            if append:
                self._current_terminal_output += output
            else:
                self._current_terminal_output = output

            # Limit output size to prevent memory issues (keep last 50KB)
            if len(self._current_terminal_output) > 50000:
                self._current_terminal_output = self._current_terminal_output[-50000:]

    def get_terminal_output(self) -> str:
        """Get current terminal output"""
        with self._terminal_output_lock:
            return self._current_terminal_output

    def clear_terminal_output(self):
        """Clear terminal output"""
        with self._terminal_output_lock:
            self._current_terminal_output = ""

    def run(self):
        """Start the GUI"""
        self.main_window.run()


def main():
    """Main function to run the control panel"""
    print("Starting Project Control Panel...")
    print(f"Source directory: {SOURCE_DIR}")

    app = ProjectControlPanel(SOURCE_DIR)
    app.run()


if __name__ == "__main__":
    main()
