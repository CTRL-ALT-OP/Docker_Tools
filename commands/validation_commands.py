"""
Validation-specific command implementations
Handles project group validation operations with complex output processing
"""

import asyncio
import re
from pathlib import Path
from typing import Dict, Any

from utils.async_base import AsyncCommand, AsyncResult, ProcessError
from services.project_group_service import ProjectGroup
from config.config import get_config

COLORS = get_config().gui.colors


class ValidateProjectGroupCommand(AsyncCommand):
    """Standardized command for project group validation with complex output processing"""

    def __init__(
        self,
        project_group: ProjectGroup,
        validation_service,
        window=None,
        async_bridge=None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.project_group = project_group
        self.validation_service = validation_service
        self.window = window
        self.async_bridge = async_bridge
        self.terminal_window = None

    async def execute(self) -> AsyncResult[Dict[str, Any]]:
        """Execute the validation command with terminal window"""
        try:
            # Import here to avoid circular imports
            from gui import TerminalOutputWindow

            self._update_progress("Starting validation process...", "info")

            # Create terminal window immediately if window is available
            if self.window and self.async_bridge:
                event_id, window_ready_event = self.async_bridge.create_sync_event()

                def create_window():
                    self.terminal_window = TerminalOutputWindow(
                        self.window, f"Validation - {self.project_group.name}"
                    )
                    self.terminal_window.create_window()
                    self.terminal_window.update_status(
                        "Starting validation...", COLORS["warning"]
                    )
                    # Signal that window is ready
                    self.async_bridge.signal_from_gui(event_id)

                self.window.after(0, create_window)
                await window_ready_event.wait()
                self.async_bridge.cleanup_event(event_id)

            # Capture all streaming output for validation ID extraction
            captured_output = []

            # Define progress callbacks that stream to terminal window
            def validation_progress_callback(message: str):
                # Capture all output for later processing
                captured_output.append(message)
                if self.terminal_window:
                    self.terminal_window.append_output(message)
                # Only update progress for significant messages, not every line
                if any(
                    keyword in message.lower()
                    for keyword in [
                        "started",
                        "building",
                        "testing",
                        "completed",
                        "failed",
                        "error",
                        "warning",
                    ]
                ):
                    self._update_progress(message.strip(), "info")

            def validation_status_callback(status: str, color: str):
                # Also capture status messages
                captured_output.append(f"STATUS: {status}\n")
                if self.terminal_window:
                    self.terminal_window.update_status(status, color)
                level = (
                    "success"
                    if color == COLORS["success"]
                    else "warning" if color == COLORS["warning"] else "error"
                )
                # Always update progress for status changes since these are significant
                self._update_progress(status, level)

            # Run validation process
            validation_result = (
                await self.validation_service.archive_and_validate_project_group(
                    self.project_group,
                    validation_progress_callback,
                    validation_status_callback,
                )
            )

            if validation_result.is_error:
                if self.terminal_window:
                    self.terminal_window.update_status(
                        "Validation failed", COLORS["error"]
                    )
                    self.terminal_window.append_output(
                        f"\n❌ Error: {validation_result.error.message}\n"
                    )
                    # Add final buttons even on error so user can copy error output
                    if self.terminal_window.text_area:
                        terminal_content = self.terminal_window.text_area.get(
                            "1.0", "end-1c"
                        )
                        self.terminal_window.add_final_buttons(
                            copy_text=terminal_content
                        )
                return AsyncResult.error_result(validation_result.error)

            # Handle partial results (validation completed with issues)
            if validation_result.is_partial and self.terminal_window:
                self.terminal_window.update_status(
                    "Validation completed with issues", COLORS["warning"]
                )
                self.terminal_window.append_output(
                    f"\n⚠️ Validation completed with some issues: {validation_result.error.message}\n"
                )

            # Combine all captured output for validation ID extraction
            full_output = "".join(captured_output)

            # Also try to get output from the validation result data
            result_output = ""
            if validation_result.data:
                if hasattr(validation_result.data, "validation_output"):
                    result_output = validation_result.data.validation_output
                elif hasattr(validation_result.data, "raw_output"):
                    result_output = validation_result.data.raw_output
                elif hasattr(validation_result.data, "get"):
                    result_output = validation_result.data.get("raw_output", "")
                else:
                    result_output = str(validation_result.data)

            # Use the most comprehensive output available
            raw_output = (
                full_output + "\n" + result_output if result_output else full_output
            )

            validation_id = self._extract_validation_id(raw_output)

            # Update terminal window with success
            if self.terminal_window:
                self.terminal_window.update_status(
                    "Validation completed successfully", COLORS["success"]
                )
                self.terminal_window.append_output(
                    "\n✅ Validation completed successfully!\n"
                )

                # Add validation ID to output if found
                if validation_id:
                    self.terminal_window.append_output(
                        f"\n📋 Validation ID: {validation_id}\n"
                    )

                # Add final buttons for complex interactions
                additional_buttons = []

                # Add validation ID copy button if we found an ID
                if validation_id:

                    def copy_validation_id():
                        try:
                            import pyperclip

                            pyperclip.copy(validation_id)
                            import tkinter.messagebox as messagebox

                            messagebox.showinfo(
                                "Copied!",
                                f"Validation ID copied to clipboard:\n{validation_id}",
                            )
                        except ImportError:
                            # Fallback for systems without pyperclip
                            self.window.clipboard_clear()
                            self.window.clipboard_append(validation_id)
                            import tkinter.messagebox as messagebox

                            messagebox.showinfo(
                                "Copied!",
                                f"Validation ID copied to clipboard:\n{validation_id}",
                            )
                        except Exception as e:
                            import tkinter.messagebox as messagebox

                            messagebox.showerror(
                                "Copy Error", f"Could not copy validation ID: {e}"
                            )

                    additional_buttons.append(
                        {
                            "text": "📋 Copy Validation ID",
                            "command": copy_validation_id,
                            "style": "git",
                        }
                    )

                # Add button to open results file if it exists
                results_file = Path("validation-tool/output/validation_results.csv")
                if results_file.exists():

                    def open_results():
                        try:
                            from services.platform_service import PlatformService

                            success, error_msg = (
                                PlatformService.run_command_with_result(
                                    "FILE_OPEN_COMMANDS", file_path=str(results_file)
                                )
                            )
                            if not success:
                                import tkinter.messagebox as messagebox

                                messagebox.showerror(
                                    "Error", f"Could not open results file: {error_msg}"
                                )
                        except Exception as e:
                            import tkinter.messagebox as messagebox

                            messagebox.showerror(
                                "Error", f"Could not open results file: {e}"
                            )

                    additional_buttons.append(
                        {
                            "text": "📊 Open Results",
                            "command": open_results,
                            "style": "archive",
                        }
                    )

                # Use the full captured output as copy text for the main copy button
                # Get current terminal content for copying
                terminal_content = ""
                if self.terminal_window.text_area:
                    terminal_content = self.terminal_window.text_area.get(
                        "1.0", "end-1c"
                    )

                copy_text = terminal_content or raw_output
                self.terminal_window.add_final_buttons(
                    copy_text=copy_text, additional_buttons=additional_buttons
                )

            result_data = {
                "message": f"Validation completed for {self.project_group.name}",
                "project_group_name": self.project_group.name,
                "success": validation_result.is_success,
                "raw_output": raw_output,
                "validation_id": validation_id,
                "terminal_created": self.terminal_window is not None,
            }

            self._update_progress("Validation completed", "success")

            return AsyncResult.success_result(
                result_data, message=f"Successfully validated {self.project_group.name}"
            )

        except Exception as e:
            self.logger.exception(
                f"Validation command failed for {self.project_group.name}"
            )
            if self.terminal_window:
                self.terminal_window.update_status("Error occurred", COLORS["error"])
                self.terminal_window.append_output(f"\n❌ Error: {str(e)}\n")

            return AsyncResult.error_result(
                ProcessError(
                    f"Validation failed: {str(e)}", error_code="VALIDATION_ERROR"
                )
            )

    def _extract_validation_id(self, raw_output: str) -> str:
        """Extract validation ID from output"""
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
