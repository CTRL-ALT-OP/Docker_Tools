"""
Validation Service - Standardized Async Version
"""

import os
import shutil
import logging
import asyncio
from pathlib import Path
from typing import Callable, List, Dict, Any, Optional
from dataclasses import dataclass

from services.platform_service import PlatformService
from services.file_service import FileService
from services.project_service import ProjectService
from services.project_group_service import ProjectGroup
from models.project import Project
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

    success: bool
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
                error = ResourceError(
                    "Validation service is in degraded state", details=health_info
                )
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
                status_callback("Preparing validation...", "#f39c12")
                output_callback(
                    f"=== VALIDATION PROCESS FOR {project_group.name} ===\n\n"
                )

                # Validate validation tool
                if not settings.validation_tool_path.exists():
                    error = ResourceError(
                        "Validation tool directory not found",
                        details={"expected_path": str(settings.validation_tool_path)},
                    )
                    output_callback(
                        f"❌ Validation tool not found: {settings.validation_tool_path}\n"
                    )
                    status_callback("Validation tool not found", "#e74c3c")
                    return ServiceResult.error(error)

                # Clear existing archives
                await self._clear_existing_archives(
                    settings.codebases_path, output_callback
                )

                # Get project versions
                versions = project_group.get_all_versions()
                if not versions:
                    error = ResourceError("No versions found for this project")
                    output_callback(f"❌ No versions found\n")
                    status_callback("No versions found", "#e74c3c")
                    return ServiceResult.error(error)

                output_callback(f"🔍 Found {len(versions)} versions to archive:\n")
                for version in versions:
                    alias = self.project_service.get_folder_alias(version.parent)
                    alias_text = f" ({alias})" if alias else ""
                    output_callback(
                        f"  • {version.parent}{alias_text}: {version.name}\n"
                    )
                output_callback("\n")

                # Archive all versions
                archive_result = await self._archive_all_versions(
                    versions, settings, output_callback, status_callback
                )

                if archive_result.is_error:
                    return ServiceResult.error(archive_result.error)

                archived_projects = archive_result.data

                if not archived_projects:
                    error = ResourceError("No archives were successfully created")
                    output_callback(f"❌ No archives created\n")
                    status_callback("Archiving failed", "#e74c3c")
                    return ServiceResult.error(error)

                output_callback(
                    f"✅ Successfully archived {len(archived_projects)} versions\n"
                )
                output_callback("Archives in validation directory:\n")
                for archive in archived_projects:
                    output_callback(f"  • {archive.archive_name}\n")
                output_callback("\n")

                # Run validation
                status_callback("Running validation...", "#3498db")
                output_callback("=== RUNNING VALIDATION ===\n")

                validation_result = await self._run_validation_script(
                    settings.validation_tool_path, output_callback
                )

                processing_time = asyncio.get_event_loop().time() - start_time

                if validation_result.is_success:
                    validation_output, validation_errors = validation_result.data

                    result = ValidationResult(
                        success=True,
                        archived_projects=archived_projects,
                        validation_output=validation_output,
                        failed_archives=[],
                        validation_errors=validation_errors,
                        total_projects=len(versions),
                        processing_time=processing_time,
                    )

                    status_callback("Validation completed successfully", "#27ae60")
                    output_callback("\n✅ Validation process completed successfully!\n")

                    return ServiceResult.success(
                        result,
                        message="Validation completed successfully",
                        metadata={
                            "processing_time_minutes": round(processing_time / 60, 2),
                            "archived_count": len(archived_projects),
                            "total_projects": len(versions),
                        },
                    )
                else:
                    # Validation had issues but archives were created
                    validation_output = (
                        validation_result.error.message
                        if validation_result.error
                        else "Unknown validation error"
                    )

                    result = ValidationResult(
                        success=False,
                        archived_projects=archived_projects,
                        validation_output=validation_output,
                        failed_archives=[],
                        validation_errors=[validation_output],
                        total_projects=len(versions),
                        processing_time=processing_time,
                    )

                    status_callback("Validation completed with issues", "#f39c12")

                    # This is a partial success - archives created but validation failed
                    return ServiceResult.partial(
                        result,
                        validation_result.error,
                        message="Archives created but validation failed",
                    )

            except Exception as e:
                self.logger.exception("Unexpected error during validation")
                processing_time = asyncio.get_event_loop().time() - start_time

                error = ProcessError(f"Validation process failed: {str(e)}")
                return ServiceResult.error(error)

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
                    f"Archiving {project.parent} ({i+1}/{len(versions)})", "#f39c12"
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
                details={"failed_projects": failed_archives},
            )
            return ServiceResult.error(error)
        elif failed_archives:
            error = ResourceError(
                f"Failed to archive {len(failed_archives)} projects",
                details={"failed_projects": failed_archives},
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

    async def _run_validation_script(
        self, validation_tool_path: Path, output_callback: Callable[[str], None]
    ) -> ServiceResult[tuple[str, List[str]]]:
        """Run validation script with standardized error handling"""
        try:
            # Determine script based on platform
            if self.platform_service.is_windows():
                # Use the interactive version since non-interactive doesn't exist
                script_path = validation_tool_path / "run_validation.bat"
            else:
                script_path = validation_tool_path / "run_validation.sh"

            if not script_path.exists():
                error = ResourceError(
                    f"Validation script not found: {script_path}",
                    details={"platform": self.platform_service.get_platform()},
                )
                return ServiceResult.error(error)

            # Run the validation script
            if self.platform_service.is_windows():
                return_code, output = await self._run_windows_script_with_input(
                    str(script_path), str(validation_tool_path), output_callback
                )
            else:
                return_code, output = await self._run_unix_script(
                    str(script_path), str(validation_tool_path), output_callback
                )

            # Parse validation errors from output
            validation_errors = []
            if "ERROR" in output.upper() or "FAILED" in output.upper():
                validation_errors = [
                    line.strip()
                    for line in output.split("\n")
                    if "ERROR" in line.upper() or "FAILED" in line.upper()
                ]

            if return_code == 0:
                return ServiceResult.success((output, validation_errors))
            error = ProcessError(
                f"Validation script failed with exit code {return_code}",
                return_code=return_code,
            )
            return ServiceResult.error(error)

        except Exception as e:
            error = ProcessError(f"Failed to run validation script: {str(e)}")
            return ServiceResult.error(error)

    async def _run_windows_script_with_input(
        self,
        script_path: str,
        working_dir: str,
        output_callback: Callable[[str], None],
    ) -> tuple[int, str]:
        """Run Windows batch script with input handling for "Press any key" prompts"""

        try:
            # Run the script with input handling for "Press any key" prompts
            import asyncio
            import subprocess

            def run_subprocess_with_input():
                """Run subprocess in thread with automatic input handling"""
                try:
                    # Create subprocess with pipes for input/output
                    process = subprocess.Popen(
                        [script_path],
                        cwd=working_dir,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        bufsize=0,  # Unbuffered for real-time streaming
                        universal_newlines=True,
                    )

                    full_output = ""

                    # Handle output streaming and input when needed
                    while True:
                        # Check if process is still running
                        if process.poll() is not None:
                            # Process finished, read any remaining output
                            remaining = process.stdout.read()
                            if remaining:
                                full_output += remaining
                                if output_callback:
                                    output_callback(remaining)
                            break

                        # Try to read available data
                        try:
                            line = process.stdout.readline()
                            if line:
                                full_output += line
                                if output_callback:
                                    output_callback(line)

                                # Check for "Press any key" prompt and send input
                                if (
                                    "press any key" in line.lower()
                                    or "pause" in line.lower()
                                ):
                                    try:
                                        process.stdin.write("\n")
                                        process.stdin.flush()
                                    except Exception:
                                        # If input fails, process might have already closed
                                        pass
                            else:
                                # No data available, small sleep to prevent busy waiting
                                import time

                                time.sleep(0.1)
                        except Exception:
                            # If readline fails, small sleep and continue
                            import time

                            time.sleep(0.1)

                    # Wait for process to complete and get return code
                    return_code = process.wait()

                    # Close input pipe
                    try:
                        process.stdin.close()
                    except Exception:
                        pass

                    return return_code, full_output

                except Exception as e:
                    error_msg = f"Error running validation script: {str(e)}\n"
                    if output_callback:
                        output_callback(error_msg)
                    return 1, error_msg

            # Use run_in_executor to run the subprocess in a thread
            return await run_in_executor(run_subprocess_with_input)

        except Exception as e:
            error_msg = f"Error running validation script: {str(e)}\n"
            output_callback(error_msg)
            return 1, error_msg

    async def _run_unix_script(
        self,
        script_path: str,
        working_dir: str,
        output_callback: Callable[[str], None],
    ) -> tuple[int, str]:
        """Run Unix shell script"""
        return_code, output = await run_subprocess_streaming_async(
            ["bash", script_path],
            working_dir,
            output_callback,
            timeout=1800,  # 30 minutes
        )

        return return_code, output

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
