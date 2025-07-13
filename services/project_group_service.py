"""
Service for grouping projects by name and managing project navigation
"""

import asyncio
from typing import List, Dict, Optional, Callable
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

    def get_version_count(self) -> int:
        """Get the number of versions in this group"""
        return len(self.versions)

    def get_folder_names(self) -> List[str]:
        """Get all folder names for this group"""
        return list(self.versions.keys())

    def get_project_info(self) -> Dict:
        """Get structured information about this project group"""
        return {
            "name": self.name,
            "version_count": self.get_version_count(),
            "folder_names": self.get_folder_names(),
            "projects": [
                {
                    "name": project.name,
                    "parent": project.parent,
                    "alias": self.project_service.get_folder_alias(project.parent),
                    "path": str(project.path),
                    "relative_path": project.relative_path,
                }
                for project in self.get_all_versions()
            ],
        }


class ProjectGroupService:
    """Service for managing project groups"""

    def __init__(self, project_service: ProjectService):
        self.project_service = project_service
        self._groups: Dict[str, ProjectGroup] = {}
        self._current_group_index = 0
        self._group_names: List[str] = []
        self._selection_callbacks: List[Callable[[str], None]] = []

    def add_selection_callback(self, callback: Callable[[str], None]):
        """Add a callback to be called when project selection changes"""
        if callback not in self._selection_callbacks:
            self._selection_callbacks.append(callback)

    def remove_selection_callback(self, callback: Callable[[str], None]):
        """Remove a selection callback"""
        if callback in self._selection_callbacks:
            self._selection_callbacks.remove(callback)

    def _notify_selection_changed(self, group_name: str):
        """Notify all callbacks about selection change"""
        for callback in self._selection_callbacks:
            try:
                callback(group_name)
            except Exception as e:
                # Log error but don't let callback failures break the system
                print(f"Error in selection callback: {e}")

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

    def set_current_group_by_name(self, group_name: str) -> bool:
        """Set the current group by name and notify callbacks"""
        if group_name in self._group_names:
            self._current_group_index = self._group_names.index(group_name)
            self._notify_selection_changed(group_name)
            return True
        return False

    def set_current_group_by_index(self, index: int) -> bool:
        """Set the current group by index and notify callbacks"""
        if 0 <= index < len(self._group_names):
            self._current_group_index = index
            group_name = self._group_names[index]
            self._notify_selection_changed(group_name)
            return True
        return False

    def get_next_group(self) -> Optional[ProjectGroup]:
        """Get the next project group"""
        if self._group_names:
            next_index = (self._current_group_index + 1) % len(self._group_names)
            if self.set_current_group_by_index(next_index):
                return self.get_current_group()
        return None

    def get_previous_group(self) -> Optional[ProjectGroup]:
        """Get the previous project group"""
        if self._group_names:
            prev_index = (self._current_group_index - 1) % len(self._group_names)
            if self.set_current_group_by_index(prev_index):
                return self.get_current_group()
        return None

    def get_group_by_name(self, group_name: str) -> Optional[ProjectGroup]:
        """Get a project group by name without changing current selection"""
        return self._groups.get(group_name)

    def get_all_groups(self) -> List[ProjectGroup]:
        """Get all project groups"""
        return list(self._groups.values())

    def get_group_count(self) -> int:
        """Get the total number of project groups"""
        return len(self._groups)

    def has_group(self, group_name: str) -> bool:
        """Check if a group exists"""
        return group_name in self._groups

    def get_system_status(self) -> Dict:
        """Get system status information"""
        return {
            "total_groups": self.get_group_count(),
            "current_group": self.get_current_group_name(),
            "current_index": self.get_current_group_index(),
            "group_names": self.get_group_names(),
        }

    # ========== ASYNC METHODS ==========

    async def load_project_groups_async(self):
        """Async version of load_project_groups"""
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

    async def get_folder_alias_async(self, folder_name: str) -> Optional[str]:
        """Async version of get_folder_alias"""
        return await self.project_service.get_folder_alias_async(folder_name)
