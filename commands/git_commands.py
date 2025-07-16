"""
Git-specific command implementations
Handles Git repository viewing and checkout operations
"""

import asyncio
from typing import Dict, Any

from utils.async_base import AsyncCommand, AsyncResult, ProcessError
from models.project import Project
from services.project_group_service import ProjectGroup
from config.config import get_config

COLORS = get_config().gui.colors


class GitViewCommand(AsyncCommand):
    """Standardized command for Git operations with real-time window coordination"""

    def __init__(
        self,
        project: Project,
        git_service,
        window=None,
        checkout_callback=None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.project = project
        self.git_service = git_service
        self.window = window
        self.checkout_callback = checkout_callback
        self.git_window = None

    async def execute(self) -> AsyncResult[Dict[str, Any]]:
        """Execute the Git view command with real-time streaming"""
        try:
            # Import here to avoid circular imports
            from gui import GitCommitWindow

            self._update_progress("Initializing Git view...", "info")

            # Create git window immediately with loading state
            def create_git_window():
                # Create a wrapper callback that passes the git window reference
                def checkout_wrapper(commit_hash):
                    if self.checkout_callback:
                        # Call the original callback with the git window reference
                        self.checkout_callback(commit_hash, self.git_window)

                self.git_window = GitCommitWindow(
                    self.window,
                    self.project.name,
                    [],  # Start with empty commits
                    checkout_wrapper,
                    git_service=self.git_service,
                    project_path=self.project.path,
                    current_commit_hash=None,  # Will be set later when we get repo info
                )
                # Show window immediately with loading animation
                self.git_window.create_window_with_loading(True, "Initializing...")

            if self.window:
                self.window.after(0, create_git_window)
                await asyncio.sleep(0.1)  # Wait for window creation

            # Update status to show fetching
            if self.git_window:
                self.git_window.update_status("Fetching latest commits...")

            self._update_progress("Fetching latest commits...", "info")

            # Fetch latest commits
            fetch_result = await self.git_service.fetch_latest_commits(
                self.project.path
            )

            fetch_success = fetch_result.is_success
            fetch_message = fetch_result.message or (
                fetch_result.error.message if fetch_result.error else "Unknown error"
            )

            if (
                not fetch_success
                and "No remote repository" not in fetch_message
                and self.git_window
            ):
                self.git_window.update_status(f"Fetch warning: {fetch_message}")

            # Update status to show loading commits
            if self.git_window:
                self.git_window.update_status("Loading commit history...")

            self._update_progress("Loading commit history...", "info")

            # Get current repository information (including current commit)
            repo_info_result = await self.git_service.get_repository_info(
                self.project.path
            )
            current_commit_hash = None
            if repo_info_result.is_success:
                current_commit_hash = repo_info_result.data.current_commit
                self._update_progress(f"Current commit: {current_commit_hash}", "info")

            # Get commits
            commits_result = await self.git_service.get_git_commits(self.project.path)

            if commits_result.is_error:
                error_msg = commits_result.error.message
                if self.git_window:
                    self.git_window.update_with_error(error_msg)
                return AsyncResult.error_result(commits_result.error)

            commits = commits_result.data or []

            if not commits:
                if self.git_window:
                    self.git_window.update_with_no_commits()
                return AsyncResult.success_result(
                    {
                        "message": "No commits found in repository",
                        "project_name": self.project.name,
                        "commits": [],
                        "current_commit": current_commit_hash,
                        "git_window_created": self.git_window is not None,
                    }
                )

            # Update window with commits and current commit hash
            if self.git_window:
                self.git_window.update_with_commits(commits, current_commit_hash)
                status_text = f"Loaded all {len(commits)} commits from repository"
                if current_commit_hash:
                    status_text += f" (current: {current_commit_hash})"
                self.git_window.update_status(status_text)

            result_data = {
                "message": f"Git information loaded for {self.project.name}",
                "project_path": str(self.project.path),
                "project_name": self.project.name,
                "fetch_success": fetch_success,
                "fetch_message": fetch_message,
                "commits": commits,
                "current_commit": current_commit_hash,
                "git_window_created": self.git_window is not None,
            }

            self._update_progress(f"Loaded {len(commits)} commits", "success")

            return AsyncResult.success_result(
                result_data,
                message=f"Successfully loaded Git information for {self.project.name}",
            )

        except Exception as e:
            self.logger.exception(f"Git command failed for {self.project.name}")
            error_msg = f"Error accessing git repository: {str(e)}"
            if self.git_window:
                self.git_window.update_with_error(error_msg)

            return AsyncResult.error_result(
                ProcessError(f"Git operation failed: {str(e)}", error_code="GIT_ERROR")
            )


class GitCheckoutAllCommand(AsyncCommand):
    """Standardized command for Git checkout operations across all project versions"""

    def __init__(
        self,
        project_group: ProjectGroup,
        git_service,
        window=None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.project_group = project_group
        self.git_service = git_service
        self.window = window
        self.git_window = None

    async def execute(self) -> AsyncResult[Dict[str, Any]]:
        """Execute the Git checkout all command with real-time streaming"""
        try:
            # Import here to avoid circular imports
            from gui.popup_windows import GitCheckoutAllWindow

            self._update_progress("Initializing Git checkout all view...", "info")

            # Get all project versions
            all_versions = self.project_group.get_all_versions()
            if not all_versions:
                return AsyncResult.error_result(
                    ProcessError("No project versions found", error_code="NO_VERSIONS")
                )

            # Use the first version to get the git commits (they should all be the same repo)
            representative_project = all_versions[0]

            # Create git checkout all window immediately with loading state
            def create_git_window():
                def checkout_all_callback(commit_hash):
                    # This will handle checkout to all versions
                    self._checkout_all_versions(commit_hash, all_versions)

                self.git_window = GitCheckoutAllWindow(
                    self.window,
                    self.project_group.name,
                    [],  # Start with empty commits
                    checkout_all_callback,
                    git_service=self.git_service,
                    project_group=self.project_group,
                    all_versions=all_versions,
                )
                # Show window immediately with loading animation
                self.git_window.create_window_with_loading(True, "Initializing...")

            if self.window:
                self.window.after(0, create_git_window)
                await asyncio.sleep(0.1)  # Wait for window creation

            # Update status to show fetching
            if self.git_window:
                self.git_window.update_status("Fetching latest commits...")

            self._update_progress("Fetching latest commits...", "info")

            # Fetch latest commits from the representative project
            fetch_result = await self.git_service.fetch_latest_commits(
                representative_project.path
            )

            fetch_success = fetch_result.is_success
            fetch_message = fetch_result.message or (
                fetch_result.error.message if fetch_result.error else "Unknown error"
            )

            if (
                not fetch_success
                and "No remote repository" not in fetch_message
                and self.git_window
            ):
                self.git_window.update_status(f"Fetch warning: {fetch_message}")

            # Update status to show loading commits
            if self.git_window:
                self.git_window.update_status("Loading commit history...")

            self._update_progress("Loading commit history...", "info")

            # Get commits from the representative project
            commits_result = await self.git_service.get_git_commits(
                representative_project.path
            )

            if commits_result.is_error:
                error_msg = commits_result.error.message
                if self.git_window:
                    self.git_window.update_with_error(error_msg)
                return AsyncResult.error_result(commits_result.error)

            commits = commits_result.data or []

            if not commits:
                if self.git_window:
                    self.git_window.update_with_no_commits()
                return AsyncResult.success_result(
                    {
                        "message": "No commits found in repository",
                        "project_group_name": self.project_group.name,
                        "commits": [],
                        "git_window_created": self.git_window is not None,
                    }
                )

            # Update window with commits (streaming complete)
            if self.git_window:
                self.git_window.update_with_commits(commits)
                self.git_window.update_status(
                    f"Loaded all {len(commits)} commits. Ready to checkout to {len(all_versions)} versions."
                )

            result_data = {
                "message": f"Git information loaded for {self.project_group.name}",
                "project_group_name": self.project_group.name,
                "fetch_success": fetch_success,
                "fetch_message": fetch_message,
                "commits": commits,
                "all_versions": all_versions,
                "git_window_created": self.git_window is not None,
            }

            self._update_progress(
                f"Loaded {len(commits)} commits for {len(all_versions)} versions",
                "success",
            )

            return AsyncResult.success_result(
                result_data,
                message=f"Successfully loaded Git information for {self.project_group.name}",
            )

        except Exception as e:
            self.logger.exception(
                f"Git checkout all command failed for {self.project_group.name}"
            )
            error_msg = f"Error accessing git repository: {str(e)}"
            if self.git_window:
                self.git_window.update_with_error(error_msg)

            return AsyncResult.error_result(
                ProcessError(
                    f"Git checkout all operation failed: {str(e)}",
                    error_code="GIT_CHECKOUT_ALL_ERROR",
                )
            )

    def _checkout_all_versions(self, commit_hash: str, all_versions):
        """Handle checkout to all versions of the project"""
        # Import here to avoid circular imports
        import tkinter as tk
        from tkinter import messagebox

        # Confirm checkout to all versions
        version_names = [f"{v.parent}/{v.name}" for v in all_versions]
        versions_text = "\n".join([f"• {name}" for name in version_names[:10]])
        if len(version_names) > 10:
            versions_text += f"\n... and {len(version_names) - 10} more versions"

        response = messagebox.askyesno(
            "Confirm Checkout All",
            f"Are you sure you want to checkout ALL versions to commit {commit_hash}?\n\n"
            f"This will affect {len(all_versions)} project versions:\n{versions_text}\n\n"
            f"⚠️  Any uncommitted changes in these projects may be lost.\n\n"
            f"Continue with checkout to all versions?",
        )

        if not response:
            return

        # Run checkout as async task for all versions
        async def checkout_all_async():
            try:
                # Import here to avoid circular imports
                from gui import TerminalOutputWindow

                # Create terminal window for showing progress
                terminal_window = TerminalOutputWindow(
                    self.window, f"Git Checkout All - {self.project_group.name}"
                )
                terminal_window.create_window()
                terminal_window.update_status(
                    "Starting checkout to all versions...", COLORS["warning"]
                )

                terminal_window.append_output(
                    f"🔀 Git Checkout All - {self.project_group.name}\n"
                )
                terminal_window.append_output(f"Target commit: {commit_hash}\n")
                terminal_window.append_output(
                    f"Versions to checkout: {len(all_versions)}\n\n"
                )

                successful_checkouts = []
                failed_checkouts = []

                # Checkout each version
                for i, project in enumerate(all_versions):
                    terminal_window.update_status(
                        f"Processing {project.parent}/{project.name} ({i+1}/{len(all_versions)})",
                        COLORS["warning"],
                    )
                    terminal_window.append_output(
                        f"📁 Processing {project.parent}/{project.name}...\n"
                    )

                    # First, fetch the latest commits to ensure this version knows about the target commit
                    terminal_window.append_output(f"   🔄 Fetching latest commits...\n")
                    fetch_result = await self.git_service.fetch_latest_commits(
                        project.path
                    )

                    if fetch_result.is_success:
                        terminal_window.append_output(f"   ✅ Fetch completed\n")
                    else:
                        # Fetch failed, but we can still try to checkout if it's a local commit
                        fetch_error = (
                            fetch_result.error.message
                            if fetch_result.error
                            else "Unknown fetch error"
                        )
                        if "No remote repository" in fetch_error:
                            terminal_window.append_output(
                                f"   ℹ️  No remote configured, proceeding with local commits\n"
                            )
                        else:
                            terminal_window.append_output(
                                f"   ⚠️  Fetch failed: {fetch_error}\n"
                            )
                            terminal_window.append_output(
                                f"   ℹ️  Attempting checkout with existing commits...\n"
                            )

                    # Now perform the checkout
                    terminal_window.append_output(
                        f"   🔀 Checking out to {commit_hash}...\n"
                    )
                    checkout_result = await self.git_service.checkout_commit(
                        project.path, commit_hash
                    )
                    success = checkout_result.is_success
                    message = checkout_result.message or (
                        checkout_result.error.message
                        if checkout_result.error
                        else "Unknown error"
                    )

                    if success:
                        terminal_window.append_output(f"   ✅ {message}\n")
                        successful_checkouts.append(f"{project.parent}/{project.name}")
                    else:
                        # Check if the error is due to unknown commit (after fetch failure)
                        if (
                            "pathspec" in message.lower()
                            and "did not match" in message.lower()
                        ):
                            terminal_window.append_output(
                                f"   ❌ Commit {commit_hash} not found in this version\n"
                            )
                            failed_checkouts.append(
                                f"{project.parent}/{project.name} (commit not found)"
                            )
                        # Check if the error is due to local changes
                        elif (
                            "would be overwritten" in message
                            or "local changes" in message.lower()
                        ):
                            # Ask if user wants to force checkout for this specific version
                            force_response = messagebox.askyesnocancel(
                                "Local Changes Detected",
                                f"Cannot checkout {project.parent}/{project.name} because local changes would be overwritten:\n\n"
                                f"{message}\n\n"
                                f"Would you like to discard changes and force checkout for this version?\n\n"
                                f"• Yes: Force checkout this version\n"
                                f"• No: Skip this version\n"
                                f"• Cancel: Stop all checkouts",
                            )

                            if force_response is True:  # Yes - force checkout
                                terminal_window.append_output(
                                    f"   ⚠️  Forcing checkout (discarding local changes)...\n"
                                )
                                force_result = (
                                    await self.git_service.force_checkout_commit(
                                        project.path, commit_hash
                                    )
                                )
                                force_success = force_result.is_success
                                force_message = force_result.message or (
                                    force_result.error.message
                                    if force_result.error
                                    else "Unknown error"
                                )

                                if force_success:
                                    terminal_window.append_output(
                                        f"   ✅ {force_message}\n"
                                    )
                                    successful_checkouts.append(
                                        f"{project.parent}/{project.name}"
                                    )
                                else:
                                    terminal_window.append_output(
                                        f"   ❌ Force checkout failed: {force_message}\n"
                                    )
                                    failed_checkouts.append(
                                        f"{project.parent}/{project.name} (force failed: {force_message})"
                                    )
                            elif force_response is False:  # No - skip
                                terminal_window.append_output(
                                    f"   ⏭️  Skipped (preserving local changes)\n"
                                )
                                failed_checkouts.append(
                                    f"{project.parent}/{project.name} (skipped: local changes)"
                                )
                            else:  # Cancel - stop all
                                terminal_window.append_output(
                                    f"   🛑 Checkout cancelled by user\n"
                                )
                                break
                        else:
                            # Some other git error
                            terminal_window.append_output(f"   ❌ {message}\n")
                            failed_checkouts.append(
                                f"{project.parent}/{project.name} ({message})"
                            )

                # Final summary
                terminal_window.append_output("\n" + "=" * 50 + "\n")
                terminal_window.append_output("CHECKOUT ALL SUMMARY:\n")
                terminal_window.append_output(f"🎯 Target commit: {commit_hash}\n")
                terminal_window.append_output(
                    f"📊 Total versions processed: {len(all_versions)}\n"
                )
                terminal_window.append_output(
                    f"✅ Successful checkouts: {len(successful_checkouts)}\n"
                )
                terminal_window.append_output(
                    f"❌ Failed/skipped checkouts: {len(failed_checkouts)}\n"
                )

                if successful_checkouts:
                    terminal_window.append_output("\nSuccessful checkouts:\n")
                    for checkout in successful_checkouts:
                        terminal_window.append_output(f"  • {checkout}\n")

                if failed_checkouts:
                    terminal_window.append_output("\nFailed/skipped checkouts:\n")
                    for checkout in failed_checkouts:
                        terminal_window.append_output(f"  • {checkout}\n")

                # Add helpful note about the operation
                terminal_window.append_output(
                    f"\n💡 Note: Each version was updated with latest commits before checkout\n"
                )
                terminal_window.append_output(
                    f"📋 All versions that could be updated are now at commit {commit_hash}\n"
                )

                # Update final status
                if len(successful_checkouts) == len(all_versions):
                    terminal_window.update_status(
                        "All checkouts completed successfully!", COLORS["success"]
                    )
                elif successful_checkouts:
                    terminal_window.update_status(
                        "Partially completed with some failures/skips",
                        COLORS["warning"],
                    )
                else:
                    terminal_window.update_status(
                        "All checkouts failed or were skipped", COLORS["error"]
                    )

                # Add final buttons
                terminal_window.add_final_buttons(
                    copy_text=(
                        terminal_window.text_area.get("1.0", "end-1c")
                        if terminal_window.text_area
                        else ""
                    )
                )

                # Close the git window if checkout was successful for all versions
                if len(successful_checkouts) == len(all_versions) and self.git_window:
                    self.window.after(0, self.git_window.destroy)

            except asyncio.CancelledError:
                self.logger.info(
                    "Checkout all was cancelled for %s", self.project_group.name
                )
                if "terminal_window" in locals():
                    terminal_window.update_status(
                        "Operation cancelled", COLORS["error"]
                    )
                raise
            except Exception as e:
                self.logger.exception(
                    "Error during checkout all for %s", self.project_group.name
                )
                error_msg = f"Error during checkout all: {str(e)}"
                if "terminal_window" in locals():
                    terminal_window.update_status("Error occurred", COLORS["error"])
                    terminal_window.append_output(f"\nError: {error_msg}\n")

        # Import task manager and run the async operation
        from utils.async_utils import task_manager

        task_manager.run_task(
            checkout_all_async(),
            task_name=f"checkout-all-{self.project_group.name}-{commit_hash[:8]}",
        )
