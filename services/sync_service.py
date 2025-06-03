"""
Service for synchronizing files between project versions
"""

from pathlib import Path
from typing import List, Tuple, Optional
from models.project import Project
from services.project_group_service import ProjectGroup


class SyncService:
    """Service for synchronizing files between project versions"""

    def __init__(self):
        pass

    def sync_file_from_pre_edit(
        self, project_group: ProjectGroup, file_name: str
    ) -> Tuple[bool, str, List[str]]:
        """
        Sync a file from the pre-edit version to all other versions in the project group.

        Args:
            project_group: The project group containing all versions
            file_name: The name of the file to sync

        Returns:
            Tuple of (success: bool, message: str, synced_paths: List[str])
        """
        pass

    def get_pre_edit_version(self, project_group: ProjectGroup) -> Optional[Project]:
        """
        Get the pre-edit version from a project group.

        Args:
            project_group: The project group to search in

        Returns:
            Project object for pre-edit version or None if not found
        """
        pass

    def has_file(self, project: Project, file_name: str) -> bool:
        """
        Check if a project has a file.

        Args:
            project: The project to check

        Returns:
            True if file exists, False otherwise
        """
        pass

    def copy_file(
        self, source_project: Project, target_project: Project, file_name: str
    ) -> bool:
        """
        Copy a file from source project to target project.

        Args:
            source_project: Project to copy from
            target_project: Project to copy to

        Returns:
            True if copy was successful, False otherwise
        """
        pass

    def get_non_pre_edit_versions(self, project_group: ProjectGroup) -> List[Project]:
        """
        Get all versions in a project group except the pre-edit version.

        Args:
            project_group: The project group to filter

        Returns:
            List of projects excluding pre-edit version
        """
        pass
