"""
Operation Manager for Project Control Panel

This class handles all async operation commands and their completion callbacks,
extracting this responsibility from the main ProjectControlPanel class.
"""

import asyncio
import contextlib
import logging
from pathlib import Path
from typing import Dict, Any, List
from tkinter import messagebox

from models.project import Project
from services.project_group_service import ProjectGroup
from services.platform_service import PlatformService
from utils.async_utils import task_manager
from gui import TerminalOutputWindow, EditRunTestsWindow
from config.config import get_config
from commands import (
    CleanupProjectCommand,
    ArchiveProjectCommand,
    DockerBuildAndTestCommand,
    GitViewCommand,
    GitCheckoutAllCommand,
    SyncRunTestsCommand,
    ValidateProjectGroupCommand,
    BuildDockerFilesCommand,
)

# Cache config values for efficiency
_config = get_config()
COLORS = _config.gui.colors
SOURCE_DIR = _config.project.source_dir

logger = logging.getLogger(__name__)


class OperationManager:
    """
    Manages all async operation commands for the Project Control Panel.

    This class handles:
    - Project operations (cleanup, archive, docker, git, sync, validation, build)
    - Command instantiation with proper callbacks
    - Completion handling and result processing
    - Complex async operations like add_project and edit_run_tests
    """

    def __init__(
        self, services: Dict[str, Any], callback_handler, window, control_panel=None
    ):
        """
        Initialize the operation manager.

        Args:
            services: Dictionary of initialized services
            callback_handler: Unified callback handler for operation results
            window: Main tkinter window
            control_panel: Reference to main control panel for terminal windows
        """
        self.services = services
        self.callback_handler = callback_handler
        self.window = window
        self.control_panel = control_panel

        # Extract individual services for easier access
        self.project_service = services.get("project_service")
        self.file_service = services.get("file_service")
        self.git_service = services.get("git_service")
        self.docker_service = services.get("docker_service")
        self.sync_service = services.get("sync_service")
        self.validation_service = services.get("validation_service")
        self.docker_files_service = services.get("docker_files_service")

        # For async bridge operations
        self.async_bridge = services.get("async_bridge")

    # Status update methods
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
        # Only log significant status changes, not all progress messages
        if any(
            keyword in message.lower()
            for keyword in ["completed", "failed", "error", "started", "finished"]
        ):
            logger.info(f"Status: {message} ({color})")

    # Project Operations
    def cleanup_project(self, project: Project):
        """Execute project cleanup operation"""
        command = CleanupProjectCommand(
            project=project,
            file_service=self.file_service,
            progress_callback=self._update_status,
            completion_callback=self._handle_cleanup_completion,
        )
        task_manager.run_task(
            command.run_with_progress(), task_name=f"cleanup-{project.name}"
        )

    def archive_project(self, project: Project):
        """Execute project archive operation"""
        command = ArchiveProjectCommand(
            project=project,
            file_service=self.file_service,
            project_service=self.project_service,
            progress_callback=self._update_status,
            completion_callback=self._handle_archive_completion,
        )
        task_manager.run_task(
            command.run_with_progress(), task_name=f"archive-{project.name}"
        )

    def docker_build_and_test(self, project: Project):
        """Execute Docker build and test operation"""
        command = DockerBuildAndTestCommand(
            project=project,
            docker_service=self.docker_service,
            window=self.window,
            progress_callback=self._update_status,
            completion_callback=self._handle_docker_completion,
        )
        task_manager.run_task(
            command.run_with_progress(), task_name=f"docker-{project.name}"
        )

    def git_view(self, project: Project):
        """Execute git view operation"""
        command = GitViewCommand(
            project=project,
            git_service=self.git_service,
            window=self.window,
            checkout_callback=lambda commit_hash, git_window: self.checkout_commit_callback(
                project.path, project.name, commit_hash, git_window
            ),
            progress_callback=self._update_status,
            completion_callback=self._handle_git_completion,
        )

        task_manager.run_task(
            command.run_with_progress(), task_name=f"git-{project.name}"
        )

    def git_checkout_all(self, project_group: ProjectGroup):
        """Execute git checkout all operation"""
        command = GitCheckoutAllCommand(
            project_group=project_group,
            git_service=self.git_service,
            window=self.window,
            progress_callback=self._update_status,
            completion_callback=self._handle_git_checkout_all_completion,
        )

        task_manager.run_task(
            command.run_with_progress(),
            task_name=f"git-checkout-all-{project_group.name}",
        )

    def sync_run_tests_from_pre_edit(self, project_group: ProjectGroup):
        """Execute sync run tests operation"""
        command = SyncRunTestsCommand(
            project_group=project_group,
            sync_service=self.sync_service,
            progress_callback=self._update_status,
            completion_callback=self._handle_sync_completion,
        )

        task_manager.run_task(
            command.run_with_progress(), task_name=f"sync-{project_group.name}"
        )

    def validate_project_group(self, project_group: ProjectGroup):
        """Execute project group validation operation"""
        command = ValidateProjectGroupCommand(
            project_group=project_group,
            validation_service=self.validation_service,
            window=self.window,
            async_bridge=self.async_bridge,
            progress_callback=self._update_status,
            completion_callback=self._handle_validation_completion,
        )

        task_manager.run_task(
            command.run_with_progress(), task_name=f"validate-{project_group.name}"
        )

    def build_docker_files_for_project_group(self, project_group: ProjectGroup):
        """Execute Docker files build operation"""
        command = BuildDockerFilesCommand(
            project_group=project_group,
            docker_files_service=self.docker_files_service,
            window=self.window,
            async_bridge=self.async_bridge,
            progress_callback=self._update_status,
            completion_callback=self._handle_build_completion,
        )

        task_manager.run_task(
            command.run_with_progress(), task_name=f"build-docker-{project_group.name}"
        )

    # Completion Handlers
    def _handle_cleanup_completion(self, result):
        """Handle cleanup operation completion"""
        if result.is_success:
            self.callback_handler.show_success("cleanup", result.data)
            # Reset archive button color if files were actually deleted and project was archived
            if result.data and "project" in result.data:
                project = result.data["project"]
                deleted_dirs = result.data.get("deleted_directories", [])
                deleted_files = result.data.get("deleted_files", [])
                # Only reset if something was actually deleted
                if deleted_dirs or deleted_files:
                    self.control_panel.main_window.reset_archive_button_color(project)
        else:
            self.callback_handler.show_error("cleanup", result.error)

    def _handle_archive_completion(self, result):
        """Handle archive operation completion"""
        if result.is_success:
            self.callback_handler.show_success("archive", result.data)
            # Mark the project as archived to turn button green and start monitoring
            if result.data and "project" in result.data:
                project = result.data["project"]
                self.control_panel.main_window.mark_project_archived(project)
        else:
            self.callback_handler.show_error("archive", result.error)

    def _handle_docker_completion(self, result):
        """Handle Docker operation completion"""
        # Check if the command already created a terminal window
        if result.data and result.data.get("terminal_created", False):
            # Terminal window already exists with real-time output, no need for additional handling
            return

        # Only show dialogs if the command didn't create a terminal window
        if result.is_success and result.data:
            self.callback_handler.show_results("docker", result.data)
        elif result.is_error:
            self.callback_handler.show_error("docker", result.error)

    def _handle_git_completion(self, result):
        """Handle git operation completion"""
        # Check if the command already created a git window
        if result.data and result.data.get("git_window_created", False):
            # Git window already exists with real-time output, no need for additional handling
            return

        # Only show messages if the command didn't create a window
        if result.is_success:
            self.callback_handler.show_success("git", result.data)
        else:
            self.callback_handler.show_error("git", result.error)

    def _handle_git_checkout_all_completion(self, result):
        """Handle git checkout all operation completion"""
        # Check if the command already created a git window
        if result.data and result.data.get("git_window_created", False):
            # Git window already exists with real-time output, no need for additional handling
            return

        # Only show messages if the command didn't create a window
        if result.is_success:
            self.callback_handler.show_success("git_checkout_all", result.data)
        else:
            self.callback_handler.show_error("git_checkout_all", result.error)

    def _handle_sync_completion(self, result):
        """Handle sync operation completion"""
        if result.is_success:
            self.callback_handler.show_success("sync", result.data)
        elif result.is_partial:
            self.callback_handler.show_partial_result("sync", result.data, result.error)
        else:
            self.callback_handler.show_error("sync", result.error)

    def _handle_validation_completion(self, result):
        """Handle validation operation completion"""
        # Check if the command already created a terminal window
        if result.data and result.data.get("terminal_created", False):
            # Terminal window already exists with real-time output, no need for additional handling
            return

        # Only show dialogs if the command didn't create a terminal window
        if result.is_success:
            self.callback_handler.show_success("validation", result.data)
        elif result.is_error:
            self.callback_handler.show_error("validation", result.error)

    def _handle_build_completion(self, result):
        """Handle build operation completion"""
        # Check if the command already created a terminal window
        if result.data and result.data.get("terminal_created", False):
            # Terminal window already exists with real-time output, no need for additional handling
            return

        # Only show dialogs if the command didn't create a terminal window
        if result.is_success:
            self.callback_handler.show_success("build", result.data)
        elif result.is_error:
            self.callback_handler.show_error("build", result.error)

    # Complex Operations
    def edit_run_tests(self, project_group: ProjectGroup):
        """Open the edit run_tests.sh window"""
        edit_window = EditRunTestsWindow(
            self.window, project_group, self._handle_run_tests_edit
        )
        edit_window.create_window()

    def _handle_run_tests_edit(
        self,
        project_group: ProjectGroup,
        selected_tests: List[str],
        language: str = "python",
    ):
        """Handle run_tests.sh editing operation"""

        async def edit_run_tests_async():
            output_window = None
            try:
                # Create output window for showing progress
                output_window = TerminalOutputWindow(
                    self.window,
                    f"Edit run_tests.sh - {project_group.name}",
                    control_panel=self.control_panel,
                )
                output_window.create_window()
                output_window.update_status("Initializing...", COLORS["warning"])

                # Get all versions of the project
                versions = project_group.get_all_versions()
                if not versions:
                    output_window.update_status(
                        "Error: No versions found", COLORS["error"]
                    )
                    output_window.append_output(
                        f"No versions found for project group {project_group.name}\n"
                    )
                    return

                output_window.append_output(
                    f"Found {len(versions)} versions to update:\n"
                )
                for version in versions:
                    output_window.append_output(
                        f"  • {version.parent}/{version.name}\n"
                    )
                output_window.append_output("\n")

                # Generate test command based on selected tests and language
                test_paths = " ".join(selected_tests) if selected_tests else ""
                test_command = self._generate_test_command(language, test_paths)

                output_window.append_output(f"Generated test command for {language}:\n")
                output_window.append_output(f"  {test_command}\n\n")

                successful_updates = []
                failed_updates = []

                # Update run_tests.sh in each version
                for i, project in enumerate(versions):
                    try:
                        output_window.update_status(
                            f"Updating {project.parent} ({i+1}/{len(versions)})",
                            COLORS["warning"],
                        )

                        run_tests_path = project.path / "run_tests.sh"

                        # Preserve original shebang if file exists, otherwise use portable default
                        original_shebang = "#!/bin/sh"  # Default to portable shell
                        if run_tests_path.exists():
                            with contextlib.suppress(Exception):
                                existing_content = run_tests_path.read_text(
                                    encoding="utf-8"
                                )
                                lines = existing_content.split("\n")
                                if lines and lines[0].startswith("#!"):
                                    original_shebang = lines[0].rstrip(
                                        "\r"
                                    )  # Strip CRLF fix

                        # Create the run_tests.sh content
                        run_tests_content = f"""{original_shebang}
# Auto-generated run_tests.sh for {project.parent}
# Language: {language}
# Selected tests: {', '.join(selected_tests) if selected_tests else 'All tests'}

set -e  # Exit on any error

echo "Running tests for {project.parent}..."
echo "Language: {language}"
echo "Test command: {test_command}"
echo ""

# Execute the test command
{test_command}

echo ""
echo "Tests completed for {project.parent}"
"""

                        # Write the file with Unix line endings (LF) to avoid Docker issues
                        run_tests_path.write_text(
                            run_tests_content,
                            encoding="utf-8",
                            newline="\n",  # LF enforcement fix
                        )

                        # Make it executable (on Unix-like systems)
                        if run_tests_path.exists():
                            import stat

                            run_tests_path.chmod(
                                run_tests_path.stat().st_mode | stat.S_IEXEC
                            )

                        successful_updates.append(f"{project.parent}/{project.name}")
                        output_window.append_output(
                            f"✅ Updated {project.parent}/run_tests.sh\n"
                        )

                    except Exception as e:
                        failed_updates.append(
                            f"{project.parent}/{project.name}: {str(e)}"
                        )
                        output_window.append_output(
                            f"❌ Failed to update {project.parent}: {str(e)}\n"
                        )

                # Final summary
                output_window.append_output(f"\n" + "=" * 50 + "\n")
                output_window.append_output(f"EDIT SUMMARY\n")
                output_window.append_output("=" * 50 + "\n")
                output_window.append_output(f"Total versions: {len(versions)}\n")
                output_window.append_output(
                    f"Successfully updated: {len(successful_updates)}\n"
                )
                output_window.append_output(f"Failed updates: {len(failed_updates)}\n")

                if successful_updates:
                    output_window.append_output(f"\nSuccessful updates:\n")
                    for update in successful_updates:
                        output_window.append_output(f"  • {update}\n")

                if failed_updates:
                    output_window.append_output(f"\nFailed updates:\n")
                    for update in failed_updates:
                        output_window.append_output(f"  • {update}\n")

                # Set final status
                if failed_updates:
                    output_window.update_status(
                        f"Partially completed ({len(successful_updates)}/{len(versions)})",
                        COLORS["warning"],
                    )
                else:
                    output_window.update_status(
                        "All updates completed successfully", COLORS["success"]
                    )

                # Add final buttons
                output_window.add_final_buttons(
                    copy_text=(
                        output_window.text_area.get("1.0", "end-1c")
                        if output_window.text_area
                        else ""
                    )
                )

            except asyncio.CancelledError:
                logger.info("Edit run_tests was cancelled for %s", project_group.name)
                if output_window:
                    output_window.update_status("Operation cancelled", COLORS["error"])
                raise
            except Exception as e:
                logger.exception("Error editing run_tests for %s", project_group.name)
                if output_window:
                    output_window.update_status("Error occurred", COLORS["error"])
                    output_window.append_output(f"\nError: {str(e)}\n")
                else:
                    self.window.after(
                        0,
                        lambda: messagebox.showerror(
                            "Edit run_tests Error",
                            f"Error editing run_tests.sh: {str(e)}",
                        ),
                    )

        # Run the async operation
        task_manager.run_task(
            edit_run_tests_async(), task_name=f"edit-run-tests-{project_group.name}"
        )

    def _generate_test_command(self, language: str, test_paths: str) -> str:
        """Generate language-specific test command"""
        config = get_config()
        TEST_COMMAND_TEMPLATES = config.test.command_templates
        DEFAULT_TEST_COMMANDS = config.test.default_commands

        if not test_paths or not test_paths.strip():
            # Use default command for the language
            return DEFAULT_TEST_COMMANDS.get(language, "pytest -vv -s tests/")
        # Use template with specific test paths
        template = TEST_COMMAND_TEMPLATES.get(language, "pytest -vv -s {test_paths}")
        return template.format(test_paths=test_paths)

    def _is_test_command_line(self, line: str, language: str) -> bool:
        """Check if a line contains a test command for the specified language"""
        TEST_COMMAND_PATTERNS = get_config().test.command_patterns

        if line.startswith("#"):
            return False

        patterns = TEST_COMMAND_PATTERNS.get(language, ["pytest"])

        # For languages with multiple patterns, check appropriately
        if language == "java":
            return "mvn" in line and "test" in line
        elif language == "typescript":
            return ("npm run build" in line and "npm test" in line) or (
                "npm test" in line
            )
        else:
            return any(pattern in line for pattern in patterns)

    def _preserve_command_prefix(
        self, old_command: str, new_command: str, language: str
    ) -> str:
        """Preserve command prefixes when updating test commands"""
        # Language-specific prefix preservation
        if language == "python":
            if "python" not in old_command or "-m pytest" not in old_command:
                return new_command
            python_prefix = old_command.split("pytest")[0] + "pytest"
            # Replace the base command but keep the prefix
            return new_command.replace("pytest", python_prefix, 1)
        elif language in {"javascript", "typescript"}:
            # Handle cases like "export CI=true && npm test"
            if "export" in old_command and "CI=true" in old_command:
                return f"export CI=true\n{new_command}"
            else:
                return new_command
        elif language == "java":
            if "mvn" not in old_command:
                return new_command
            prefix = old_command[: old_command.find("mvn")]
            return f"{prefix}{new_command}" if prefix.strip() else new_command
        else:
            # For other languages, return as-is
            return new_command

    def add_project(self, repo_url: str, project_name: str):
        """Add a new project by cloning it into all subdirectories"""

        async def add_project_async():
            output_window = None
            try:
                # Create output window for showing progress
                output_window = TerminalOutputWindow(
                    self.window,
                    f"Adding Project: {project_name}",
                    control_panel=self.control_panel,
                )
                output_window.create_window()
                output_window.update_status("Initializing...", COLORS["warning"])

                # Get all subdirectories from SOURCE_DIR
                source_path = Path(SOURCE_DIR)

                # Use project service for platform-aware directory listing
                if self.project_service:
                    try:
                        subdir_names = self.project_service._list_directory_contents(
                            str(source_path)
                        )
                        subdirs = [
                            source_path / name
                            for name in subdir_names
                            if not name.startswith(".")
                        ]
                    except Exception:
                        # Fallback to direct filesystem access
                        subdirs = [
                            d
                            for d in source_path.iterdir()
                            if d.is_dir() and not d.name.startswith(".")
                        ]
                else:
                    subdirs = [
                        d
                        for d in source_path.iterdir()
                        if d.is_dir() and not d.name.startswith(".")
                    ]

                if not subdirs:
                    output_window.update_status(
                        "Error: No subdirectories found", COLORS["error"]
                    )
                    output_window.append_output(
                        f"No subdirectories found in {SOURCE_DIR}\n"
                    )
                    return

                output_window.append_output(
                    f"Found {len(subdirs)} subdirectories to clone into:\n"
                )
                for subdir in subdirs:
                    output_window.append_output(f"  • {subdir.name}\n")
                output_window.append_output("\n")

                successful_clones = []
                failed_clones = []

                # Clone into each subdirectory
                for i, subdir in enumerate(subdirs):
                    try:
                        output_window.update_status(
                            f"Cloning into {subdir.name} ({i+1}/{len(subdirs)})",
                            COLORS["warning"],
                        )

                        target_path = subdir / project_name

                        # Check if directory already exists
                        if target_path.exists():
                            output_window.append_output(
                                f"⚠️  {subdir.name}/{project_name} already exists, skipping...\n"
                            )
                            continue

                        # Clone the repository using platform service
                        clone_success, clone_result = (
                            PlatformService.run_command_with_result(
                                "GIT_COMMANDS",
                                subkey="clone",
                                repo_url=repo_url,
                                project_name=str(target_path),
                                capture_output=True,
                                text=True,
                                timeout=300,  # 5 minute timeout
                            )
                        )

                        if clone_success:
                            successful_clones.append(f"{subdir.name}/{project_name}")
                            output_window.append_output(
                                f"✅ Cloned into {subdir.name}/{project_name}\n"
                            )
                        else:
                            failed_clones.append(
                                f"{subdir.name}: {clone_result.strip()}"
                            )
                            output_window.append_output(
                                f"❌ Failed to clone into {subdir.name}: {clone_result.strip()}\n"
                            )

                    except Exception as e:
                        # Handle timeouts and other errors
                        error_msg = str(e)
                        if "timeout" in error_msg.lower():
                            error_msg = "Clone timed out after 5 minutes"
                        failed_clones.append(f"{subdir.name}: {error_msg}")
                        output_window.append_output(
                            f"❌ Clone into {subdir.name} failed: {error_msg}\n"
                        )
                    except Exception as e:
                        failed_clones.append(f"{subdir.name}: {str(e)}")
                        output_window.append_output(
                            f"❌ Error cloning into {subdir.name}: {str(e)}\n"
                        )

                # Final summary
                output_window.append_output(f"\n" + "=" * 50 + "\n")
                output_window.append_output(f"PROJECT ADDITION SUMMARY\n")
                output_window.append_output("=" * 50 + "\n")
                output_window.append_output(f"Project name: {project_name}\n")
                output_window.append_output(f"Repository: {repo_url}\n")
                output_window.append_output(f"Total directories: {len(subdirs)}\n")
                output_window.append_output(
                    f"Successful clones: {len(successful_clones)}\n"
                )
                output_window.append_output(f"Failed clones: {len(failed_clones)}\n")

                if successful_clones:
                    output_window.append_output(f"\nSuccessful clones:\n")
                    for clone in successful_clones:
                        output_window.append_output(f"  • {clone}\n")

                if failed_clones:
                    output_window.append_output(f"\nFailed clones:\n")
                    for clone in failed_clones:
                        output_window.append_output(f"  • {clone}\n")

                # Set final status
                if failed_clones:
                    output_window.update_status(
                        f"Partially completed ({len(successful_clones)}/{len(subdirs)})",
                        COLORS["warning"],
                    )
                else:
                    output_window.update_status(
                        "All clones completed successfully", COLORS["success"]
                    )

                # Add final buttons
                output_window.add_final_buttons(
                    copy_text=(
                        output_window.text_area.get("1.0", "end-1c")
                        if output_window.text_area
                        else ""
                    ),
                    additional_buttons=[
                        {
                            "text": "Refresh Projects",
                            "command": lambda: (
                                (
                                    self.control_panel.refresh_projects()
                                    if self.control_panel
                                    else None
                                ),
                                output_window.destroy(),
                            ),
                            "style": "refresh",
                        }
                    ],
                )

            except asyncio.CancelledError:
                logger.info("Add project was cancelled for %s", project_name)
                if output_window:
                    output_window.update_status("Operation cancelled", COLORS["error"])
                raise
            except Exception as e:
                logger.exception("Error adding project %s", project_name)
                if output_window:
                    output_window.update_status("Error occurred", COLORS["error"])
                    output_window.append_output(f"\nError: {str(e)}\n")
                else:
                    self.window.after(
                        0,
                        lambda: messagebox.showerror(
                            "Add Project Error", f"Error adding project: {str(e)}"
                        ),
                    )

        # Run the async operation
        task_manager.run_task(
            add_project_async(), task_name=f"add-project-{project_name}"
        )

    def checkout_commit_callback(
        self, project_path, project_name, commit_hash, git_window
    ):
        """Handle commit checkout with proper async pattern"""

        async def checkout_async():
            try:
                if git_window:
                    git_window.update_status(
                        "Checking out commit...", COLORS["warning"]
                    )

                # Use git service to checkout the commit
                checkout_result = await self.git_service.checkout_commit(
                    Path(project_path), commit_hash
                )

                if checkout_result.is_success:
                    success_message = f"✅ Successfully checked out commit {commit_hash[:8]} in {project_name}"
                    if git_window:
                        git_window.update_status(
                            "Checkout completed", COLORS["success"]
                        )

                    # Show success notification
                    self.window.after(
                        0,
                        lambda: messagebox.showinfo(
                            "Checkout Complete", success_message
                        ),
                    )
                    # Close the git window after successful checkout
                    if git_window:
                        self.window.after(100, git_window.destroy)
                else:
                    error_message = f"❌ Failed to checkout commit {commit_hash[:8]}: {checkout_result.error.message}"
                    if git_window:
                        git_window.update_status("Checkout failed", COLORS["error"])

                    self.window.after(
                        0,
                        lambda: messagebox.showerror("Checkout Failed", error_message),
                    )

            except Exception as e:
                error_message = f"❌ Error during checkout: {str(e)}"
                logger.exception(
                    f"Error checking out commit {commit_hash} in {project_name}"
                )

                if git_window:
                    git_window.update_status("Checkout error", COLORS["error"])

                self.window.after(
                    0, lambda: messagebox.showerror("Checkout Error", error_message)
                )

        # Run the checkout operation
        task_manager.run_task(
            checkout_async(), task_name=f"checkout-{project_name}-{commit_hash[:8]}"
        )
