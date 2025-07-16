"""
Unified Callback Handler for Project Control Panel Operations

This class provides centralized callback handling for all operation types
with configurable behavior and consistent message formatting.
"""

import tkinter as tk
from tkinter import messagebox
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field
from pathlib import Path

from config.config import get_config

COLORS = get_config().gui.colors


@dataclass
class CallbackConfig:
    """Configuration for operation-specific callback behavior"""

    # Success message customization
    success_title_template: str = "{operation_title} Complete"
    success_message_template: str = "{operation_title} completed successfully"
    success_show_dialog: bool = True
    success_show_terminal: bool = False

    # Error message customization
    error_title_template: str = "{operation_title} Error"
    error_message_template: str = "{operation_title} failed: {error_message}"

    # Partial result customization
    partial_title_template: str = "{operation_title} Warning"
    partial_message_template: str = (
        "{operation_title} completed with issues: {error_message}"
    )

    # Data extraction functions
    custom_success_message: Optional[Callable[[Dict[str, Any]], str]] = None
    custom_error_message: Optional[Callable[[Exception], str]] = None
    custom_data_processing: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None

    # Additional UI actions
    additional_success_actions: List[Callable[[Dict[str, Any]], None]] = field(
        default_factory=list
    )
    additional_error_actions: List[Callable[[Exception], None]] = field(
        default_factory=list
    )


class CallbackHandler:
    """Unified callback handler for all project operations"""

    def __init__(self, window: tk.Tk, control_panel=None):
        """
        Initialize the callback handler.

        Args:
            window: The main tkinter window
            control_panel: Reference to the main control panel for terminal windows
        """
        self.window = window
        self.control_panel = control_panel

        # Pre-configured operation types
        self.operation_configs = self._initialize_operation_configs()

    def _initialize_operation_configs(self) -> Dict[str, CallbackConfig]:
        """Initialize standardized configurations for different operation types"""
        configs = {
            "cleanup": CallbackConfig(
                custom_success_message=self._format_cleanup_success,
                success_show_dialog=True,
            )
        }

        # Validation operations
        configs["validation"] = CallbackConfig(
            custom_success_message=self._format_validation_success,
            success_show_dialog=True,
            additional_success_actions=[self._handle_validation_additional_actions],
        )

        # Git operations
        configs["git"] = CallbackConfig(
            success_show_dialog=False,  # Git ops show custom windows
            custom_success_message=self._format_git_success,
            additional_success_actions=[self._handle_git_warnings],
        )

        configs["git_checkout_all"] = CallbackConfig(
            success_show_dialog=False,
            custom_success_message=self._format_git_checkout_all_success,
            additional_success_actions=[self._handle_git_warnings],
        )

        # Docker operations
        configs["docker"] = CallbackConfig(
            success_show_dialog=False,  # Docker shows terminal windows
            success_show_terminal=True,
            custom_data_processing=self._process_docker_data,
            additional_success_actions=[self._show_docker_terminal],
        )

        # Sync operations
        configs["sync"] = CallbackConfig(
            custom_success_message=self._format_sync_success,
        )

        # Build operations
        configs["build"] = CallbackConfig(
            success_show_dialog=True,
        )

        # Archive operations
        configs["archive"] = CallbackConfig(
            custom_success_message=self._format_archive_success,
        )

        return configs

    def show_success(self, operation: str, data: Dict[str, Any] = None) -> None:
        """
        Unified success callback for all operations.

        Args:
            operation: The operation type (cleanup, validation, git, etc.)
            data: Operation result data
        """
        data = data or {}
        config = self.operation_configs.get(operation, CallbackConfig())

        # Process data if custom processor exists
        if config.custom_data_processing:
            data = config.custom_data_processing(data)

        # Generate success message
        if config.custom_success_message:
            message = config.custom_success_message(data)
        else:
            message = config.success_message_template.format(
                operation_title=operation.title(), **data
            )

        # Show dialog if configured
        if config.success_show_dialog:
            title = config.success_title_template.format(
                operation_title=operation.title()
            )
            self._show_info_message(title, message)

        # Show terminal if configured
        if config.success_show_terminal:
            self._show_terminal_results(operation, data)

        # Execute additional actions
        for action in config.additional_success_actions:
            try:
                action(data)
            except Exception as e:
                print(f"Error in additional success action for {operation}: {e}")

    def show_error(self, operation: str, error: Exception) -> None:
        """
        Unified error callback for all operations.

        Args:
            operation: The operation type (cleanup, validation, git, etc.)
            error: The error that occurred
        """
        config = self.operation_configs.get(operation, CallbackConfig())

        # Generate error message
        if config.custom_error_message:
            message = config.custom_error_message(error)
        else:
            error_message = getattr(error, "message", str(error))
            message = config.error_message_template.format(
                operation_title=operation.title(), error_message=error_message
            )

        # Show error dialog
        title = config.error_title_template.format(operation_title=operation.title())
        self._show_error_message(title, message)

        # Execute additional error actions
        for action in config.additional_error_actions:
            try:
                action(error)
            except Exception as e:
                print(f"Error in additional error action for {operation}: {e}")

    def show_results(self, operation: str, data: Dict[str, Any]) -> None:
        """
        Show operation results in appropriate format (terminal window, dialog, etc.).

        Args:
            operation: The operation type
            data: Result data to display
        """
        if operation == "docker":
            self._show_docker_terminal(data)
        else:
            # Default to success handling
            self.show_success(operation, data)

    def show_partial_result(
        self, operation: str, data: Dict[str, Any], error: Exception
    ) -> None:
        """
        Handle partial success results (completed with warnings/issues).

        Args:
            operation: The operation type
            data: Partial result data
            error: The warning/issue that occurred
        """
        config = self.operation_configs.get(operation, CallbackConfig())

        error_message = getattr(error, "message", str(error))
        message = config.partial_message_template.format(
            operation_title=operation.title(), error_message=error_message
        )

        title = config.partial_title_template.format(operation_title=operation.title())
        self._show_warning_message(title, message)

    # Thread-safe GUI update helpers
    def _show_info_message(self, title: str, message: str) -> None:
        """Show info message in GUI thread"""
        from .gui_coordinator import get_gui_coordinator

        if coordinator := get_gui_coordinator():
            coordinator.show_info(title, message)
        else:
            # Fallback to direct tkinter
            self.window.after(0, lambda: messagebox.showinfo(title, message))

    def _show_error_message(self, title: str, message: str) -> None:
        """Show error message in GUI thread"""
        from .gui_coordinator import get_gui_coordinator

        if coordinator := get_gui_coordinator():
            coordinator.show_error(title, message)
        else:
            # Fallback to direct tkinter
            self.window.after(0, lambda: messagebox.showerror(title, message))

    def _show_warning_message(self, title: str, message: str) -> None:
        """Show warning message in GUI thread"""
        from .gui_coordinator import get_gui_coordinator

        if coordinator := get_gui_coordinator():
            coordinator.show_warning(title, message)
        else:
            # Fallback to direct tkinter
            self.window.after(0, lambda: messagebox.showwarning(title, message))

    def _show_terminal_results(self, operation: str, data: Dict[str, Any]) -> None:
        """Show results in a terminal window"""
        # This would be implemented based on specific terminal window needs
        pass

    # Custom message formatters for specific operations
    def _format_cleanup_success(self, data: Dict[str, Any]) -> str:
        """Format cleanup success message with deleted items"""
        message = data.get("message", "Cleanup completed successfully")
        deleted_items = data.get("deleted_directories", []) + data.get(
            "deleted_files", []
        )

        if not deleted_items:
            return f"{message}\n\nNo items needed cleanup."
        item_list = "\n".join([f"  • {item}" for item in deleted_items[:10]])
        if len(deleted_items) > 10:
            item_list += f"\n  ... and {len(deleted_items) - 10} more items"
        return f"{message}\n\nDeleted items:\n{item_list}"

    def _format_validation_success(self, data: Dict[str, Any]) -> str:
        """Format validation success message with validation ID"""
        validation_id = data.get("validation_id", "")
        if validation_id:
            return f"Validation completed successfully!\nValidation ID: {validation_id}"
        else:
            return "Validation completed successfully!"

    def _format_git_success(self, data: Dict[str, Any]) -> str:
        """Format git operation success message"""
        commits_count = len(data.get("commits", []))
        return f"Loaded {commits_count} commits from repository"

    def _format_git_checkout_all_success(self, data: Dict[str, Any]) -> str:
        """Format git checkout all success message"""
        commits_count = len(data.get("commits", []))
        versions_count = len(data.get("all_versions", []))
        return f"Loaded {commits_count} commits for {versions_count} versions"

    def _format_sync_success(self, data: Dict[str, Any]) -> str:
        """Format sync operation success message"""
        success_count = data.get("success_count", 0)
        total_targets = data.get("total_targets", 0)
        file_name = data.get("file_name", "files")
        return f"Successfully synced {file_name} to {success_count}/{total_targets} directories"

    def _format_archive_success(self, data: Dict[str, Any]) -> str:
        """Format archive success message with details"""
        message = data.get("message", "Archive created successfully")
        archive_size = data.get("archive_size", 0)
        if archive_size > 0:
            size_mb = archive_size / (1024 * 1024)
            return f"{message}\nArchive size: {size_mb:.1f} MB"
        return message

    # Custom data processors
    def _process_docker_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process Docker operation data for consistent format"""
        # Ensure consistent data structure for Docker operations
        processed = data.copy()
        if "build_data" not in processed:
            processed["build_data"] = {}
        if "test_data" not in processed:
            processed["test_data"] = {}
        return processed

    # Additional action handlers
    def _handle_validation_additional_actions(self, data: Dict[str, Any]) -> None:
        """Handle additional validation-specific actions"""
        # Check for validation results file
        results_file = Path("validation-tool/output/validation_results.csv")
        if results_file.exists():
            # Could add automatic file opening or other actions here
            pass

    def _handle_git_warnings(self, data: Dict[str, Any]) -> None:
        """Handle git-specific warnings"""
        fetch_success = data.get("fetch_success", True)
        fetch_message = data.get("fetch_message", "")

        if not fetch_success and "No remote repository" not in fetch_message:
            self._show_warning_message(
                "Fetch Warning",
                f"Could not fetch latest commits:\n{fetch_message}\n\nShowing local commits only.",
            )

    def _show_docker_terminal(self, data: Dict[str, Any]) -> None:
        """Show Docker results in terminal window"""
        if not self.control_panel:
            return

        def create_window():
            from gui import TerminalOutputWindow

            docker_tag = data.get("docker_tag", "unknown")
            project_name = data.get("project_name", "unknown")

            terminal_window = TerminalOutputWindow(
                self.window,
                f"Docker Build & Test - {project_name}",
                control_panel=self.control_panel,
            )
            terminal_window.create_window()

            # Combine build and test output
            build_data = data.get("build_data", {})
            test_data = data.get("test_data", {})

            build_output = (
                build_data.get("build_output", "")
                if isinstance(build_data, dict)
                else str(build_data)
            )
            test_output = (
                test_data.get("raw_output", "")
                if isinstance(test_data, dict)
                else str(test_data)
            )

            # Add output to terminal window
            if build_output:
                terminal_window.append_output("=== BUILD OUTPUT ===\n")
                terminal_window.append_output(build_output)
                terminal_window.append_output("\n\n")

            if test_output:
                terminal_window.append_output("=== TEST OUTPUT ===\n")
                terminal_window.append_output(test_output)
                terminal_window.append_output("\n")

            # Add final buttons with copy functionality
            combined_output = f"=== BUILD OUTPUT ===\n{build_output}\n\n=== TEST OUTPUT ===\n{test_output}"
            terminal_window.add_final_buttons(copy_text=combined_output)

            # Update final status
            terminal_window.update_status(
                "Docker operation completed", COLORS["success"]
            )

        from .gui_coordinator import get_gui_coordinator

        coordinator = get_gui_coordinator()
        if coordinator:
            coordinator.schedule_immediate(create_window)
        else:
            # Fallback to direct tkinter
            self.window.after(0, create_window)

    def register_operation_config(self, operation: str, config: CallbackConfig) -> None:
        """Register a custom configuration for an operation"""
        self.operation_configs[operation] = config

    def get_operation_config(self, operation: str) -> CallbackConfig:
        """Get the configuration for an operation"""
        return self.operation_configs.get(operation, CallbackConfig())
