"""
Service for grouping projects by name and managing project navigation
"""

import asyncio
from typing import List, Dict, Optional
from models.project import Project
from services.project_service import ProjectService

# Import async utilities if available
try:
    from utils.async_utils import run_in_executor

    ASYNC_AVAILABLE = True
except ImportError:
    ASYNC_AVAILABLE = False


class ProjectGroup:
    """Represents a group of projects with the same name across different versions"""

    def __init__(self, name: str, project_service: ProjectService):
        self.name = name
        self.versions: Dict[str, Project] = {}
        self.project_service = project_service

    def add_project(self, project: Project):
        """Add a project to this group"""
        self.versions[project.parent] = project

    def get_version(self, parent_folder: str) -> Optional[Project]:
        """Get a specific version of the project"""
        return self.versions.get(parent_folder)

    def get_all_versions(self) -> List[Project]:
        """Get all versions of the project, sorted by FOLDER_ALIASES order"""
        return sorted(
            self.versions.values(),
            key=lambda x: self.project_service.get_folder_sort_order(x.parent),
        )

    def has_version(self, parent_folder: str) -> bool:
        """Check if this group has a specific version"""
        return parent_folder in self.versions

    # ========== ASYNC METHODS ==========

    async def get_all_versions_async(self) -> List[Project]:
        """Async version of get_all_versions with async sorting"""
        if not ASYNC_AVAILABLE:
            return await run_in_executor(self.get_all_versions)

        versions = list(self.versions.values())
        if not versions:
            return []

        # Get sort orders for all versions asynchronously
        sort_order_tasks = [
            self.project_service.get_folder_sort_order_async(version.parent)
            for version in versions
        ]
        sort_orders = await asyncio.gather(*sort_order_tasks)

        # Create version-order pairs and sort
        version_order_pairs = list(zip(versions, sort_orders))
        version_order_pairs.sort(key=lambda x: x[1])

        return [version for version, _ in version_order_pairs]


class ProjectGroupService:
    """Service for managing project groups"""

    def __init__(self, project_service: ProjectService):
        self.project_service = project_service
        self._groups: Dict[str, ProjectGroup] = {}
        self._current_group_index = 0
        self._group_names: List[str] = []

    def load_project_groups(self):
        """Load and group all projects by name"""
        self._groups.clear()
        self._group_names.clear()

        # Get all projects
        projects = self.project_service.find_two_layer_projects()

        # Group projects by name
        for project in projects:
            if project.name not in self._groups:
                self._groups[project.name] = ProjectGroup(
                    project.name, self.project_service
                )

            self._groups[project.name].add_project(project)

        # Sort group names
        self._group_names = sorted(self._groups.keys())

        # Reset current group index
        self._current_group_index = 0 if self._group_names else -1

    def get_group_names(self) -> List[str]:
        """Get all group names"""
        return self._group_names.copy()

    def get_current_group(self) -> Optional[ProjectGroup]:
        """Get the currently selected project group"""
        if 0 <= self._current_group_index < len(self._group_names):
            group_name = self._group_names[self._current_group_index]
            return self._groups[group_name]
        return None

    def get_current_group_name(self) -> Optional[str]:
        """Get the name of the currently selected project group"""
        if 0 <= self._current_group_index < len(self._group_names):
            return self._group_names[self._current_group_index]
        return None

    def get_current_group_index(self) -> int:
        """Get the current group index"""
        return self._current_group_index

    def set_current_group_by_index(self, index: int) -> bool:
        """Set the current group by index. Returns True if successful."""
        if 0 <= index < len(self._group_names):
            self._current_group_index = index
            return True
        return False

    def set_current_group_by_name(self, name: str) -> bool:
        """Set the current group by name. Returns True if successful."""
        if name in self._group_names:
            self._current_group_index = self._group_names.index(name)
            return True
        return False

    def has_next_group(self) -> bool:
        """Check if there's a next group"""
        return self._current_group_index < len(self._group_names) - 1

    def has_previous_group(self) -> bool:
        """Check if there's a previous group"""
        return self._current_group_index > 0

    def next_group(self) -> bool:
        """Move to the next group. Returns True if successful."""
        if self.has_next_group():
            self._current_group_index += 1
            return True
        return False

    def previous_group(self) -> bool:
        """Move to the previous group. Returns True if successful."""
        if self.has_previous_group():
            self._current_group_index -= 1
            return True
        return False

    def get_group_count(self) -> int:
        """Get the total number of project groups"""
        return len(self._group_names)

    def get_group_by_name(self, name: str) -> Optional[ProjectGroup]:
        """Get a specific project group by name"""
        return self._groups.get(name)

    # ========== ASYNC METHODS ==========

    async def load_project_groups_async(self):
        """Async version of load_project_groups using async project finding"""
        if not ASYNC_AVAILABLE:
            return await run_in_executor(self.load_project_groups)

        self._groups.clear()
        self._group_names.clear()

        # Get all projects asynchronously
        projects = await self.project_service.find_two_layer_projects_async()

        # Group projects by name
        for project in projects:
            if project.name not in self._groups:
                self._groups[project.name] = ProjectGroup(
                    project.name, self.project_service
                )

            self._groups[project.name].add_project(project)

        # Sort group names
        self._group_names = sorted(self._groups.keys())

        # Reset current group index
        self._current_group_index = 0 if self._group_names else -1

    async def get_group_names_async(self) -> List[str]:
        """Async version of get_group_names"""
        return await run_in_executor(self.get_group_names)

    async def get_current_group_async(self) -> Optional[ProjectGroup]:
        """Async version of get_current_group"""
        return await run_in_executor(self.get_current_group)

    async def get_current_group_name_async(self) -> Optional[str]:
        """Async version of get_current_group_name"""
        return await run_in_executor(self.get_current_group_name)

    async def get_current_group_index_async(self) -> int:
        """Async version of get_current_group_index"""
        return await run_in_executor(self.get_current_group_index)

    async def set_current_group_by_index_async(self, index: int) -> bool:
        """Async version of set_current_group_by_index"""
        return await run_in_executor(self.set_current_group_by_index, index)

    async def set_current_group_by_name_async(self, name: str) -> bool:
        """Async version of set_current_group_by_name"""
        return await run_in_executor(self.set_current_group_by_name, name)

    async def has_next_group_async(self) -> bool:
        """Async version of has_next_group"""
        return await run_in_executor(self.has_next_group)

    async def has_previous_group_async(self) -> bool:
        """Async version of has_previous_group"""
        return await run_in_executor(self.has_previous_group)

    async def next_group_async(self) -> bool:
        """Async version of next_group"""
        return await run_in_executor(self.next_group)

    async def previous_group_async(self) -> bool:
        """Async version of previous_group"""
        return await run_in_executor(self.previous_group)

    async def get_group_count_async(self) -> int:
        """Async version of get_group_count"""
        return await run_in_executor(self.get_group_count)

    async def get_group_by_name_async(self, name: str) -> Optional[ProjectGroup]:
        """Async version of get_group_by_name"""
        return await run_in_executor(self.get_group_by_name, name)

    async def get_all_groups_with_sorted_versions_async(
        self,
    ) -> Dict[str, List[Project]]:
        """Get all groups with their versions sorted asynchronously"""
        if not ASYNC_AVAILABLE:
            result = {}
            for name, group in self._groups.items():
                result[name] = group.get_all_versions()
            return result

        result = {}

        # Get all groups and their sorted versions concurrently
        sort_tasks = []
        group_names = []

        for name, group in self._groups.items():
            sort_tasks.append(group.get_all_versions_async())
            group_names.append(name)

        if sort_tasks:
            sorted_versions_list = await asyncio.gather(*sort_tasks)
            result = dict(zip(group_names, sorted_versions_list))

        return result
