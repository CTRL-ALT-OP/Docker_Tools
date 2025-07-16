"""
Service for managing projects and folder aliases
"""

import asyncio
from pathlib import Path
from typing import List, Optional

from config.config import get_config

FOLDER_ALIASES = get_config().project.folder_aliases
from models.project import Project
from services.platform_service import PlatformService

# Import async utilities if available
try:
    from utils.async_utils import run_in_executor

    ASYNC_AVAILABLE = True
except ImportError:
    ASYNC_AVAILABLE = False


class ProjectService:
    """Service for managing projects and folder aliases"""

    def __init__(self, root_dir: str = "."):
        self.root_dir = Path(root_dir).resolve()
        self.platform_service = PlatformService()

    def get_folder_alias(self, folder_name: str) -> Optional[str]:
        """Get the alias for a folder name, returns None if no alias exists"""
        return next(
            (
                alias
                for alias, folder_list in FOLDER_ALIASES.items()
                if folder_name in folder_list
            ),
            None,
        )

    def get_archive_name(self, parent_folder: str, project_name: str) -> str:
        """Generate archive name based on the specified naming convention"""
        project_clean = project_name.replace("-", "")
        parent_clean = parent_folder.replace("-", "")

        # Handle empty strings case
        if not project_clean and not parent_clean:
            return "_.zip"

        # Use underscore as fallback for empty values
        project_clean = project_clean or "_"
        parent_clean = parent_clean or "_"

        # Check if parent folder has an alias
        alias = self.get_folder_alias(parent_folder)
        if alias:
            return f"{project_clean}_{alias}.zip"
        # Default behavior for folders without aliases
        return f"{project_clean}_{parent_clean}.zip"

    def get_docker_tag(self, parent_folder: str, project_name: str) -> str:
        """Generate Docker tag based on parent folder and project name"""
        project_clean = project_name.replace("-", "")

        # Check if parent folder has an alias
        alias = self.get_folder_alias(parent_folder)
        if alias:
            return f"{project_clean}:{alias}"
        # Default behavior for folders without aliases
        parent_clean = parent_folder.replace("-", "")
        return f"{project_clean}:{parent_clean}"

    def get_folder_sort_order(self, folder_name: str) -> int:
        """Get the sort order for a folder based on FOLDER_ALIASES.
        Returns the index in FOLDER_ALIASES order, or 999 for unaliased folders."""

        # Create ordered list of alias keys from FOLDER_ALIASES
        alias_order = list(FOLDER_ALIASES.keys())

        return next(
            (
                i
                for i, (alias, folder_list) in enumerate(FOLDER_ALIASES.items())
                if folder_name in folder_list
            ),
            999,
        )

    def find_two_layer_projects(self) -> List[Project]:
        """Find all projects that are exactly 2 layers deep"""
        projects = []

        for item in self.root_dir.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                # Check for subdirectories (2nd layer)
                for subitem in item.iterdir():
                    if subitem.is_dir() and not subitem.name.startswith("."):
                        project = Project(
                            parent=item.name,
                            name=subitem.name,
                            path=subitem,
                            relative_path=f"{item.name}/{subitem.name}",
                        )
                        projects.append(project)

        return sorted(projects, key=lambda x: (x.parent, x.name))

    def _check_directory_exists(self, dir_path: str) -> bool:
        """Helper method to check if directory exists using platform service"""
        try:
            success, _ = PlatformService.run_command_with_result(
                "FILE_SYSTEM_COMMANDS",
                subkey="check_dir_exists",
                dir_path=dir_path,
                capture_output=True,
                text=True,
            )
            return success
        except Exception:
            # Fall back to pathlib check
            return Path(dir_path).is_dir()

    def _list_directory_contents(self, dir_path: str) -> List[str]:
        """Helper method to list directory contents using platform service"""
        try:
            success, output = PlatformService.run_command_with_result(
                "FILE_SYSTEM_COMMANDS",
                subkey="list_dir",
                dir_path=dir_path,
                capture_output=True,
                text=True,
            )
            if success:
                return [line.strip() for line in output.split("\n") if line.strip()]
            else:
                # Fall back to pathlib
                return [item.name for item in Path(dir_path).iterdir() if item.is_dir()]
        except Exception:
            # Fall back to pathlib
            try:
                return [item.name for item in Path(dir_path).iterdir() if item.is_dir()]
            except Exception:
                return []

    # ========== ASYNC METHODS ==========

    async def find_two_layer_projects_async(self) -> List[Project]:
        """Async version of find_two_layer_projects using command execution"""
        if not ASYNC_AVAILABLE:
            # Fall back to sync version
            return await run_in_executor(self.find_two_layer_projects)

        projects = []

        try:
            # Get list of directories in root directory
            success, output = await PlatformService.run_command_with_result_async(
                "FILE_SYSTEM_COMMANDS",
                subkey="list_dir",
                dir_path=str(self.root_dir),
                capture_output=True,
                text=True,
            )

            if not success:
                # Fall back to sync version if command fails
                return await run_in_executor(self.find_two_layer_projects)

            # Parse the output to get directory names
            dir_names = [line.strip() for line in output.split("\n") if line.strip()]

            # For each directory, check if it's actually a directory and get its subdirectories
            for dir_name in dir_names:
                if dir_name.startswith("."):
                    continue

                dir_path = self.root_dir / dir_name

                # Check if it's actually a directory using platform service
                is_dir = await self._check_directory_exists_async(str(dir_path))
                if not is_dir:
                    continue

                # Get subdirectories
                sub_success, sub_output = (
                    await PlatformService.run_command_with_result_async(
                        "FILE_SYSTEM_COMMANDS",
                        subkey="list_dir",
                        dir_path=str(dir_path),
                        capture_output=True,
                        text=True,
                    )
                )

                if not sub_success:
                    continue

                # Parse subdirectory names
                sub_dir_names = [
                    line.strip() for line in sub_output.split("\n") if line.strip()
                ]

                for sub_dir_name in sub_dir_names:
                    if sub_dir_name.startswith("."):
                        continue

                    sub_dir_path = dir_path / sub_dir_name

                    # Check if it's actually a directory using platform service
                    is_sub_dir = await self._check_directory_exists_async(
                        str(sub_dir_path)
                    )
                    if not is_sub_dir:
                        continue

                    project = Project(
                        parent=dir_name,
                        name=sub_dir_name,
                        path=sub_dir_path,
                        relative_path=f"{dir_name}/{sub_dir_name}",
                    )
                    projects.append(project)

        except Exception:
            # Fall back to sync version if any error occurs
            return await run_in_executor(self.find_two_layer_projects)

        return sorted(projects, key=lambda x: (x.parent, x.name))

    async def _check_directory_exists_async(self, dir_path: str) -> bool:
        """Async helper method to check if directory exists using platform service"""
        if not ASYNC_AVAILABLE:
            return await run_in_executor(self._check_directory_exists, dir_path)

        try:
            success, _ = await PlatformService.run_command_with_result_async(
                "FILE_SYSTEM_COMMANDS",
                subkey="check_dir_exists",
                dir_path=dir_path,
                capture_output=True,
                text=True,
            )
            return success
        except Exception:
            # Fall back to pathlib check
            return await run_in_executor(lambda: Path(dir_path).is_dir())

    async def check_directory_exists_async(self, dir_path: str) -> bool:
        """Check if a directory exists using async command execution"""
        return await self._check_directory_exists_async(dir_path)

    async def _list_directory_contents_async(self, dir_path: str) -> List[str]:
        """Async helper method to list directory contents using platform service"""
        if not ASYNC_AVAILABLE:
            return await run_in_executor(self._list_directory_contents, dir_path)

        try:
            success, output = await PlatformService.run_command_with_result_async(
                "FILE_SYSTEM_COMMANDS",
                subkey="list_dir",
                dir_path=dir_path,
                capture_output=True,
                text=True,
            )
            if success:
                return [line.strip() for line in output.split("\n") if line.strip()]
            else:
                # Fall back to pathlib
                return await run_in_executor(
                    lambda: [
                        item.name for item in Path(dir_path).iterdir() if item.is_dir()
                    ]
                )
        except Exception:
            # Fall back to pathlib
            return await run_in_executor(
                lambda: [
                    item.name for item in Path(dir_path).iterdir() if item.is_dir()
                ]
            )

    async def get_folder_alias_async(self, folder_name: str) -> Optional[str]:
        """Async version of get_folder_alias"""
        if not ASYNC_AVAILABLE:
            return self.get_folder_alias(folder_name)
        return await run_in_executor(self.get_folder_alias, folder_name)

    async def get_archive_name_async(
        self, parent_folder: str, project_name: str
    ) -> str:
        """Async version of get_archive_name"""
        if not ASYNC_AVAILABLE:
            return self.get_archive_name(parent_folder, project_name)
        return await run_in_executor(self.get_archive_name, parent_folder, project_name)

    async def get_docker_tag_async(self, parent_folder: str, project_name: str) -> str:
        """Async version of get_docker_tag"""
        if not ASYNC_AVAILABLE:
            return self.get_docker_tag(parent_folder, project_name)
        return await run_in_executor(self.get_docker_tag, parent_folder, project_name)

    async def get_folder_sort_order_async(self, folder_name: str) -> int:
        """Async version of get_folder_sort_order"""
        if not ASYNC_AVAILABLE:
            return self.get_folder_sort_order(folder_name)
        return await run_in_executor(self.get_folder_sort_order, folder_name)
