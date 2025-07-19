"""
File Service - Standardized Async Version
"""

import contextlib
import os
import shutil
import logging
from pathlib import Path
from typing import List, Tuple, Dict, Any
from dataclasses import dataclass

from config.config import get_config

config = get_config()
IGNORE_DIRS = config.project.ignore_dirs
IGNORE_FILES = config.project.ignore_files
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

logger = logging.getLogger(__name__)


@dataclass
class CleanupScanResult:
    """Result of scanning for cleanup items"""

    directories: List[Path]
    files: List[Path]
    total_size: int  # Total size in bytes
    item_count: int


@dataclass
class CleanupResult:
    """Result of cleanup operation"""

    deleted_directories: List[Path]
    deleted_files: List[Path]
    total_deleted_size: int
    failed_deletions: List[Tuple[Path, str]]  # (path, error_reason)


@dataclass
class ArchiveResult:
    """Result of archive creation"""

    archive_path: Path
    archive_size: int
    files_archived: int
    compression_ratio: float


class FileService(AsyncServiceInterface):
    """Standardized File service with consistent async interface"""

    def __init__(self):
        super().__init__("FileService")
        self.platform_service = PlatformService()

    async def health_check(self) -> ServiceResult[Dict[str, Any]]:
        """Check File service health"""
        async with self.operation_context("health_check", timeout=10.0) as ctx:
            try:
                # Check basic file system operations
                import tempfile

                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_path = Path(temp_dir)

                    # Test file creation
                    test_file = temp_path / "test.txt"
                    test_file.write_text("test content")

                    # Test file reading
                    content = test_file.read_text()

                    # Test directory operations
                    test_dir = temp_path / "test_dir"
                    test_dir.mkdir()

                    return ServiceResult.success(
                        {
                            "status": "healthy",
                            "platform": self.platform_service.get_platform(),
                            "cleanup_dirs": len(self.cleanup_dirs),
                            "cleanup_files": len(self.cleanup_files),
                            "temp_dir_available": True,
                        }
                    )

            except Exception as e:
                error = ResourceError(f"File system operations failed: {str(e)}")
                return ServiceResult.error(error)

    @property
    def cleanup_dirs(self):
        """Get cleanup directories from configuration"""
        return IGNORE_DIRS

    @property
    def cleanup_files(self):
        """Get cleanup files from configuration"""
        return IGNORE_FILES

    async def scan_for_cleanup_items(
        self, project_path: Path
    ) -> ServiceResult[CleanupScanResult]:
        """Scan for directories and files that match cleanup patterns"""
        # Validate input
        if not project_path.exists():
            error = ValidationError(f"Project path does not exist: {project_path}")
            return ServiceResult.error(error)

        if not project_path.is_dir():
            error = ValidationError(f"Project path is not a directory: {project_path}")
            return ServiceResult.error(error)

        async with self.operation_context(
            "scan_for_cleanup_items", timeout=60.0
        ) as ctx:
            try:
                scan_result = await run_in_executor(
                    self._scan_for_cleanup_items_sync, project_path
                )

                return ServiceResult.success(
                    scan_result,
                    message=f"Scanned {scan_result.item_count} items for cleanup",
                    metadata={
                        "project_path": str(project_path),
                        "total_size_mb": round(
                            scan_result.total_size / (1024 * 1024), 2
                        ),
                    },
                )

            except PermissionError as e:
                error = ResourceError(
                    f"Permission denied scanning {project_path}: {str(e)}"
                )
                return ServiceResult.error(error)
            except Exception as e:
                self.logger.exception("Unexpected error during cleanup scan")
                error = ProcessError(f"Failed to scan for cleanup items: {str(e)}")
                return ServiceResult.error(error)

    def _scan_for_cleanup_items_sync(self, project_path: Path) -> CleanupScanResult:
        """Synchronous implementation of directory scanning (files are skipped for cleanup)"""
        cleanup_dirs = []
        cleanup_files = []  # Keep empty list for backward compatibility
        total_size = 0

        try:
            for root, dirs, files in os.walk(project_path):
                root_path = Path(root)

                # Scan for directories to cleanup
                for dir_name in dirs:
                    if any(
                        pattern in dir_name.lower() for pattern in self.cleanup_dirs
                    ):
                        dir_path = root_path / dir_name
                        cleanup_dirs.append(dir_path)
                        # Calculate directory size
                        with contextlib.suppress(OSError):
                            dir_size = sum(
                                f.stat().st_size
                                for f in dir_path.rglob("*")
                                if f.is_file()
                            )
                            total_size += dir_size
                # Note: Files are no longer scanned for cleanup - they will be skipped during archival instead
        except PermissionError as e:
            logger.error("Permission denied scanning directory %s: %s", project_path, e)
            # Re-raise so the async method can handle it properly
            raise
        except OSError as e:
            logger.error("OS error scanning directory %s: %s", project_path, e)
            # Continue with partial results for other OS errors

        return CleanupScanResult(
            directories=cleanup_dirs,
            files=cleanup_files,  # Empty list - files are no longer cleaned up
            total_size=total_size,
            item_count=len(cleanup_dirs),  # Only count directories
        )

    async def cleanup_project_items(
        self, project_path: Path
    ) -> ServiceResult[CleanupResult]:
        """Clean up specified directories and files in the project"""
        # Validate input
        if not project_path.exists():
            error = ValidationError(f"Project path does not exist: {project_path}")
            return ServiceResult.error(error)

        async with self.operation_context(
            "cleanup_project_items", timeout=120.0
        ) as ctx:
            try:
                # First scan to get what we're going to clean
                scan_result_response = await self.scan_for_cleanup_items(project_path)
                if scan_result_response.is_error:
                    return ServiceResult.error(scan_result_response.error)

                scan_result = scan_result_response.data

                if scan_result.item_count == 0:
                    return ServiceResult.success(
                        CleanupResult(
                            deleted_directories=[],
                            deleted_files=[],
                            total_deleted_size=0,
                            failed_deletions=[],
                        ),
                        message="No items found to clean up",
                    )

                # Perform cleanup
                cleanup_result = await run_in_executor(
                    self._cleanup_project_items_sync, project_path
                )

                success_count = len(cleanup_result.deleted_directories) + len(
                    cleanup_result.deleted_files
                )
                failed_count = len(cleanup_result.failed_deletions)

                if failed_count == 0:
                    return ServiceResult.success(
                        cleanup_result,
                        message=f"Successfully cleaned up {success_count} items",
                        metadata={
                            "deleted_size_mb": round(
                                cleanup_result.total_deleted_size / (1024 * 1024), 2
                            )
                        },
                    )
                elif success_count > 0:
                    # Partial success
                    error = ResourceError(
                        f"Failed to delete {failed_count} items",
                        details={
                            "failed_items": [
                                str(path) for path, _ in cleanup_result.failed_deletions
                            ]
                        },
                    )
                    return ServiceResult.partial(
                        cleanup_result,
                        error,
                        message=f"Partially cleaned up {success_count} items, {failed_count} failed",
                    )
                else:
                    # All failed
                    error = ResourceError(
                        f"Failed to delete all {failed_count} items",
                        details={
                            "failed_items": [
                                str(path) for path, _ in cleanup_result.failed_deletions
                            ]
                        },
                    )
                    return ServiceResult.error(error)

            except Exception as e:
                self.logger.exception("Unexpected error during cleanup")
                error = ProcessError(f"Cleanup operation failed: {str(e)}")
                return ServiceResult.error(error)

    def _cleanup_project_items_sync(self, project_path: Path) -> CleanupResult:
        """Synchronous implementation of directory cleanup (files are skipped)"""
        deleted_dirs = []
        deleted_files = []  # Keep empty list for backward compatibility
        failed_deletions = []
        total_deleted_size = 0

        def remove_items_recursive(path):
            """Recursively remove directories matching cleanup patterns (files are skipped)"""
            try:
                for root, dirs, files in os.walk(path, topdown=False):
                    root_path = Path(root)

                    # Note: Files are no longer deleted during cleanup - they will be skipped during archival instead
                    # This preserves ignore files like .coverage for the project but excludes them from archives

                    # Remove directories that match cleanup patterns
                    for dir_name in dirs:
                        if any(
                            pattern in dir_name.lower() for pattern in self.cleanup_dirs
                        ):
                            dir_path = root_path / dir_name
                            try:
                                # Calculate directory size before deletion
                                dir_size = sum(
                                    f.stat().st_size
                                    for f in dir_path.rglob("*")
                                    if f.is_file()
                                )
                                shutil.rmtree(dir_path)
                                deleted_dirs.append(dir_path)
                                nonlocal total_deleted_size
                                total_deleted_size += dir_size
                                logger.debug("Deleted directory: %s", dir_path)
                            except PermissionError as e:
                                failed_deletions.append(
                                    (dir_path, f"Permission denied: {e}")
                                )
                                logger.warning(
                                    "Permission denied deleting %s: %s", dir_path, e
                                )
                            except FileNotFoundError:
                                logger.debug("Directory already deleted: %s", dir_path)
                            except OSError as e:
                                failed_deletions.append((dir_path, f"OS error: {e}"))
                                logger.error("OS error deleting %s: %s", dir_path, e)
            except OSError as e:
                logger.error("Error walking directory %s: %s", path, e)

        remove_items_recursive(project_path)

        return CleanupResult(
            deleted_directories=deleted_dirs,
            deleted_files=deleted_files,  # Empty list - files are no longer deleted
            total_deleted_size=total_deleted_size,
            failed_deletions=failed_deletions,
        )

    async def create_archive(
        self, project_path: Path, archive_name: str
    ) -> ServiceResult[ArchiveResult]:
        """Create archive of the project with standardized result format"""
        # Validate input
        if not project_path.exists():
            error = ValidationError(f"Project path does not exist: {project_path}")
            return ServiceResult.error(error)

        if not project_path.is_dir():
            error = ValidationError(f"Project path is not a directory: {project_path}")
            return ServiceResult.error(error)

        if not archive_name:
            error = ValidationError("Archive name cannot be empty")
            return ServiceResult.error(error)

        async with self.operation_context("create_archive", timeout=300.0) as ctx:
            try:
                # Calculate original size
                original_size = await run_in_executor(
                    self._calculate_directory_size, project_path
                )

                # Count files to be archived
                file_count = await run_in_executor(self._count_files, project_path)

                # Create archive
                archive_result = await self._create_archive_async(
                    project_path, archive_name
                )

                if archive_result["success"]:
                    archive_path = project_path / archive_name
                    archive_size = (
                        archive_path.stat().st_size if archive_path.exists() else 0
                    )
                    compression_ratio = (
                        (archive_size / original_size) if original_size > 0 else 0
                    )

                    result = ArchiveResult(
                        archive_path=archive_path,
                        archive_size=archive_size,
                        files_archived=file_count,
                        compression_ratio=compression_ratio,
                    )

                    return ServiceResult.success(
                        result,
                        message=f"Successfully created archive: {archive_name}",
                        metadata={
                            "original_size_mb": round(original_size / (1024 * 1024), 2),
                            "archive_size_mb": round(archive_size / (1024 * 1024), 2),
                            "compression_percent": round(
                                (1 - compression_ratio) * 100, 1
                            ),
                        },
                    )
                else:
                    error = ProcessError(
                        f"Archive creation failed: {archive_result['error']}",
                        return_code=archive_result.get("return_code", 1),
                    )
                    return ServiceResult.error(error)

            except Exception as e:
                self.logger.exception("Unexpected error during archive creation")
                error = ProcessError(f"Archive creation error: {str(e)}")
                return ServiceResult.error(error)

    def _calculate_directory_size(self, directory: Path) -> int:
        """Calculate total size of directory contents"""
        total_size = 0
        with contextlib.suppress(OSError):
            for file_path in directory.rglob("*"):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
        return total_size

    def _count_files(self, directory: Path) -> int:
        """Count total number of files in directory"""
        file_count = 0
        with contextlib.suppress(OSError):
            for file_path in directory.rglob("*"):
                if file_path.is_file():
                    file_count += 1
        return file_count

    async def _create_archive_async(
        self, project_path: Path, archive_name: str
    ) -> Dict[str, Any]:
        """Async implementation of archive creation with cleanup and exclusions"""
        original_cwd = None
        try:
            # Change to project directory
            original_cwd = os.getcwd()
            os.chdir(project_path)

            # First, run cleanup on directories to remove unwanted items
            cleanup_result = await self.cleanup_project_items(project_path)
            if cleanup_result.is_error:
                logger.warning(
                    "Cleanup failed before archive creation: %s", cleanup_result.error
                )
                # Continue with archive creation even if cleanup fails

            # Create archive with exclusions
            success, output = await self._create_archive_with_exclusions(archive_name)

            if success:
                logger.info("Successfully created archive: %s", archive_name)
                return {
                    "success": True,
                    "archive_name": archive_name,
                    "output": output,
                }
            else:
                logger.error("Archive creation failed: %s", output)
                return {
                    "success": False,
                    "error": output,
                    "return_code": 1,
                }

        except FileNotFoundError:
            logger.error("Project directory not found: %s", project_path)
            return {
                "success": False,
                "error": f"Project directory not found: {project_path}",
            }
        except PermissionError as e:
            logger.error(
                "Permission denied creating archive for %s: %s", project_path, e
            )
            return {"success": False, "error": f"Permission denied: {str(e)}"}
        except Exception as e:
            logger.exception("Unexpected error during archive creation")
            return {"success": False, "error": f"Unexpected error: {str(e)}"}
        finally:
            # Restore original working directory
            if original_cwd:
                try:
                    os.chdir(original_cwd)
                except Exception as e:
                    logger.warning("Failed to restore working directory: %s", e)

    def _is_hidden(self, path: Path) -> bool:
        """Check if a file or directory is hidden (starts with dot or has hidden attribute on Windows)"""
        import stat

        # Check if any part of the path starts with a dot (Unix-style hidden)
        for part in path.parts:
            if part.startswith(".") and part not in (".", ".."):
                return True

        # On Windows, also check the hidden attribute
        with contextlib.suppress(AttributeError, OSError):
            if PlatformService.is_windows() and path.exists():
                return bool(path.stat().st_file_attributes & stat.FILE_ATTRIBUTE_HIDDEN)
        return False

    async def _create_archive_with_exclusions(
        self, archive_name: str
    ) -> Tuple[bool, str]:
        """Create archive with exclusions for hidden files, ignore patterns, and cleanup items"""
        try:
            import zipfile

            # Use Python to determine which files to include
            current_dir = Path.cwd()
            items_to_include = []

            # Get all items recursively
            for item in current_dir.rglob("*"):
                if item.is_file() and item.name != archive_name:
                    # Get relative path from current directory
                    try:
                        relative_path = item.relative_to(current_dir)
                        relative_path_str = str(relative_path).replace("\\", "/")

                        # Check if this item should be excluded
                        should_exclude = False

                        # 1. Exclude hidden files and directories (PowerShell-like behavior)
                        if self._is_hidden(relative_path):
                            should_exclude = True

                        # 2. Check against ignore directories (cleanup_dirs)
                        if not should_exclude:
                            for ignore_dir in self.cleanup_dirs:
                                if ignore_dir in relative_path_str:
                                    should_exclude = True
                                    break

                        # 3. Check against ignore files (cleanup_files)
                        if not should_exclude:
                            for ignore_file in self.cleanup_files:
                                if ignore_file in relative_path_str:
                                    should_exclude = True
                                    break

                        if not should_exclude:
                            # Ensure consistent forward slashes for archive paths
                            archive_path = str(relative_path).replace("\\", "/")
                            items_to_include.append((item, archive_path))
                    except ValueError:
                        # Skip if can't get relative path
                        continue

            # Remove duplicates based on the archive path
            seen_paths = set()
            unique_items = []
            for item, archive_path in items_to_include:
                if archive_path not in seen_paths:
                    seen_paths.add(archive_path)
                    unique_items.append((item, archive_path))

            # Create the zip archive using Python zipfile for consistent directory structure
            with zipfile.ZipFile(archive_name, "w", zipfile.ZIP_DEFLATED) as zipf:
                for item, archive_path in unique_items:
                    if item.is_file():
                        zipf.write(item, archive_path)

            return (
                True,
                f"Successfully created archive {archive_name} with {len(unique_items)} files (hidden files excluded)",
            )

        except Exception as e:
            logger.exception("Error creating archive with exclusions")
            return False, f"Error creating archive: {str(e)}"

    # Backward compatibility methods
    async def scan_for_cleanup_dirs(
        self, project_path: Path
    ) -> ServiceResult[List[Path]]:
        """Backward compatibility: scan for cleanup directories only"""
        result = await self.scan_for_cleanup_items(project_path)
        if result.is_success:
            return ServiceResult.success(
                result.data.directories,
                message=f"Found {len(result.data.directories)} directories to clean",
            )
        else:
            return ServiceResult.error(result.error)

    async def cleanup_project_dirs(
        self, project_path: Path
    ) -> ServiceResult[List[Path]]:
        """Backward compatibility: cleanup and return deleted directory paths"""
        result = await self.cleanup_project_items(project_path)
        if not result.is_success and not result.is_partial:
            return ServiceResult.error(result.error)
        deleted_paths = result.data.deleted_directories + result.data.deleted_files
        return ServiceResult.success(
            deleted_paths, message=f"Cleaned up {len(deleted_paths)} items"
        )
