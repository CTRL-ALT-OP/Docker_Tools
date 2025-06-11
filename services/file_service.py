"""
Service for file operations (cleanup, archiving) - Async version
"""

import os
import shutil
import logging
from pathlib import Path
from typing import List, Tuple

from config.settings import IGNORE_DIRS
from services.platform_service import PlatformService
from utils.async_utils import run_in_executor

logger = logging.getLogger(__name__)


class FileService:
    """Service for file operations - Async version"""

    def __init__(self):
        self.cleanup_dirs = IGNORE_DIRS
        self.platform_service = PlatformService()

    async def scan_for_cleanup_dirs(self, project_path: Path) -> List[str]:
        """Scan for directories that match cleanup patterns"""
        return await run_in_executor(self._scan_for_cleanup_dirs_sync, project_path)

    def _scan_for_cleanup_dirs_sync(self, project_path: Path) -> List[str]:
        """Synchronous implementation of directory scanning"""
        cleanup_needed_dirs = []

        try:
            for root, dirs, files in os.walk(project_path):
                cleanup_needed_dirs.extend(
                    os.path.join(root, dir_name)
                    for dir_name in dirs
                    if any(pattern in dir_name.lower() for pattern in self.cleanup_dirs)
                )
        except (OSError, PermissionError) as e:
            logger.error("Error scanning directory %s: %s", project_path, e)
            # Return empty list on error - let caller handle the situation

        return cleanup_needed_dirs

    async def cleanup_project_dirs(self, project_path: Path) -> List[str]:
        """
        Clean up specified directories in the project
        Returns list of deleted items
        """
        return await run_in_executor(self._cleanup_project_dirs_sync, project_path)

    def _cleanup_project_dirs_sync(self, project_path: Path) -> List[str]:
        """Synchronous implementation of directory cleanup"""
        deleted_items = []

        def remove_dir_recursive(path):
            """Recursively remove directories matching cleanup patterns"""
            try:
                for root, dirs, files in os.walk(path, topdown=False):
                    # Remove directories that match cleanup patterns
                    for dir_name in list(dirs):
                        if any(
                            pattern in dir_name.lower() for pattern in self.cleanup_dirs
                        ):
                            dir_path = os.path.join(root, dir_name)
                            try:
                                shutil.rmtree(dir_path)
                                deleted_items.append(dir_path)
                                logger.debug("Deleted directory: %s", dir_path)
                            except PermissionError as e:
                                logger.warning(
                                    "Permission denied deleting %s: %s", dir_path, e
                                )
                            except FileNotFoundError:
                                logger.debug("Directory already deleted: %s", dir_path)
                            except OSError as e:
                                logger.error("OS error deleting %s: %s", dir_path, e)
            except (OSError, PermissionError) as e:
                logger.error("Error walking directory %s: %s", path, e)

        remove_dir_recursive(project_path)
        return deleted_items

    async def create_archive(
        self, project_path: Path, archive_name: str
    ) -> Tuple[bool, str]:
        """
        Create archive of the project
        Returns (success, error_message)
        """
        return await run_in_executor(
            self._create_archive_sync, project_path, archive_name
        )

    def _create_archive_sync(
        self, project_path: Path, archive_name: str
    ) -> Tuple[bool, str]:
        """Synchronous implementation of archive creation"""
        original_cwd = None
        try:
            # Change to project directory
            original_cwd = os.getcwd()
            os.chdir(project_path)

            # Get platform-specific archive command
            cmd, use_shell = self.platform_service.create_archive_command(archive_name)

            result = self.platform_service.run_command(
                cmd,
                use_shell=use_shell,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            if result.returncode == 0:
                logger.info("Successfully created archive: %s", archive_name)
                return True, ""

            error_msg = result.stderr or result.stdout
            logger.error("Archive creation failed: %s", error_msg)
            return False, error_msg

        except FileNotFoundError as e:
            logger.error("Project directory not found: %s", project_path)
            return False, f"Project directory not found: {project_path}"
        except PermissionError as e:
            logger.error(
                "Permission denied creating archive for %s: %s", project_path, e
            )
            return False, f"Permission denied: {str(e)}"
        except OSError as e:
            logger.error("OS error creating archive for %s: %s", project_path, e)
            return False, f"File system error: {str(e)}"
        except Exception as e:
            logger.exception("Unexpected error creating archive for %s", project_path)
            return False, f"Unexpected error: {str(e)}"
        finally:
            # Always restore original directory
            if original_cwd:
                try:
                    os.chdir(original_cwd)
                except OSError as e:
                    logger.error(
                        "Could not restore original directory %s: %s", original_cwd, e
                    )
