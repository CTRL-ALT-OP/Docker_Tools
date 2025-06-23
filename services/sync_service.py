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

                    # Create test source and target
                    source_dir = temp_path / "source"
                    target_dir = temp_path / "target"
                    source_dir.mkdir()
                    target_dir.mkdir()

                    # Test file creation and copy
                    test_file = source_dir / "test.txt"
                    test_content = "sync test content"
                    test_file.write_text(test_content)

                    # Test sync operation
                    target_file = target_dir / "test.txt"
                    shutil.copy2(test_file, target_file)

                    # Verify sync
                    copied_content = target_file.read_text()
                    sync_successful = copied_content == test_content

                    return ServiceResult.success(
                        {
                            "status": "healthy",
                            "sync_operations": "functional",
                            "file_copy_test": sync_successful,
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
                file_info = await run_in_executor(
                    self._get_file_info_sync, project, file_name
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

    def _get_file_info_sync(self, project: Project, file_name: str) -> FileSyncInfo:
        """Synchronous implementation of file info retrieval"""
        file_path = project.path / file_name

        try:
            if file_path.exists() and file_path.is_file():
                stat_info = file_path.stat()
                return FileSyncInfo(
                    file_path=file_path,
                    file_size=stat_info.st_size,
                    file_exists=True,
                    is_readable=os.access(file_path, os.R_OK),
                    last_modified=stat_info.st_mtime,
                )
            else:
                return FileSyncInfo(
                    file_path=file_path,
                    file_size=0,
                    file_exists=False,
                    is_readable=False,
                    last_modified=0.0,
                )
        except (OSError, PermissionError):
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
                        f"Failed to sync file to {len(result.failed_syncs)} target(s)",
                        details={"failed_targets": result.failed_syncs},
                    )
                    return ServiceResult.partial(
                        result,
                        error,
                        message=f"File '{file_name}' partially synced to {result.success_count}/{result.total_targets} versions",
                    )
                else:
                    # All failed
                    error = ResourceError(
                        f"Failed to sync file '{file_name}' to any target versions",
                        details={"failed_targets": result.failed_syncs},
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

                # Ensure target directory exists
                target_file.parent.mkdir(parents=True, exist_ok=True)

                # Copy the file
                shutil.copy2(source_file, target_file)
                synced_paths.append(target_file)

                self.logger.debug(
                    "Synced %s from %s to %s",
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
                        if sync_result.data
                        else SyncOperationResult(
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
                        f"Failed to sync {total_files - successful_files} files",
                        details={
                            "failed_files": [
                                r.file_name for r in results if r.success_count == 0
                            ]
                        },
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
            if project.parent != "pre-edit"
        ]

    # Backward compatibility methods
    async def has_file(self, project: Project, file_name: str) -> ServiceResult[bool]:
        """Check if a project has a file (backward compatibility)"""
        file_info_result = await self.get_file_info(project, file_name)
        if file_info_result.is_success:
            return ServiceResult.success(
                file_info_result.data.file_exists,
                message=f"File existence check for {file_name}",
            )
        else:
            return ServiceResult.error(file_info_result.error)

    async def copy_file(
        self, source_project: Project, target_project: Project, file_name: str
    ) -> ServiceResult[bool]:
        """Copy a file from source project to target project (backward compatibility)"""
        async with self.operation_context("copy_file", timeout=30.0) as ctx:
            try:
                success = await run_in_executor(
                    self._copy_file_sync, source_project, target_project, file_name
                )

                if success:
                    return ServiceResult.success(
                        True, message=f"Successfully copied {file_name}"
                    )
                else:
                    error = ProcessError(f"Failed to copy {file_name}")
                    return ServiceResult.error(error)

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

            # Check if source file exists
            if not source_file.exists() or not source_file.is_file():
                return False

            # Ensure target directory exists
            target_file.parent.mkdir(parents=True, exist_ok=True)

            # Copy the file
            shutil.copy2(source_file, target_file)
            return True

        except Exception:
            return False
