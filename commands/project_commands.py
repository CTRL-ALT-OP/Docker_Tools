"""
Project-specific command implementations
Handles cleanup and archiving operations for individual projects
"""

from pathlib import Path
from typing import Dict, Any

from utils.async_base import AsyncCommand, AsyncResult, ProcessError
from models.project import Project


class CleanupProjectCommand(AsyncCommand):
    """Standardized command for project cleanup operations"""

    def __init__(self, project: Project, file_service, **kwargs):
        super().__init__(**kwargs)
        self.project = project
        self.file_service = file_service

    async def execute(self) -> AsyncResult[Dict[str, Any]]:
        """Execute the cleanup command"""
        try:
            # Update progress
            self._update_progress("Scanning for cleanup items...", "info")

            # Scan for items to cleanup
            scan_result = await self.file_service.scan_for_cleanup_items(
                self.project.path
            )
            if scan_result.is_error:
                return AsyncResult.error_result(scan_result.error)

            cleanup_data = scan_result.data

            # Check if there are items to cleanup
            if not cleanup_data.directories and not cleanup_data.files:
                return AsyncResult.success_result(
                    {"message": "No items found to cleanup", "deleted_items": []},
                    message="No cleanup needed",
                )

            self._update_progress("Removing cleanup items...", "warning")

            # Perform cleanup
            cleanup_result = await self.file_service.cleanup_project_items(
                self.project.path
            )

            if cleanup_result.is_error:
                return AsyncResult.error_result(cleanup_result.error)

            result_data = {
                "message": f"Cleanup completed for {self.project.name}",
                "deleted_directories": cleanup_result.data.deleted_directories,
                "deleted_files": cleanup_result.data.deleted_files,
                "total_deleted_size": cleanup_result.data.total_deleted_size,
                "failed_deletions": cleanup_result.data.failed_deletions,
                "project": self.project,  # Include project for button reset
            }

            self._update_progress("Cleanup completed successfully", "success")

            return AsyncResult.success_result(
                result_data, message=f"Successfully cleaned up {self.project.name}"
            )

        except Exception as e:
            self.logger.exception(f"Cleanup command failed for {self.project.name}")
            return AsyncResult.error_result(
                ProcessError(f"Cleanup failed: {str(e)}", error_code="CLEANUP_ERROR")
            )


class ArchiveProjectCommand(AsyncCommand):
    """Standardized command for project archive operations"""

    def __init__(self, project: Project, file_service, project_service, **kwargs):
        super().__init__(**kwargs)
        self.project = project
        self.file_service = file_service
        self.project_service = project_service

    async def execute(self) -> AsyncResult[Dict[str, Any]]:
        """Execute the archive command"""
        try:
            self._update_progress("Scanning for cleanup items...", "info")

            # First, scan for directories and files that need cleanup
            scan_result = await self.file_service.scan_for_cleanup_items(
                self.project.path
            )

            cleanup_needed = False
            cleanup_message = ""

            if scan_result.is_success and scan_result.data:
                cleanup_data = scan_result.data
                if cleanup_data.directories or cleanup_data.files:
                    cleanup_needed = True
                    cleanup_message = (
                        f"Found {len(cleanup_data.directories)} directories and "
                        f"{len(cleanup_data.files)} files that should be cleaned up before archiving."
                    )

            self._update_progress("Creating archive...", "info")

            # Get archive name
            archive_name = await self.project_service.get_archive_name_async(
                self.project.parent, self.project.name
            )

            # Create archive
            archive_result = await self.file_service.create_archive(
                self.project.path, archive_name
            )

            if archive_result.is_error:
                return AsyncResult.error_result(archive_result.error)

            result_data = {
                "message": f"Archive created for {self.project.name}",
                "archive_path": str(archive_result.data.archive_path),
                "archive_size": archive_result.data.archive_size,
                "files_archived": archive_result.data.files_archived,
                "compression_ratio": archive_result.data.compression_ratio,
                "cleanup_needed": cleanup_needed,
                "cleanup_message": cleanup_message,
                "project": self.project,  # Include project for button color management
            }

            self._update_progress("Archive created successfully", "success")

            return AsyncResult.success_result(
                result_data, message=f"Successfully archived {self.project.name}"
            )

        except Exception as e:
            self.logger.exception(f"Archive command failed for {self.project.name}")
            return AsyncResult.error_result(
                ProcessError(f"Archive failed: {str(e)}", error_code="ARCHIVE_ERROR")
            )
