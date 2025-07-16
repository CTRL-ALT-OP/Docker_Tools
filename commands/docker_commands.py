"""
Docker-specific command implementations
Handles Docker build, test, and file generation operations
"""

import asyncio
from typing import Dict, Any

from utils.async_base import AsyncCommand, AsyncResult, ProcessError
from models.project import Project
from services.project_group_service import ProjectGroup
from config.config import get_config

COLORS = get_config().gui.colors


class DockerBuildAndTestCommand(AsyncCommand):
    """Standardized command for Docker build and test operations with real-time streaming"""

    def __init__(self, project: Project, docker_service, window=None, **kwargs):
        super().__init__(**kwargs)
        self.project = project
        self.docker_service = docker_service
        self.docker_tag = f"{self.project.parent}_{self.project.name}".lower()
        self.window = window
        self.terminal_window = None

    async def execute(self) -> AsyncResult[Dict[str, Any]]:
        """Execute the Docker build and test command with real-time streaming"""
        try:
            # Import here to avoid circular imports
            from gui import TerminalOutputWindow

            self._update_progress("Starting Docker build and test...", "info")

            # Create terminal window immediately (before starting operation)
            def create_window():
                self.terminal_window = TerminalOutputWindow(
                    self.window, f"Docker Build & Test - {self.project.name}"
                )
                self.terminal_window.create_window()
                self.terminal_window.update_status(
                    "Starting Docker build...", COLORS["warning"]
                )

            if self.window:
                self.window.after(0, create_window)
                await asyncio.sleep(0.1)  # Wait for window creation

            # Define streaming callbacks that update the GUI in real-time
            def streaming_output_callback(message: str):
                """Real-time output streaming to GUI"""
                if self.terminal_window:
                    self.terminal_window.append_output(message)

            def streaming_status_callback(status: str, color: str):
                """Real-time status updates to GUI"""
                if self.terminal_window:
                    self.terminal_window.update_status(status, color)

            # Execute Docker build and test with real-time streaming
            result = await self.docker_service.build_and_test(
                self.project.path,
                self.docker_tag,
                progress_callback=streaming_output_callback,
                status_callback=streaming_status_callback,
            )

            # Handle results and update terminal window
            if result.is_success:
                if self.terminal_window:
                    self.terminal_window.update_status(
                        "Build and test completed successfully!", COLORS["success"]
                    )
                    self.terminal_window.append_output(
                        "\n✅ All operations completed successfully!\n"
                    )
            elif result.is_partial:
                if self.terminal_window:
                    self.terminal_window.update_status(
                        "Build successful, some tests failed", COLORS["warning"]
                    )
                    self.terminal_window.append_output(
                        "\n⚠️ Build completed but some tests failed.\n"
                    )
            else:
                if self.terminal_window:
                    self.terminal_window.update_status(
                        "Build and test failed", COLORS["error"]
                    )
                    self.terminal_window.append_output("\n❌ Build and test failed.\n")

            # Add final buttons for interaction
            if self.terminal_window and self.window:

                def add_buttons():
                    if self.terminal_window.text_area:
                        full_output = self.terminal_window.text_area.get(
                            "1.0", "end-1c"
                        )
                        self.terminal_window.add_final_buttons(copy_text=full_output)

                self.window.after(0, add_buttons)

            result_data = {
                "message": f"Docker build and test completed for {self.project.name}",
                "docker_tag": self.docker_tag,
                "build_data": result.data.get("build_data", {}) if result.data else {},
                "test_data": result.data.get("test_data", {}) if result.data else {},
                "project_name": self.project.name,
                "terminal_created": self.terminal_window is not None,
            }

            if result.is_error:
                return AsyncResult.error_result(result.error)
            elif result.is_partial:
                return AsyncResult.partial_result(result_data, result.error)
            else:
                return AsyncResult.success_result(result_data)

        except Exception as e:
            self.logger.exception(f"Docker command failed for {self.project.name}")
            if self.terminal_window:
                self.terminal_window.update_status("Error occurred", COLORS["error"])
                self.terminal_window.append_output(f"\n❌ Error: {str(e)}\n")

            return AsyncResult.error_result(
                ProcessError(
                    f"Docker build and test failed: {str(e)}", error_code="DOCKER_ERROR"
                )
            )


class BuildDockerFilesCommand(AsyncCommand):
    """Standardized command for building Docker files with complex file generation"""

    def __init__(
        self,
        project_group: ProjectGroup,
        docker_files_service,
        window=None,
        async_bridge=None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.project_group = project_group
        self.docker_files_service = docker_files_service
        self.window = window
        self.async_bridge = async_bridge
        self.terminal_window = None

    def _restart_with_removal(self):
        """Restart the build process after removing existing files"""

        async def restart_async():
            # Find the pre-edit version to remove files from
            pre_edit_project = self.docker_files_service._find_pre_edit_version(
                self.project_group
            )
            if not pre_edit_project:
                if self.window:
                    from tkinter import messagebox

                    self.window.after(
                        0,
                        lambda: messagebox.showerror(
                            "Error", "Could not find pre-edit version for file removal"
                        ),
                    )
                return

            # Create new terminal window for the removal and rebuild
            from gui import TerminalOutputWindow

            def create_new_window():
                self.terminal_window = TerminalOutputWindow(
                    self.window,
                    f"Build Docker Files - {self.project_group.name} (Removing existing)",
                )
                self.terminal_window.create_window()
                self.terminal_window.update_status(
                    "Removing existing files...", COLORS["warning"]
                )

            if self.window:
                self.window.after(0, create_new_window)
                await asyncio.sleep(0.1)  # Wait for window creation

            # Define callbacks for the removal and rebuild
            def progress_callback(message: str):
                if self.terminal_window:
                    self.terminal_window.append_output(message)

            def status_callback(status: str, color: str):
                if self.terminal_window:
                    self.terminal_window.update_status(status, color)

            try:
                # Remove existing Docker files
                removal_success = (
                    await self.docker_files_service.remove_existing_docker_files(
                        pre_edit_project, progress_callback
                    )
                )

                if not removal_success:
                    if self.terminal_window:
                        self.terminal_window.update_status(
                            "Removal failed", COLORS["error"]
                        )
                        self.terminal_window.append_output(
                            "\n❌ Failed to remove existing files.\n"
                        )
                    return

                # Now retry the build
                status_callback("Starting fresh build...", COLORS["warning"])
                build_result = await self.docker_files_service.build_docker_files_for_project_group(
                    self.project_group,
                    progress_callback,
                    status_callback,
                )

                # Handle the result
                if isinstance(build_result, tuple):
                    success, message = build_result
                    if success:
                        if self.terminal_window:
                            self.terminal_window.update_status(
                                "Build completed successfully", COLORS["success"]
                            )
                            self.terminal_window.append_output(
                                "\n✅ Docker files build completed successfully!\n"
                            )

                            # Add final buttons
                            if self.terminal_window.text_area:
                                full_output = self.terminal_window.text_area.get(
                                    "1.0", "end-1c"
                                )
                                self.terminal_window.add_final_buttons(
                                    copy_text=full_output
                                )
                    else:
                        if self.terminal_window:
                            self.terminal_window.update_status(
                                "Build failed", COLORS["error"]
                            )
                            self.terminal_window.append_output(
                                f"\n❌ Build failed: {message}\n"
                            )
                else:
                    # Handle AsyncResult format
                    if hasattr(build_result, "is_success") and build_result.is_success:
                        if self.terminal_window:
                            self.terminal_window.update_status(
                                "Build completed successfully", COLORS["success"]
                            )
                            self.terminal_window.append_output(
                                "\n✅ Docker files build completed successfully!\n"
                            )

                            # Add final buttons
                            if self.terminal_window.text_area:
                                full_output = self.terminal_window.text_area.get(
                                    "1.0", "end-1c"
                                )
                                self.terminal_window.add_final_buttons(
                                    copy_text=full_output
                                )
                    else:
                        if self.terminal_window:
                            self.terminal_window.update_status(
                                "Build failed", COLORS["error"]
                            )
                            self.terminal_window.append_output(
                                f"\n❌ Build failed: {build_result.error.message if hasattr(build_result, 'error') else 'Unknown error'}\n"
                            )

            except Exception as e:
                if self.terminal_window:
                    self.terminal_window.update_status(
                        "Error occurred", COLORS["error"]
                    )
                    self.terminal_window.append_output(
                        f"\n❌ Error during removal and rebuild: {str(e)}\n"
                    )

        # Start the async restart operation
        if hasattr(self, "_task_manager"):
            self._task_manager.run_task(
                restart_async(), task_name=f"rebuild-docker-{self.project_group.name}"
            )
        else:
            # Fallback to using the global task manager
            from utils.async_utils import task_manager

            task_manager.run_task(
                restart_async(), task_name=f"rebuild-docker-{self.project_group.name}"
            )

    async def execute(self) -> AsyncResult[Dict[str, Any]]:
        """Execute the build Docker files command with terminal window"""
        try:
            # Import here to avoid circular imports
            from gui import TerminalOutputWindow

            self._update_progress("Building Docker files...", "info")

            # Create terminal window immediately if window is available
            if self.window and self.async_bridge:
                event_id, window_ready_event = self.async_bridge.create_sync_event()

                def create_window():
                    self.terminal_window = TerminalOutputWindow(
                        self.window, f"Build Docker Files - {self.project_group.name}"
                    )
                    self.terminal_window.create_window()
                    self.terminal_window.update_status(
                        "Starting Docker files build...", COLORS["warning"]
                    )
                    # Signal that window is ready
                    self.async_bridge.signal_from_gui(event_id)

                self.window.after(0, create_window)
                await window_ready_event.wait()
                self.async_bridge.cleanup_event(event_id)

            # Define progress callback that streams to terminal window
            def docker_files_progress_callback(message: str):
                if self.terminal_window:
                    self.terminal_window.append_output(message)
                self._update_progress(message, "info")

            # Define status callback
            def docker_files_status_callback(status: str, color: str):
                if self.terminal_window:
                    self.terminal_window.update_status(status, color)
                level = (
                    "success"
                    if color == COLORS["success"]
                    else "warning" if color == COLORS["warning"] else "error"
                )
                self._update_progress(status, level)

            # Build Docker files
            build_result = (
                await self.docker_files_service.build_docker_files_for_project_group(
                    self.project_group,
                    docker_files_progress_callback,
                    docker_files_status_callback,
                )
            )

            # Handle different return formats - service might return tuple (success, message) or AsyncResult
            if isinstance(build_result, tuple):
                # Old format: (success: bool, message: str)
                success, message = build_result
                if not success:
                    # Check if the error is due to existing files
                    if "Existing Docker files found" in message:
                        # Handle existing files by prompting user
                        if self.terminal_window:
                            self.terminal_window.update_status(
                                "Existing files found", COLORS["warning"]
                            )
                            self.terminal_window.append_output(f"\n⚠️  {message}\n")
                            self.terminal_window.append_output("\nOptions:\n")
                            self.terminal_window.append_output(
                                "• Remove existing files and proceed\n"
                            )
                            self.terminal_window.append_output("• Cancel operation\n\n")

                            # Add buttons for user choice
                            def handle_remove_and_continue():
                                if self.terminal_window:
                                    # Close the terminal window and restart with removal
                                    self.terminal_window.destroy()
                                # Trigger a new build with removal
                                self._restart_with_removal()

                            def handle_cancel():
                                if self.terminal_window:
                                    self.terminal_window.update_status(
                                        "Operation cancelled", COLORS["error"]
                                    )
                                    self.terminal_window.append_output(
                                        "\n❌ Operation cancelled by user.\n"
                                    )

                            additional_buttons = [
                                {
                                    "text": "🗑️ Remove & Continue",
                                    "command": handle_remove_and_continue,
                                    "style": "cleanup",
                                },
                                {
                                    "text": "❌ Cancel",
                                    "command": handle_cancel,
                                    "style": "close",
                                },
                            ]

                            self.terminal_window.add_final_buttons(
                                copy_text="", additional_buttons=additional_buttons
                            )

                        return AsyncResult.error_result(
                            ProcessError(
                                f"Build cancelled due to existing files: {message}",
                                error_code="EXISTING_FILES",
                            )
                        )
                    else:
                        # Other type of error
                        if self.terminal_window:
                            self.terminal_window.update_status(
                                "Build failed", COLORS["error"]
                            )
                            self.terminal_window.append_output(
                                f"\n❌ Error: {message}\n"
                            )
                        return AsyncResult.error_result(
                            ProcessError(
                                f"Build failed: {message}",
                                error_code="DOCKER_FILES_ERROR",
                            )
                        )
                # Convert to standard format for success
                build_result = AsyncResult.success_result(
                    {"message": message, "success": True}
                )
            elif hasattr(build_result, "is_error") and build_result.is_error:
                # New format: AsyncResult
                if self.terminal_window:
                    self.terminal_window.update_status("Build failed", COLORS["error"])
                    self.terminal_window.append_output(
                        f"\n❌ Error: {build_result.error.message}\n"
                    )
                return AsyncResult.error_result(build_result.error)

            # Update terminal window with success
            if self.terminal_window:
                self.terminal_window.update_status(
                    "Docker files built successfully", COLORS["success"]
                )
                self.terminal_window.append_output(
                    "\n✅ Docker files build completed successfully!\n"
                )

                # Add final buttons with copy functionality
                if self.terminal_window.text_area:
                    full_output = self.terminal_window.text_area.get("1.0", "end-1c")
                    self.terminal_window.add_final_buttons(copy_text=full_output)

            result_data = {
                "message": f"Docker files built for {self.project_group.name}",
                "project_group_name": self.project_group.name,
                "success": (
                    build_result.is_success
                    if hasattr(build_result, "is_success")
                    else True
                ),
                "details": (
                    build_result.data
                    if hasattr(build_result, "data") and build_result.data
                    else {}
                ),
                "terminal_created": self.terminal_window is not None,
            }

            self._update_progress("Docker files built successfully", "success")

            return AsyncResult.success_result(
                result_data,
                message=f"Successfully built Docker files for {self.project_group.name}",
            )

        except Exception as e:
            self.logger.exception(
                f"Build Docker files command failed for {self.project_group.name}"
            )
            if self.terminal_window:
                self.terminal_window.update_status("Error occurred", COLORS["error"])
                self.terminal_window.append_output(f"\n❌ Error: {str(e)}\n")

            return AsyncResult.error_result(
                ProcessError(
                    f"Build Docker files failed: {str(e)}",
                    error_code="DOCKER_FILES_ERROR",
                )
            )
