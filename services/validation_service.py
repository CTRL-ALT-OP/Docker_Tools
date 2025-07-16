"""
Validation Service - Standardized Async Version
"""

import contextlib
import os
import shutil
import logging
import asyncio
from pathlib import Path
from typing import Callable, List, Dict, Any, Optional
from dataclasses import dataclass

import requests
import json
import subprocess
import time
import os
from concurrent.futures import ThreadPoolExecutor

from services.platform_service import PlatformService
from services.file_service import FileService
from services.project_service import ProjectService
from services.project_group_service import ProjectGroup
from models.project import Project
from config.config import get_config

COMMANDS = get_config().commands.commands
FOLDER_ALIASES = get_config().project.folder_aliases
COLORS = get_config().gui.colors
from utils.async_base import (
    AsyncServiceInterface,
    ServiceResult,
    ProcessError,
    ValidationError,
    ResourceError,
    AsyncServiceContext,
)
from utils.async_utils import run_subprocess_streaming_async, run_in_executor

logger = logging.getLogger(__name__)


@dataclass
class ValidationSettings:
    """Configuration for validation operations"""

    validation_tool_path: Path
    codebases_path: Path
    auto_cleanup: bool = True
    max_parallel_archives: int = 3
    timeout_minutes: int = 30


@dataclass
class ArchiveInfo:
    """Information about an archived project"""

    project_name: str
    project_parent: str
    archive_name: str
    archive_path: Path
    archive_size: int
    alias: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of validation operation"""

    success: (
        bool  # True if all codebases passed validation according to their type criteria
    )
    archived_projects: List[ArchiveInfo]
    validation_output: str
    failed_archives: List[str]
    validation_errors: List[str]
    total_projects: int
    processing_time: float


class ValidationService(AsyncServiceInterface):
    """Standardized Validation service with consistent async interface"""

    def __init__(self):
        super().__init__("ValidationService")
        self.platform_service = PlatformService()
        self.file_service = FileService()
        self.project_service = ProjectService()
        self._streaming_task = None  # Store reference to background streaming task

    def _determine_codebase_type(self, project: Project) -> str:
        """Determine codebase type based on project parent directory"""
        parent_lower = project.parent.lower()

        # Check each category in FOLDER_ALIASES
        for category, aliases in FOLDER_ALIASES.items():
            for alias in aliases:
                if alias.lower() in parent_lower:
                    # Map category to validation type
                    if category == "preedit":
                        return "preedit"
                    elif category.startswith("postedit"):
                        return "postedit"
                    elif category == "rewrite":
                        return "rewrite"

        # Default to rewrite if no match found
        return "rewrite"

    def _determine_codebase_type_from_filename(self, filename: str) -> str:
        """Determine codebase type from ZIP filename when project info is not available"""
        filename_lower = filename.lower()

        # Check each category in FOLDER_ALIASES
        for category, aliases in FOLDER_ALIASES.items():
            for alias in aliases:
                if alias.lower() in filename_lower:
                    # Map category to validation type
                    if category == "preedit":
                        return "preedit"
                    elif category.startswith("postedit"):
                        return "postedit"
                    elif category == "rewrite":
                        return "rewrite"

        # Default to rewrite if no match found
        return "rewrite"

    async def health_check(self) -> ServiceResult[Dict[str, Any]]:
        """Check Validation service health"""
        async with self.operation_context("health_check", timeout=30.0) as ctx:
            try:
                # Check validation tool availability
                validation_tool_path = Path("validation-tool").resolve()
                validation_tool_exists = validation_tool_path.exists()

                # Check codebases directory
                codebases_path = validation_tool_path / "codebases"
                codebases_exists = codebases_path.exists()

                # Test file service health
                file_service_health = await self.file_service.health_check()

                health_info = {
                    "status": (
                        "healthy"
                        if all(
                            [
                                validation_tool_exists,
                                file_service_health.is_success,
                            ]
                        )
                        else "degraded"
                    ),
                    "validation_tool_available": validation_tool_exists,
                    "validation_tool_path": str(validation_tool_path),
                    "codebases_directory_exists": codebases_exists,
                    "file_service_healthy": file_service_health.is_success,
                    "platform": self.platform_service.get_platform(),
                }

                if health_info["status"] == "healthy":
                    return ServiceResult.success(health_info)
                error = ResourceError("Validation service is in degraded state")
                return ServiceResult.error(error)

            except Exception as e:
                error = ProcessError(
                    f"Validation service health check failed: {str(e)}"
                )
                return ServiceResult.error(error)

    async def get_validation_settings(self) -> ServiceResult[ValidationSettings]:
        """Get validation settings and verify paths"""
        async with self.operation_context(
            "get_validation_settings", timeout=10.0
        ) as ctx:
            try:
                validation_tool_path = Path("validation-tool").resolve()
                codebases_path = validation_tool_path / "codebases"

                # Create codebases directory if it doesn't exist
                if not codebases_path.exists():
                    codebases_path.mkdir(parents=True)

                settings = ValidationSettings(
                    validation_tool_path=validation_tool_path,
                    codebases_path=codebases_path,
                    auto_cleanup=True,
                    max_parallel_archives=3,
                    timeout_minutes=30,
                )

                return ServiceResult.success(
                    settings,
                    message="Validation settings configured",
                    metadata={
                        "validation_tool_exists": validation_tool_path.exists(),
                        "codebases_path_exists": codebases_path.exists(),
                    },
                )

            except Exception as e:
                error = ProcessError(
                    f"Failed to configure validation settings: {str(e)}"
                )
                return ServiceResult.error(error)

    async def archive_and_validate_project_group(
        self,
        project_group: ProjectGroup,
        output_callback: Callable[[str], None],
        status_callback: Callable[[str, str], None],
        settings: Optional[ValidationSettings] = None,
    ) -> ServiceResult[ValidationResult]:
        """
        Archive all versions of a project group and run validation
        with standardized result format
        """
        start_time = asyncio.get_event_loop().time()

        # Get settings if not provided
        if settings is None:
            settings_result = await self.get_validation_settings()
            if settings_result.is_error:
                return ServiceResult.error(settings_result.error)
            settings = settings_result.data

        async with self.operation_context(
            "archive_and_validate_project_group",
            timeout=settings.timeout_minutes * 60.0,
        ) as ctx:
            try:
                status_callback("Preparing validation...", COLORS["warning"])
                output_callback(
                    f"=== VALIDATION PROCESS FOR {project_group.name} ===\n\n"
                )

                # Check if validation tool exists
                if not settings.validation_tool_path.exists():
                    status_callback("Validation tool not found", COLORS["error"])
                    return ServiceResult.error(
                        ResourceError(
                            f"Validation tool not found at: {settings.validation_tool_path}"
                        )
                    )

                # Get all versions for this project group
                versions = project_group.get_all_versions()

                if not versions:
                    status_callback("No versions found", COLORS["error"])
                    return ServiceResult.error(
                        ValidationError(
                            f"No versions found for project group: {project_group.name}"
                        )
                    )

                output_callback(f"🔍 Found {len(versions)} versions to archive:\n")
                for version in versions:
                    alias = self.project_service.get_folder_alias(version.parent)
                    alias_text = f" ({alias})" if alias else ""
                    output_callback(
                        f"  • {version.parent}{alias_text}: {version.name}\n"
                    )
                output_callback("\n")

                # Clear existing archives
                try:
                    await self._clear_existing_archives(
                        settings.codebases_path, output_callback
                    )
                except Exception as e:
                    self.logger.error(f"Error clearing existing archives: {e}")

                # Archive all versions
                archive_result = await self._archive_all_versions(
                    versions, settings, output_callback, status_callback
                )

                if archive_result.is_error:
                    status_callback("Archiving failed", COLORS["error"])
                    return ServiceResult.error(archive_result.error)

                archived_projects = archive_result.data

                if not archived_projects:
                    error = ResourceError("No archives were successfully created")
                    output_callback(f"❌ No archives created\n")
                    status_callback("Archiving failed", COLORS["error"])
                    return ServiceResult.error(error)

                output_callback(
                    f"✅ Successfully archived {len(archived_projects)} versions\n"
                )
                output_callback("Archives in validation directory:\n")
                for archive in archived_projects:
                    output_callback(f"  • {archive.archive_name}\n")
                output_callback("\n")

                # Run validation script
                output_callback("\n=== RUNNING VALIDATION ===\n")
                status_callback("Running validation...", COLORS["info"])

                validation_result = await self._run_validation_script(
                    settings.validation_tool_path, output_callback, archived_projects
                )

                if validation_result.is_error:
                    return ServiceResult.error(validation_result.error)

                raw_output, validation_errors, all_successful = validation_result.data

                # Use the validation result from the script
                success = all_successful
                failed_archives = [
                    archive.archive_name
                    for archive in archived_projects
                    if archive.archive_name in raw_output and "FAILED" in raw_output
                ]

                if success:
                    status_callback("All validations passed", COLORS["success"])
                    return ServiceResult.success(
                        ValidationResult(
                            success=True,
                            archived_projects=archived_projects,
                            validation_output=raw_output,
                            failed_archives=failed_archives,
                            validation_errors=validation_errors,
                            total_projects=len(archived_projects),
                            processing_time=time.time() - start_time,
                        ),
                        message="Validation completed successfully",
                    )
                else:
                    status_callback(
                        "Validation process completed with failures", COLORS["warning"]
                    )
                    return ServiceResult.partial(
                        ValidationResult(
                            success=False,
                            archived_projects=archived_projects,
                            validation_output=raw_output,
                            failed_archives=failed_archives,
                            validation_errors=validation_errors,
                            total_projects=len(archived_projects),
                            processing_time=time.time() - start_time,
                        ),
                        ProcessError(
                            f"Validation completed with {len(failed_archives)} failures"
                        ),
                    )

            except Exception as e:
                self.logger.exception(f"Archive and validation failed: {e}")
                # Clean up validation process if it was started
                await self._cleanup_validation_process()

                # Extract details for better error reporting
                error_details = str(e)
                if "validation" in error_details.lower():
                    error_code = "VALIDATION_ERROR"
                elif "archive" in error_details.lower():
                    error_code = "ARCHIVE_ERROR"
                else:
                    error_code = "UNKNOWN_ERROR"

                status_callback("Validation completed with issues", COLORS["warning"])
                return ServiceResult.partial(
                    ValidationResult(
                        success=False,
                        archived_projects=[],
                        validation_output=error_details,
                        failed_archives=[],
                        validation_errors=[error_details],
                        total_projects=0,
                        processing_time=time.time() - start_time,
                    ),
                    ProcessError(
                        f"Validation process encountered issues: {error_details}",
                        error_code=error_code,
                    ),
                )

    async def _clear_existing_archives(
        self, codebases_path: Path, output_callback: Callable[[str], None]
    ) -> None:
        """Clear existing archives from validation directory"""
        output_callback("🧹 Clearing existing archives from validation directory...\n")
        try:
            for existing_file in codebases_path.glob("*.zip"):
                existing_file.unlink()
                output_callback(f"   Removed: {existing_file.name}\n")
        except Exception as e:
            output_callback(f"⚠️ Warning: Could not clear some existing files: {e}\n")

        output_callback(f"📁 Using codebases directory: {codebases_path}\n\n")

    async def _archive_all_versions(
        self,
        versions: List[Project],
        settings: ValidationSettings,
        output_callback: Callable[[str], None],
        status_callback: Callable[[str, str], None],
    ) -> ServiceResult[List[ArchiveInfo]]:
        """Archive all project versions with standardized error handling"""
        archived_projects = []
        failed_archives = []

        for i, project in enumerate(versions):
            try:
                status_callback(
                    f"Archiving {project.parent} ({i+1}/{len(versions)})",
                    COLORS["warning"],
                )

                # Clean up project if needed
                if settings.auto_cleanup:
                    await self._cleanup_project_for_archive(project, output_callback)

                # Create archive
                archive_result = await self._create_project_archive(
                    project, settings.codebases_path, output_callback
                )

                if archive_result.is_success:
                    archived_projects.append(archive_result.data)
                else:
                    failed_archives.append(f"{project.parent}/{project.name}")
                    output_callback(
                        f"❌ Failed to archive {project.parent}: {archive_result.error.message}\n"
                    )

            except Exception as e:
                failed_archives.append(f"{project.parent}/{project.name}")
                output_callback(
                    f"❌ Unexpected error archiving {project.parent}: {str(e)}\n"
                )

        if not archived_projects and failed_archives:
            error = ResourceError(
                "Failed to create any archives",
            )
            return ServiceResult.error(error)
        elif failed_archives:
            error = ResourceError(
                f"Failed to archive {len(failed_archives)} projects",
            )
            return ServiceResult.partial(archived_projects, error)
        else:
            return ServiceResult.success(archived_projects)

    async def _cleanup_project_for_archive(
        self, project: Project, output_callback: Callable[[str], None]
    ) -> None:
        """Clean up project before archiving"""
        cleanup_result = await self.file_service.scan_for_cleanup_items(project.path)

        if cleanup_result.is_success and cleanup_result.data.item_count > 0:
            output_callback(f"🧹 Cleaning up {project.parent} before archiving...\n")

            scan_data = cleanup_result.data
            cleanup_items = []

            if scan_data.directories:
                cleanup_items.extend(
                    [
                        f"  • {os.path.relpath(d, project.path)} (dir)"
                        for d in scan_data.directories
                    ]
                )
            if scan_data.files:
                cleanup_items.extend(
                    [
                        f"  • {os.path.relpath(f, project.path)} (file)"
                        for f in scan_data.files
                    ]
                )

            # Show first 5 items
            for item in cleanup_items[:5]:
                output_callback(f"   {item}\n")
            if len(cleanup_items) > 5:
                output_callback(f"   ... and {len(cleanup_items) - 5} more items\n")

            # Perform cleanup
            cleanup_result = await self.file_service.cleanup_project_items(project.path)
            if cleanup_result.is_success or cleanup_result.is_partial:
                deleted_count = len(cleanup_result.data.deleted_directories) + len(
                    cleanup_result.data.deleted_files
                )
                output_callback(f"   ✅ Cleaned {deleted_count} items\n")

    async def _create_project_archive(
        self,
        project: Project,
        codebases_path: Path,
        output_callback: Callable[[str], None],
    ) -> ServiceResult[ArchiveInfo]:
        """Create archive for a single project"""
        # Get the proper archive name using ProjectService
        archive_name = self.project_service.get_archive_name(
            project.parent, project.name
        )
        output_callback(f"📦 Creating archive: {archive_name}\n")

        # Create archive
        archive_result = await self.file_service.create_archive(
            project.path, archive_name
        )

        if archive_result.is_error:
            return ServiceResult.error(archive_result.error)

        # Move archive to validation directory
        source_archive = project.path / archive_name
        target_archive = codebases_path / archive_name

        if not source_archive.exists():
            error = ResourceError(f"Archive file not found: {source_archive}")
            return ServiceResult.error(error)

        try:
            # Remove existing archive if it exists
            if target_archive.exists():
                target_archive.unlink()

            shutil.move(str(source_archive), str(target_archive))

            # Get file info
            archive_size = target_archive.stat().st_size
            alias = self.project_service.get_folder_alias(project.parent)

            archive_info = ArchiveInfo(
                project_name=project.name,
                project_parent=project.parent,
                archive_name=archive_name,
                archive_path=target_archive,
                archive_size=archive_size,
                alias=alias,
            )

            output_callback(f"✅ Moved {archive_name} to validation directory\n")
            return ServiceResult.success(archive_info)

        except Exception as e:
            error = ProcessError(f"Failed to move {archive_name}: {str(e)}")
            return ServiceResult.error(error)

    async def _stream_docker_output(
        self, process: subprocess.Popen, output_callback: Callable[[str], None]
    ):
        """Stream Docker output in real-time"""
        try:

            def read_output():
                """Read process output in a separate thread"""
                while True:
                    # Check if process is still running
                    if process.poll() is not None:
                        # Process finished, read any remaining output
                        remaining = process.stdout.read()
                        if remaining:
                            return remaining
                        break

                    # Read line by line
                    line = process.stdout.readline()
                    if line:
                        # Schedule callback in main thread
                        output_callback(line)
                    else:
                        # No data available, small sleep to prevent busy waiting
                        time.sleep(0.1)

                return None

            # Run the output reading in a thread to avoid blocking
            await run_in_executor(read_output)

        except asyncio.CancelledError:
            # Task was cancelled, this is expected during cleanup
            output_callback("🔄 Docker output streaming stopped\n")
            raise
        except Exception as e:
            output_callback(f"❌ Error streaming Docker output: {str(e)}\n")

    async def _cleanup_validation_process(self):
        """Clean up validation process and associated tasks"""
        try:
            # Cancel streaming task if it exists
            if self._streaming_task and not self._streaming_task.done():
                self._streaming_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._streaming_task
            # Clean up process reference
            if hasattr(self, "_validation_process"):
                self._validation_process = None

        except Exception as e:
            # Don't let cleanup errors propagate
            self.logger.warning(f"Error during validation process cleanup: {e}")

    async def _run_validation_script(
        self,
        validation_tool_path: Path,
        output_callback: Callable[[str], None],
        archived_projects: Optional[List[ArchiveInfo]] = None,
    ) -> ServiceResult[tuple[str, List[str]]]:
        """Run validation using the web API approach with Docker container"""
        try:
            # Check if validation service is running
            validation_url = "http://localhost:8080"
            service_running = await self._check_validation_service(validation_url)

            if not service_running:
                output_callback("🚀 Starting validation service...\n")
                # Start the validation service
                start_result = await self._start_validation_service(
                    validation_tool_path, output_callback
                )
                if not start_result:
                    error = ProcessError("Failed to start validation service")
                    return ServiceResult.error(error)

                # Wait for service to be ready
                output_callback("⏳ Waiting for validation service to be ready...\n")
                ready = await self._wait_for_service_ready(
                    validation_url, output_callback
                )
                if not ready:
                    error = ProcessError("Validation service failed to start properly")
                    return ServiceResult.error(error)
            else:
                output_callback("✅ Validation service is already running\n")

            # Give the service a moment to fully initialize
            await asyncio.sleep(2)

            # Get codebases directory
            codebases_path = validation_tool_path / "codebases"
            if not codebases_path.exists():
                error = ResourceError(
                    f"Codebases directory not found: {codebases_path}"
                )
                return ServiceResult.error(error)

            # Find all ZIP files in the codebases directory
            zip_files = list(codebases_path.glob("*.zip"))
            if not zip_files:
                error = ResourceError(
                    "No ZIP files found in codebases directory",
                )
                return ServiceResult.error(error)

            output_callback(f"🔍 Found {len(zip_files)} ZIP files to validate:\n")
            for zip_file in zip_files:
                output_callback(f"  • {zip_file.name}\n")
            output_callback("\n")

            # Create a mapping from zip filename to project info
            project_info_map = {}
            if archived_projects:
                for archive_info in archived_projects:
                    project_info_map[archive_info.archive_name] = archive_info

            # Submit all validations and collect results
            full_output = ""
            validation_errors = []
            all_successful = True

            for i, zip_file in enumerate(zip_files):
                output_callback(
                    f"🔄 Validating {zip_file.name} ({i+1}/{len(zip_files)})...\n"
                )

                # Create a temporary project object for type determination
                temp_project = None
                if archive_info := project_info_map.get(zip_file.name):
                    temp_project = Project(
                        parent=archive_info.project_parent,
                        name=archive_info.project_name,
                        path=Path("temp"),  # Not used for type determination
                        relative_path=f"{archive_info.project_parent}/{archive_info.project_name}",
                    )

                # Run validation via web API
                success, single_output, single_errors = await self._run_web_validation(
                    validation_url, zip_file, output_callback, temp_project
                )

                if success:
                    output_callback(
                        f"✅ {zip_file.name} validation completed successfully\n"
                    )
                else:
                    output_callback(f"❌ {zip_file.name} validation failed\n")
                    all_successful = False

                # Append output and errors
                full_output += f"\n=== VALIDATION RESULTS FOR {zip_file.name} ===\n"
                full_output += single_output
                full_output += "\n"

                if single_errors:
                    validation_errors.extend(single_errors)

                output_callback("\n")

            # Final summary
            failed_filenames = [err.split(":")[0] for err in validation_errors]
            successful_count = sum(
                zip_file.name not in failed_filenames  # Use .name instead of .stem
                for zip_file in zip_files
            )
            failed_count = len(zip_files) - successful_count

            output_callback(f"📋 Validation Summary:\n")
            output_callback(f"  • Total codebases: {len(zip_files)}\n")
            output_callback(f"  • Passed validation: {successful_count}\n")
            output_callback(f"  • Failed validation: {failed_count}\n")

            if all_successful:
                output_callback(
                    f"🎉 All codebases passed validation according to their type criteria!\n"
                )
            else:
                output_callback(
                    f"⚠️ {failed_count} codebase(s) failed validation. Check individual results above.\n"
                )
            return ServiceResult.success(
                (full_output, validation_errors, all_successful)
            )
        except Exception as e:
            error = ProcessError(f"Failed to run validation script: {str(e)}")
            return ServiceResult.error(error)

    async def _check_validation_service(self, validation_url: str) -> bool:
        """Check if validation service is running"""
        try:
            response = await run_in_executor(
                lambda: requests.get(f"{validation_url}/health", timeout=5)
            )
            return response.status_code == 200
        except Exception:
            return False

    async def _start_validation_service(
        self, validation_tool_path: Path, output_callback: Callable[[str], None]
    ) -> bool:
        """Start the validation service using run.bat/run.sh"""
        try:
            # First check if Docker is running
            output_callback("🐳 Checking if Docker is running...\n")
            docker_check = await self._check_docker_running()
            if not docker_check:
                output_callback(
                    "❌ Docker is not running. Please start Docker Desktop first.\n"
                )
                return False

            output_callback("✅ Docker is running!\n")

            # Determine script based on platform
            if self.platform_service.is_windows():
                script_path = validation_tool_path / "run.bat"
            else:
                script_path = validation_tool_path / "run.sh"

            if not script_path.exists():
                output_callback(f"❌ Validation script not found: {script_path}\n")
                return False

            # Start the service and monitor its output
            output_callback(f"🚀 Starting validation service with Docker Compose...\n")
            output_callback(f"📁 Working directory: {validation_tool_path}\n")
            output_callback(
                f"🔧 This may take a few minutes to build and start containers...\n\n"
            )

            # Start the process with real-time output streaming
            if self.platform_service.is_windows():
                # Use docker compose directly to get better output
                cmd = COMMANDS["DOCKER_COMMANDS"]["compose_up"]
            else:
                # Use docker compose directly to get better output
                cmd = COMMANDS["DOCKER_COMMANDS"]["compose_up"]

            # Start the process
            process = subprocess.Popen(
                cmd,
                cwd=str(validation_tool_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )

            # Store process for potential cleanup
            self._validation_process = process

            # Start a background task to stream output and store reference to avoid warnings
            self._streaming_task = asyncio.create_task(
                self._stream_docker_output(process, output_callback)
            )

            output_callback(f"🔄 Docker Compose started (PID: {process.pid})\n")
            output_callback("📋 Starting health checks while Docker builds...\n\n")

            # Give Docker a moment to start
            await asyncio.sleep(3)

            return True

        except Exception as e:
            output_callback(f"❌ Error starting validation service: {str(e)}\n")
            return False

    async def _check_docker_running(self) -> bool:
        """Check if Docker is running and available"""
        try:
            # Use docker info to check if Docker daemon is running
            result = await run_in_executor(
                lambda: subprocess.run(
                    COMMANDS["DOCKER_COMMANDS"]["info"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            )
            return result.returncode == 0
        except Exception:
            return False

    async def _wait_for_service_ready(
        self,
        validation_url: str,
        output_callback: Callable[[str], None],
        max_wait_time: int = 300,
    ) -> bool:
        """Wait for validation service to be ready"""
        start_time = time.time()
        last_status_time = start_time
        check_interval = 5

        output_callback(
            f"⏳ Waiting for validation service to be ready at {validation_url}\n"
        )
        output_callback(f"🕐 Will wait up to {max_wait_time} seconds...\n")

        attempt = 0
        while time.time() - start_time < max_wait_time:
            attempt += 1
            try:
                # Show periodic status updates
                if time.time() - last_status_time >= 30:  # Every 30 seconds
                    elapsed = int(time.time() - start_time)
                    output_callback(
                        f"⏳ Still waiting... ({elapsed}s elapsed, attempt #{attempt})\n"
                    )
                    last_status_time = time.time()

                ready = await self._check_validation_service(validation_url)
                if ready:
                    elapsed = int(time.time() - start_time)
                    output_callback(
                        f"✅ Validation service is ready! ({elapsed}s elapsed)\n"
                    )
                    return True

                # Check if Docker process is still running
                if (
                    hasattr(self, "_validation_process")
                    and self._validation_process.poll() is not None
                ):
                    output_callback(
                        "❌ Docker Compose process has stopped unexpectedly\n"
                    )
                    return False

                await asyncio.sleep(check_interval)

            except Exception as e:
                output_callback(
                    f"⚠️ Error checking service status (attempt #{attempt}): {str(e)}\n"
                )
                await asyncio.sleep(check_interval)

        elapsed = int(time.time() - start_time)
        output_callback(
            f"❌ Validation service failed to start within {max_wait_time} seconds ({elapsed}s elapsed)\n"
        )
        output_callback(
            "💡 Try running 'docker compose down' in the validation-tool directory and try again\n"
        )
        return False

    async def _run_web_validation(
        self,
        validation_url: str,
        zip_file: Path,
        output_callback: Callable[[str], None],
        project: Optional[Project] = None,
    ) -> tuple[bool, str, List[str]]:
        """Run validation via web API"""
        try:
            # Determine codebase type
            if project:
                codebase_type = self._determine_codebase_type(project)
                output_callback(
                    f"   🔍 Detected codebase type: {codebase_type} (from project: {project.parent})\n"
                )
            else:
                codebase_type = self._determine_codebase_type_from_filename(
                    zip_file.name
                )
                output_callback(
                    f"   🔍 Detected codebase type: {codebase_type} (from filename: {zip_file.name})\n"
                )

            # Upload the ZIP file
            output_callback(f"   📤 Uploading {zip_file.name}...\n")

            def upload_file():
                with open(zip_file, "rb") as f:
                    files = {"file": (zip_file.name, f, "application/zip")}
                    data = {"codebase_type": codebase_type}
                    response = requests.post(
                        f"{validation_url}/upload", files=files, data=data, timeout=30
                    )
                    return response

            response = await run_in_executor(upload_file)

            if response.status_code != 200:
                error_msg = f"Upload failed with status {response.status_code}"
                return False, error_msg, [f"{zip_file.name}: {error_msg}"]

            session_data = response.json()
            session_id = session_data.get("session_id")

            if not session_id:
                error_msg = "No session ID received from upload"
                return False, error_msg, [f"{zip_file.name}: {error_msg}"]

            output_callback(f"   🔄 Validation started (Session: {session_id})\n")

            # Poll for results
            return await self._poll_validation_results(
                validation_url, session_id, zip_file.name, output_callback
            )

        except Exception as e:
            error_msg = f"Error running web validation: {str(e)}"
            output_callback(f"   ❌ {error_msg}\n")
            return False, error_msg, [f"{zip_file.name}: {error_msg}"]

    async def _poll_validation_results(
        self,
        validation_url: str,
        session_id: str,
        filename: str,
        output_callback: Callable[[str], None],
    ) -> tuple[bool, str, List[str]]:
        """Poll for validation results until complete"""
        max_poll_time = 1800  # 30 minutes
        start_time = time.time()

        while time.time() - start_time < max_poll_time:
            try:

                def get_status():
                    return requests.get(
                        f"{validation_url}/status/{session_id}", timeout=10
                    )

                response = await run_in_executor(get_status)

                if response.status_code != 200:
                    error_msg = (
                        f"Status check failed with status {response.status_code}"
                    )
                    return False, error_msg, [f"{filename}: {error_msg}"]

                status_data = response.json()
                status = status_data.get("status", "unknown")
                progress = status_data.get("progress", 0)
                message = status_data.get("message", "")

                # Update progress
                if message:
                    output_callback(f"   📊 {progress}% - {message}\n")

                if status == "complete":
                    result = status_data.get("result", {})
                    success = result.get("validation_success", False) or (
                        result.get("build_success", False)
                        and result.get("test_success", False)
                    )

                    # Build output summary
                    output_lines = []
                    output_lines.append(
                        f"Build Success: {result.get('build_success', False)}"
                    )
                    output_lines.append(
                        f"Test Success: {result.get('test_success', False)}"
                    )
                    if result.get("error_message"):
                        output_lines.append(f"Error: {result.get('error_message')}")
                    if result.get("test_execution_time"):
                        output_lines.append(
                            f"Test Time: {result.get('test_execution_time'):.1f}s"
                        )

                    output_text = "\n".join(output_lines)
                    errors = []
                    if not success and result.get("error_message"):
                        errors.append(f"{filename}: {result.get('error_message')}")

                    return success, output_text, errors

                elif status == "error":
                    error_msg = status_data.get("error", "Unknown error")
                    return False, error_msg, [f"{filename}: {error_msg}"]

                # Continue polling
                await asyncio.sleep(5)

            except Exception as e:
                error_msg = f"Error polling results: {str(e)}"
                return False, error_msg, [f"{filename}: {error_msg}"]

        # Timeout
        error_msg = f"Validation timed out after {max_poll_time} seconds"
        return False, error_msg, [f"{filename}: {error_msg}"]

    # Backward compatibility methods
    async def validate_single_project(
        self,
        project: Project,
        output_callback: Callable[[str], None],
        status_callback: Callable[[str, str], None],
    ) -> ServiceResult[ValidationResult]:
        """Validate a single project (backward compatibility)"""
        # Create a temporary project group with just one project
        from services.project_group_service import ProjectGroup

        temp_group = ProjectGroup(project.name)
        temp_group.add_project(project)

        return await self.archive_and_validate_project_group(
            temp_group, output_callback, status_callback
        )
