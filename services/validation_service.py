"""
Service for validation operations - Archive all versions and run validation
"""

import os
import shutil
import logging
from pathlib import Path
from typing import Callable, Tuple, List

from services.platform_service import PlatformService
from services.file_service import FileService
from services.project_service import ProjectService
from services.project_group_service import ProjectGroup
from utils.async_utils import run_subprocess_streaming_async, run_in_executor

logger = logging.getLogger(__name__)


class ValidationService:
    """Service for validation operations - Async version"""

    def __init__(self):
        self.platform_service = PlatformService()
        self.file_service = FileService()
        self.project_service = ProjectService()

    async def archive_and_validate_project_group(
        self,
        project_group: ProjectGroup,
        output_callback: Callable[[str], None],
        status_callback: Callable[[str, str], None],
    ) -> Tuple[bool, str]:
        """
        Archive all versions of a project group and run validation
        Returns (success, raw_output)
        """
        try:
            status_callback("Preparing validation...", "#f39c12")
            output_callback(f"=== VALIDATION PROCESS FOR {project_group.name} ===\n\n")

            # Get validation tool path
            validation_tool_path = Path("validation-tool").resolve()
            codebases_path = validation_tool_path / "codebases"

            if not validation_tool_path.exists():
                error_msg = "Validation tool directory not found"
                output_callback(f"❌ {error_msg}\n")
                status_callback("Validation tool not found", "#e74c3c")
                return False, error_msg

            # Create codebases directory if it doesn't exist
            codebases_path.mkdir(exist_ok=True)

            # Clear existing archives in codebases directory
            output_callback(
                "🧹 Clearing existing archives from validation directory...\n"
            )
            try:
                for existing_file in codebases_path.glob("*.zip"):
                    existing_file.unlink()
                    output_callback(f"   Removed: {existing_file.name}\n")
            except Exception as e:
                output_callback(
                    f"⚠️ Warning: Could not clear some existing files: {e}\n"
                )

            output_callback(f"📁 Using codebases directory: {codebases_path}\n\n")

            # Get all versions of the project
            versions = project_group.get_all_versions()
            if not versions:
                error_msg = "No versions found for this project"
                output_callback(f"❌ {error_msg}\n")
                status_callback("No versions found", "#e74c3c")
                return False, error_msg

            output_callback(f"🔍 Found {len(versions)} versions to archive:\n")
            for version in versions:
                # Show the alias if it exists
                alias = self.project_service.get_folder_alias(version.parent)
                alias_text = f" ({alias})" if alias else ""
                output_callback(f"  • {version.parent}{alias_text}: {version.name}\n")
            output_callback("\n")

            archived_files = []

            # Archive each version using the same process as individual archive
            for i, project in enumerate(versions):
                status_callback(
                    f"Archiving {project.parent} ({i+1}/{len(versions)})", "#f39c12"
                )

                # First, scan for directories and files that need cleanup
                cleanup_needed_dirs, cleanup_needed_files = (
                    await self.file_service.scan_for_cleanup_items(project.path)
                )

                # If cleanup items found, prompt would normally happen here, but for validation
                # we'll clean up automatically to ensure clean archives
                if cleanup_needed_dirs or cleanup_needed_files:
                    output_callback(
                        f"🧹 Cleaning up {project.parent} before archiving...\n"
                    )
                    cleanup_items = []

                    if cleanup_needed_dirs:
                        cleanup_items.extend(
                            [
                                f"  • {os.path.relpath(d, project.path)} (dir)"
                                for d in cleanup_needed_dirs
                            ]
                        )
                    if cleanup_needed_files:
                        cleanup_items.extend(
                            [
                                f"  • {os.path.relpath(f, project.path)} (file)"
                                for f in cleanup_needed_files
                            ]
                        )

                    for item in cleanup_items[:5]:  # Show first 5 items
                        output_callback(f"   {item}\n")
                    if len(cleanup_items) > 5:
                        output_callback(
                            f"   ... and {len(cleanup_items) - 5} more items\n"
                        )

                    deleted_items = await self.file_service.cleanup_project_items(
                        project.path
                    )
                    if deleted_items:
                        output_callback(f"   ✅ Cleaned {len(deleted_items)} items\n")

                # Get the proper archive name using ProjectService (includes aliases)
                archive_name = self.project_service.get_archive_name(
                    project.parent, project.name
                )
                output_callback(f"📦 Creating archive: {archive_name}\n")

                # Create archive
                success, error_msg = await self.file_service.create_archive(
                    project.path, archive_name
                )

                if not success:
                    output_callback(
                        f"❌ Failed to create archive for {project.parent}: {error_msg}\n"
                    )
                    continue

                # Move archive to validation-tool/codebases
                source_archive = project.path / archive_name
                target_archive = codebases_path / archive_name

                if source_archive.exists():
                    try:
                        # Remove existing archive if it exists (shouldn't happen after clearing)
                        if target_archive.exists():
                            target_archive.unlink()

                        shutil.move(str(source_archive), str(target_archive))
                        archived_files.append(archive_name)
                        output_callback(
                            f"✅ Moved {archive_name} to validation directory\n"
                        )
                    except Exception as e:
                        output_callback(f"❌ Failed to move {archive_name}: {str(e)}\n")
                else:
                    output_callback(f"❌ Archive file not found: {source_archive}\n")

                output_callback("\n")

            if not archived_files:
                error_msg = "No archives were successfully created"
                output_callback(f"❌ {error_msg}\n")
                status_callback("Archiving failed", "#e74c3c")
                return False, error_msg

            output_callback(
                f"✅ Successfully archived {len(archived_files)} versions\n"
            )
            output_callback("Archives in validation directory:\n")
            for archive in archived_files:
                output_callback(f"  • {archive}\n")
            output_callback("\n")

            # Now run validation
            status_callback("Running validation...", "#3498db")
            output_callback("=== RUNNING VALIDATION ===\n")

            validation_success, validation_output = await self._run_validation_script(
                validation_tool_path, output_callback
            )

            if validation_success:
                status_callback("Validation completed successfully", "#27ae60")
                output_callback("\n✅ Validation process completed successfully!\n")
            else:
                status_callback("Validation completed with issues", "#f39c12")
                output_callback("\n⚠️ Validation completed but there may be issues\n")

            return True, validation_output

        except Exception as e:
            logger.exception("Error during validation process")
            error_msg = f"Error during validation process: {str(e)}"
            output_callback(f"❌ {error_msg}\n")
            status_callback("Validation error", "#e74c3c")
            return False, error_msg

    async def _run_validation_script(
        self,
        validation_tool_path: Path,
        output_callback: Callable[[str], None],
    ) -> Tuple[bool, str]:
        """
        Run the appropriate validation script based on platform
        Returns (success, raw_output)
        """
        try:
            # Determine which validation script to run
            if self.platform_service.is_windows():
                script_name = "run_validation.bat"
                script_path = validation_tool_path / script_name
                cmd_list = [str(script_path)]
                use_shell = True
            else:
                script_name = "run_validation.sh"
                script_path = validation_tool_path / script_name
                # Make sure script is executable
                await run_in_executor(os.chmod, str(script_path), 0o755)
                cmd_list = ["bash", str(script_path)]
                use_shell = False

            if not script_path.exists():
                error_msg = f"Validation script not found: {script_path}"
                output_callback(f"❌ {error_msg}\n")
                return False, error_msg

            output_callback(f"🚀 Running validation script: {script_name}\n")
            output_callback(f"Working directory: {validation_tool_path}\n")
            output_callback("=" * 50 + "\n")

            # Run the validation script with streaming output
            # For Windows, we need to handle the pause commands by providing input
            if self.platform_service.is_windows():
                return_code, raw_output = await self._run_windows_script_with_input(
                    cmd_list[0], str(validation_tool_path), output_callback
                )
            else:
                return_code, raw_output = await run_subprocess_streaming_async(
                    cmd_list,
                    shell=use_shell,
                    cwd=str(validation_tool_path),
                    output_callback=output_callback,
                )

            output_callback("\n" + "=" * 50 + "\n")
            output_callback(
                f"Validation script finished with exit code: {return_code}\n"
            )

            # Check for results file
            results_file = validation_tool_path / "output" / "validation_results.csv"
            if results_file.exists():
                output_callback(f"📊 Results saved to: {results_file}\n")
                # Read and display a summary of results
                try:
                    with open(results_file, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                        if len(lines) > 1:  # More than just header
                            output_callback(
                                f"📈 Generated {len(lines) - 1} result entries\n"
                            )
                except Exception as e:
                    output_callback(f"⚠️ Could not read results file: {e}\n")
            else:
                output_callback("⚠️ No results file generated\n")

            # Consider it successful if exit code is 0 or if results were generated
            success = return_code == 0 or results_file.exists()
            return success, raw_output

        except Exception as e:
            logger.exception("Error running validation script")
            error_msg = f"Error running validation script: {str(e)}"
            output_callback(f"❌ {error_msg}\n")
            return False, error_msg

    async def _run_windows_script_with_input(
        self,
        script_path: str,
        working_dir: str,
        output_callback: Callable[[str], None],
    ) -> Tuple[int, str]:
        """
        Run Windows validation script and automatically handle pause prompts
        Returns (return_code, raw_output)
        """
        import asyncio
        import subprocess

        try:
            # Start the process using create_subprocess_shell for Windows batch files
            process = await asyncio.create_subprocess_shell(
                f'"{script_path}"',
                cwd=working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
            )

            raw_output = ""

            # Read output line by line and handle pause prompts
            while True:
                try:
                    # Read line with timeout (as bytes)
                    line_bytes = await asyncio.wait_for(
                        process.stdout.readline(), timeout=1.0
                    )
                    if not line_bytes:
                        break

                    # Convert bytes to string and strip
                    try:
                        line = line_bytes.decode("utf-8", errors="replace").strip()
                    except UnicodeDecodeError:
                        line = line_bytes.decode("latin-1", errors="replace").strip()

                    if line:
                        output_callback(f"{line}\n")
                        raw_output += line + "\n"

                        # Check for pause prompts and send input
                        line_lower = line.lower()
                        if any(
                            prompt in line_lower
                            for prompt in [
                                "press any key",
                                "pause",
                                "any key to close",
                                "any key to continue",
                            ]
                        ):
                            output_callback("🔄 Automatically continuing...\n")
                            # Send a newline to continue (as bytes)
                            process.stdin.write(b"\n")
                            await process.stdin.drain()

                except asyncio.TimeoutError:
                    # Check if process is still running
                    if process.returncode is not None:
                        break
                    continue
                except Exception as e:
                    logger.debug(f"Error reading process output: {e}")
                    break

            # Wait for process to complete
            return_code = await process.wait()

            # Read any remaining output
            try:
                remaining_output_bytes, _ = await asyncio.wait_for(
                    process.communicate(), timeout=2.0
                )
                if remaining_output_bytes:
                    try:
                        remaining_output = remaining_output_bytes.decode(
                            "utf-8", errors="replace"
                        )
                    except UnicodeDecodeError:
                        remaining_output = remaining_output_bytes.decode(
                            "latin-1", errors="replace"
                        )
                    output_callback(remaining_output)
                    raw_output += remaining_output
            except asyncio.TimeoutError:
                pass

            return return_code, raw_output

        except Exception as e:
            logger.exception("Error running Windows script with input handling")
            output_callback(f"❌ Error running script: {str(e)}\n")
            return 1, str(e)
