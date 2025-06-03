"""
Service for file operations (cleanup, archiving)
"""

import os
import shutil
from pathlib import Path
from typing import List, Tuple

from config.settings import IGNORE_DIRS
from services.platform_service import PlatformService


class FileService:
    """Service for file operations"""

    def __init__(self):
        self.cleanup_dirs = IGNORE_DIRS
        self.platform_service = PlatformService()

    def scan_for_cleanup_dirs(self, project_path: Path) -> List[str]:
        """Scan for directories that match cleanup patterns"""
        cleanup_needed_dirs = []

        for root, dirs, files in os.walk(project_path):
            for dir_name in dirs:
                if any(pattern in dir_name.lower() for pattern in self.cleanup_dirs):
                    cleanup_needed_dirs.append(os.path.join(root, dir_name))

        return cleanup_needed_dirs

    def cleanup_project_dirs(self, project_path: Path) -> List[str]:
        """
        Clean up specified directories in the project
        Returns list of deleted items
        """
        deleted_items = []

        def remove_dir_recursive(path):
            """Recursively remove directories matching cleanup patterns"""
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
                        except Exception as e:
                            print(f"Could not delete {dir_path}: {e}")

        remove_dir_recursive(project_path)
        return deleted_items

    def create_archive(self, project_path: Path, archive_name: str) -> Tuple[bool, str]:
        """
        Create archive of the project
        Returns (success, error_message)
        """
        try:
            # Change to project directory
            original_cwd = os.getcwd()
            os.chdir(project_path)

            try:
                # Get platform-specific archive command
                cmd, use_shell = self.platform_service.create_archive_command(
                    archive_name
                )

                result = self.platform_service.run_command(
                    cmd,
                    use_shell=use_shell,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )

                if result.returncode == 0:
                    return True, ""
                else:
                    error_msg = result.stderr if result.stderr else result.stdout
                    return False, error_msg

            finally:
                os.chdir(original_cwd)

        except Exception as e:
            return False, str(e)
