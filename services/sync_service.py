"""
Sync Service - Standardized Async Version
"""

import os
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from models.project import Project
from services.project_group_service import ProjectGroup
from services.project_service import ProjectService
from services.platform_service import PlatformService
from utils.async_base import (
    AsyncServiceInterface,
    ServiceResult,
    ProcessError,
    ValidationError,
    ResourceError,
    AsyncServiceContext,
)
from utils.async_utils import run_in_executor


@dataclass
class SyncOperationResult:
    """Result of a sync operation"""

    source_project: str
    target_projects: List[str]
    file_name: str
    synced_paths: List[Path]
    failed_syncs: List[str]
    success_count: int
    total_targets: int


@dataclass
class FileSyncInfo:
    """Information about a file sync operation"""

    file_path: Path
    file_size: int
    file_exists: bool
    is_readable: bool
    last_modified: float


class SyncService(AsyncServiceInterface):
    """Standardized Sync service with consistent async interface"""

    def __init__(self):
        super().__init__("SyncService")
        self.project_service = ProjectService()

    async def health_check(self) -> ServiceResult[Dict[str, Any]]:
        """Check Sync service health"""
        async with self.operation_context("health_check", timeout=10.0) as ctx:
            try:
                # Test basic file operations
                import tempfile

                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_path = Path(temp_dir)

                    # Create test source and target directories
                    source_dir = temp_path / "source"
                    target_dir = temp_path / "target"

                    # Create directories using platform service
                    source_success, source_error = (
                        await PlatformService.create_directory_async(str(source_dir))
                    )
                    target_success, target_error = (
                        await PlatformService.create_directory_async(str(target_dir))
                    )

                    if not source_success or not target_success:
                        error = ResourceError(
                            f"Failed to create test directories: {source_error or target_error}"
                        )
                        return ServiceResult.error(error)

                    # Test file creation and copy
                    test_file = source_dir / "test.txt"
                    test_content = "sync test content"
                    test_file.write_text(test_content)

                    # Test sync operation using platform service
                    target_file = target_dir / "test.txt"
                    copy_success, copy_error = await PlatformService.copy_file_async(
                        str(test_file), str(target_file), preserve_attrs=True
                    )

                    if not copy_success:
                        self.logger.warning(
                            f"Platform copy failed: {copy_error}, falling back to shutil"
                        )
                        # Fallback to shutil for test
                        shutil.copy2(test_file, target_file)
                        copy_success = True

                    # Verify sync
                    copied_content = target_file.read_text()
                    sync_successful = copied_content == test_content

                    return ServiceResult.success(
                        {
                            "status": "healthy",
                            "sync_operations": "functional",
                            "file_copy_test": sync_successful,
                            "platform_copy_test": copy_success,
                            "project_service_available": self.project_service
                            is not None,
                        }
                    )

            except Exception as e:
                error = ResourceError(f"Sync service health check failed: {str(e)}")
                return ServiceResult.error(error)

    async def get_file_info(
        self, project: Project, file_name: str
    ) -> ServiceResult[FileSyncInfo]:
        """Get information about a file in a project"""
        # Validate input
        if not file_name:
            error = ValidationError("File name cannot be empty")
            return ServiceResult.error(error)

        async with self.operation_context("get_file_info", timeout=10.0) as ctx:
            try:
                file_path = project.path / file_name

                # First try Python's built-in file existence check (more reliable)
                file_exists = file_path.exists()

                # If file doesn't exist according to pathlib, double-check with platform service
                if not file_exists:
                    platform_exists, _ = await PlatformService.check_file_exists_async(
                        str(file_path)
                    )
                    file_exists = platform_exists

                if file_exists:
                    # Get file statistics - try platform service first, then fallback to pathlib
                    stat_success, stat_output = (
                        await PlatformService.get_file_stat_async(str(file_path))
                    )

                    if stat_success:
                        # Parse platform-specific stat output
                        file_size, last_modified = self._parse_stat_output(stat_output)
                        is_readable = os.access(
                            file_path, os.R_OK
                        )  # Keep this for now as it's Python-specific
                    else:
                        # Fallback to pathlib if platform stat fails
                        try:
                            stat_info = await run_in_executor(file_path.stat)
                            file_size = stat_info.st_size
                            last_modified = stat_info.st_mtime
                            is_readable = os.access(file_path, os.R_OK)
                        except OSError:
                            file_size = 0
                            last_modified = 0.0
                            is_readable = False

                    file_info = FileSyncInfo(
                        file_path=file_path,
                        file_size=file_size,
                        file_exists=True,
                        is_readable=is_readable,
                        last_modified=last_modified,
                    )
                else:
                    file_info = FileSyncInfo(
                        file_path=file_path,
                        file_size=0,
                        file_exists=False,
                        is_readable=False,
                        last_modified=0.0,
                    )

                return ServiceResult.success(
                    file_info,
                    message=f"Retrieved file info for {file_name}",
                    metadata={
                        "project": f"{project.parent}/{project.name}",
                        "file_name": file_name,
                    },
                )

            except Exception as e:
                self.logger.exception("Unexpected error getting file info")
                error = ProcessError(f"Failed to get file info: {str(e)}")
                return ServiceResult.error(error)

    def _parse_stat_output(self, stat_output: str) -> tuple[int, float]:
        """Parse platform-specific stat output to extract file size and modification time"""
        try:
            # Remove any extra whitespace and split
            parts = stat_output.strip().split()

            if PlatformService.is_windows():
                # Windows forfiles output format: size date time
                # Size is in bytes, date/time needs parsing
                if len(parts) >= 1:
                    file_size = int(parts[0])
                    # For Windows, we'll use a simple timestamp approach
                    # This is a simplified implementation
                    last_modified = 0.0  # Default fallback
                    return file_size, last_modified
                else:
                    return 0, 0.0
            else:
                # Unix stat output format: size timestamp permissions
                if len(parts) >= 2:
                    file_size = int(parts[0])
                    last_modified = float(parts[1])
                    return file_size, last_modified
                else:
                    return 0, 0.0
        except (ValueError, IndexError):
            return 0, 0.0

    def _get_file_info_sync(self, project: Project, file_name: str) -> FileSyncInfo:
        """Synchronous implementation of file info retrieval"""
        file_path = project.path / file_name

        try:
            # First try Python's built-in file existence check (more reliable)
            file_exists = file_path.exists()

            # If file doesn't exist according to pathlib, double-check with platform service
            if not file_exists:
                platform_exists, _ = PlatformService.check_file_exists(str(file_path))
                file_exists = platform_exists

            if file_exists:
                # Get file statistics - try platform service first, then fallback to pathlib
                stat_success, stat_output = PlatformService.get_file_stat(
                    str(file_path)
                )

                if stat_success:
                    # Parse platform-specific stat output
                    file_size, last_modified = self._parse_stat_output(stat_output)
                    is_readable = os.access(
                        file_path, os.R_OK
                    )  # Keep this for now as it's Python-specific
                else:
                    # Fallback to pathlib if platform stat fails
                    try:
                        stat_info = file_path.stat()
                        file_size = stat_info.st_size
                        last_modified = stat_info.st_mtime
                        is_readable = os.access(file_path, os.R_OK)
                    except OSError:
                        file_size = 0
                        last_modified = 0.0
                        is_readable = False

                return FileSyncInfo(
                    file_path=file_path,
                    file_size=file_size,
                    file_exists=True,
                    is_readable=is_readable,
                    last_modified=last_modified,
                )
            else:
                return FileSyncInfo(
                    file_path=file_path,
                    file_size=0,
                    file_exists=False,
                    is_readable=False,
                    last_modified=0.0,
                )
        except Exception:
            return FileSyncInfo(
                file_path=file_path,
                file_size=0,
                file_exists=False,
                is_readable=False,
                last_modified=0.0,
            )

    async def sync_file_from_pre_edit(
        self, project_group: ProjectGroup, file_name: str
    ) -> ServiceResult[SyncOperationResult]:
        """
        Sync a file from the pre-edit version to all other versions in the project group
        with standardized result format
        """
        # Validate input
        if not file_name:
            error = ValidationError("File name cannot be empty")
            return ServiceResult.error(error)

        async with self.operation_context(
            "sync_file_from_pre_edit", timeout=60.0
        ) as ctx:
            try:
                # Get the pre-edit version
                pre_edit_project = self.get_pre_edit_version(project_group)
                if not pre_edit_project:
                    error = ResourceError("No pre-edit version found in project group")
                    return ServiceResult.error(error)

                # Check if the file exists in pre-edit version
                file_info_result = await self.get_file_info(pre_edit_project, file_name)
                if file_info_result.is_error:
                    return ServiceResult.error(file_info_result.error)

                file_info = file_info_result.data
                if not file_info.file_exists:
                    error = ResourceError(
                        f"File '{file_name}' not found in pre-edit version"
                    )
                    return ServiceResult.error(error)

                # Get all non-pre-edit versions to sync to
                target_projects = self.get_non_pre_edit_versions(project_group)
                if not target_projects:
                    # No targets, but this is success
                    result = SyncOperationResult(
                        source_project=f"{pre_edit_project.parent}/{pre_edit_project.name}",
                        target_projects=[],
                        file_name=file_name,
                        synced_paths=[],
                        failed_syncs=[],
                        success_count=0,
                        total_targets=0,
                    )
                    return ServiceResult.success(
                        result,
                        message=f"File '{file_name}' sync completed (no target versions found)",
                    )

                # Sync the file to all target versions
                sync_result = await run_in_executor(
                    self._sync_file_to_targets,
                    pre_edit_project,
                    target_projects,
                    file_name,
                )

                # Create result object
                result = SyncOperationResult(
                    source_project=f"{pre_edit_project.parent}/{pre_edit_project.name}",
                    target_projects=[f"{p.parent}/{p.name}" for p in target_projects],
                    file_name=file_name,
                    synced_paths=sync_result["synced_paths"],
                    failed_syncs=sync_result["failed_syncs"],
                    success_count=len(sync_result["synced_paths"]),
                    total_targets=len(target_projects),
                )

                # Determine result status
                if result.success_count == result.total_targets:
                    return ServiceResult.success(
                        result,
                        message=f"File '{file_name}' successfully synced to {result.success_count} version(s)",
                        metadata={
                            "file_size": file_info.file_size,
                            "source_modified": file_info.last_modified,
                        },
                    )
                elif result.success_count > 0:
                    # Partial success
                    error = ResourceError(
                        f"Failed to sync file to {len(result.failed_syncs)} target(s): {', '.join(result.failed_syncs)}"
                    )
                    return ServiceResult.partial(
                        result,
                        error,
                        message=f"File '{file_name}' partially synced to {result.success_count}/{result.total_targets} versions",
                    )
                else:
                    # All failed
                    error = ResourceError(
                        f"Failed to sync file '{file_name}' to any target versions: {', '.join(result.failed_syncs)}"
                    )
                    return ServiceResult.error(error)

            except Exception as e:
                self.logger.exception("Unexpected error during file sync")
                error = ProcessError(f"File sync operation failed: {str(e)}")
                return ServiceResult.error(error)

    def _sync_file_to_targets(
        self, source_project: Project, target_projects: List[Project], file_name: str
    ) -> Dict[str, Any]:
        """Synchronous implementation of file syncing to multiple targets"""
        synced_paths = []
        failed_syncs = []

        source_file = source_project.path / file_name

        for target_project in target_projects:
            try:
                target_file = target_project.path / file_name

                # Ensure target directory exists using platform service
                target_dir = str(target_file.parent)
                dir_success, dir_error = PlatformService.create_directory(target_dir)

                if not dir_success:
                    self.logger.warning(
                        "Platform directory creation failed: %s, falling back to mkdir",
                        dir_error,
                    )
                    # Fallback to pathlib
                    target_file.parent.mkdir(parents=True, exist_ok=True)

                # Copy the file using platform service
                copy_success, copy_error = PlatformService.copy_file(
                    str(source_file), str(target_file), preserve_attrs=True
                )

                if copy_success:
                    synced_paths.append(target_file)
                    self.logger.debug(
                        "Synced %s from %s to %s using platform service",
                        file_name,
                        source_project.parent,
                        target_project.parent,
                    )
                else:
                    self.logger.warning(
                        "Platform copy failed: %s, falling back to shutil", copy_error
                    )
                    # Fallback to shutil
                    shutil.copy2(source_file, target_file)
                    synced_paths.append(target_file)
                    self.logger.debug(
                        "Synced %s from %s to %s using shutil fallback",
                        file_name,
                        source_project.parent,
                        target_project.parent,
                    )

            except Exception as e:
                failed_syncs.append(target_project.parent)
                self.logger.warning(
                    "Failed to sync %s to %s: %s",
                    file_name,
                    target_project.parent,
                    str(e),
                )

        return {"synced_paths": synced_paths, "failed_syncs": failed_syncs}

    async def sync_multiple_files(
        self, project_group: ProjectGroup, file_names: List[str]
    ) -> ServiceResult[List[SyncOperationResult]]:
        """Sync multiple files from pre-edit version to all other versions"""
        # Validate input
        if not file_names:
            error = ValidationError("File names list cannot be empty")
            return ServiceResult.error(error)

        async with self.operation_context("sync_multiple_files", timeout=300.0) as ctx:
            try:
                results = []
                all_successful = True
                total_files = len(file_names)
                successful_files = 0

                for file_name in file_names:
                    sync_result = await self.sync_file_from_pre_edit(
                        project_group, file_name
                    )
                    results.append(
                        sync_result.data
                        or SyncOperationResult(
                            source_project="unknown",
                            target_projects=[],
                            file_name=file_name,
                            synced_paths=[],
                            failed_syncs=[],
                            success_count=0,
                            total_targets=0,
                        )
                    )

                    if sync_result.is_success:
                        successful_files += 1
                    elif sync_result.is_error:
                        all_successful = False

                if all_successful:
                    return ServiceResult.success(
                        results,
                        message=f"Successfully synced all {total_files} files",
                        metadata={
                            "total_files": total_files,
                            "successful_files": successful_files,
                        },
                    )
                elif successful_files > 0:
                    error = ResourceError(
                        f"Failed to sync {total_files - successful_files} files"
                    )
                    return ServiceResult.partial(
                        results,
                        error,
                        message=f"Partially synced {successful_files}/{total_files} files",
                    )
                else:
                    error = ResourceError(f"Failed to sync all {total_files} files")
                    return ServiceResult.error(error)

            except Exception as e:
                self.logger.exception("Unexpected error during multiple file sync")
                error = ProcessError(f"Multiple file sync operation failed: {str(e)}")
                return ServiceResult.error(error)

    def get_pre_edit_version(self, project_group: ProjectGroup) -> Optional[Project]:
        """Get the pre-edit version from a project group"""
        return next(
            (
                project
                for project in project_group.get_all_versions()
                if self.project_service.get_folder_alias(project.parent) == "preedit"
            ),
            None,
        )

    def get_non_pre_edit_versions(self, project_group: ProjectGroup) -> List[Project]:
        """Get all versions in a project group except the pre-edit version"""
        return [
            project
            for project in project_group.get_all_versions()
            if self.project_service.get_folder_alias(project.parent) != "preedit"
        ]

    # Backward compatibility methods
    async def has_file(self, project: Project, file_name: str) -> ServiceResult[bool]:
        """Check if a project has a file (backward compatibility)"""
        try:
            file_path = project.path / file_name

            # First try Python's built-in file existence check (more reliable)
            file_exists = file_path.exists()

            # If file doesn't exist according to pathlib, double-check with platform service
            if not file_exists:
                platform_exists, _ = await PlatformService.check_file_exists_async(
                    str(file_path)
                )
                file_exists = platform_exists

            return ServiceResult.success(
                file_exists,
                message=f"File existence check for {file_name}",
            )
        except Exception as e:
            self.logger.exception("Unexpected error checking file existence")
            error = ProcessError(f"Failed to check file existence: {str(e)}")
            return ServiceResult.error(error)

    async def copy_file(
        self, source_project: Project, target_project: Project, file_name: str
    ) -> ServiceResult[bool]:
        """Copy a file from source project to target project (backward compatibility)"""
        async with self.operation_context("copy_file", timeout=30.0) as ctx:
            try:
                source_file = source_project.path / file_name
                target_file = target_project.path / file_name

                # First try Python's built-in file existence check (more reliable)
                file_exists = source_file.exists()

                # If file doesn't exist according to pathlib, double-check with platform service
                if not file_exists:
                    platform_exists, _ = await PlatformService.check_file_exists_async(
                        str(source_file)
                    )
                    file_exists = platform_exists

                if not file_exists:
                    error = ResourceError(f"Source file {file_name} does not exist")
                    return ServiceResult.error(error)

                # Ensure target directory exists using async platform service
                target_dir = str(target_file.parent)
                dir_success, dir_error = await PlatformService.create_directory_async(
                    target_dir
                )

                if not dir_success:
                    self.logger.warning(
                        "Platform directory creation failed: %s, falling back to mkdir",
                        dir_error,
                    )
                    # Fallback to pathlib
                    await run_in_executor(
                        target_file.parent.mkdir, parents=True, exist_ok=True
                    )

                # Copy the file using async platform service
                copy_success, copy_error = await PlatformService.copy_file_async(
                    str(source_file), str(target_file), preserve_attrs=True
                )

                if copy_success:
                    return ServiceResult.success(
                        True,
                        message=f"Successfully copied {file_name} using platform service",
                    )
                else:
                    self.logger.warning(
                        "Platform copy failed: %s, falling back to shutil", copy_error
                    )
                    # Fallback to shutil
                    await run_in_executor(shutil.copy2, source_file, target_file)
                    return ServiceResult.success(
                        True,
                        message=f"Successfully copied {file_name} using shutil fallback",
                    )

            except Exception as e:
                self.logger.exception("Unexpected error during file copy")
                error = ProcessError(f"File copy operation failed: {str(e)}")
                return ServiceResult.error(error)

    def _copy_file_sync(
        self, source_project: Project, target_project: Project, file_name: str
    ) -> bool:
        """Synchronous implementation of file copying"""
        try:
            source_file = source_project.path / file_name
            target_file = target_project.path / file_name

            # First try Python's built-in file existence check (more reliable)
            file_exists = source_file.exists()

            # If file doesn't exist according to pathlib, double-check with platform service
            if not file_exists:
                platform_exists, _ = PlatformService.check_file_exists(str(source_file))
                file_exists = platform_exists

            if not file_exists:
                return False

            # Ensure target directory exists using platform service
            target_dir = str(target_file.parent)
            dir_success, dir_error = PlatformService.create_directory(target_dir)

            if not dir_success:
                self.logger.warning(
                    "Platform directory creation failed: %s, falling back to mkdir",
                    dir_error,
                )
                # Fallback to pathlib
                target_file.parent.mkdir(parents=True, exist_ok=True)

            # Copy the file using platform service
            copy_success, copy_error = PlatformService.copy_file(
                str(source_file), str(target_file), preserve_attrs=True
            )

            if copy_success:
                return True
            else:
                self.logger.warning(
                    "Platform copy failed: %s, falling back to shutil", copy_error
                )
                # Fallback to shutil
                shutil.copy2(source_file, target_file)
                return True

        except Exception:
            return False
