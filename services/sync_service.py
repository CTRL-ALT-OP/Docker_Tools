"""
Service for synchronizing files between project versions
"""

import shutil
from pathlib import Path
from typing import List, Tuple, Optional
from models.project import Project
from services.project_group_service import ProjectGroup
from services.project_service import ProjectService


class SyncService:
    """Service for synchronizing files between project versions"""

    def __init__(self):
        self.project_service = ProjectService()

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
        # Get the pre-edit version
        pre_edit_project = self.get_pre_edit_version(project_group)
        if not pre_edit_project:
            return False, "No pre-edit version found in project group", []

        # Check if the file exists in pre-edit version
        if not self.has_file(pre_edit_project, file_name):
            return False, f"File '{file_name}' not found in pre-edit version", []

        # Get all non-pre-edit versions to sync to
        target_projects = self.get_non_pre_edit_versions(project_group)
        if not target_projects:
            return (
                True,
                f"File '{file_name}' successfully synced (no target versions found)",
                [],
            )

        # Sync the file to all target versions
        synced_paths = []
        failed_syncs = []

        for target_project in target_projects:
            if self.copy_file(pre_edit_project, target_project, file_name):
                synced_paths.append(str(target_project.path / file_name))
            else:
                failed_syncs.append(target_project.parent)

        # Determine success and create appropriate message
        total_targets = len(target_projects)
        successful_syncs = len(synced_paths)

        if successful_syncs == total_targets:
            message = f"File '{file_name}' successfully synced to {successful_syncs} version(s)"
            return True, message, synced_paths
        elif successful_syncs > 0:
            message = f"File '{file_name}' partially synced to {successful_syncs}/{total_targets} versions. Failed: {', '.join(failed_syncs)}"
            return False, message, synced_paths
        else:
            message = f"Failed to sync file '{file_name}' to any target versions"
            return False, message, synced_paths

    def get_pre_edit_version(self, project_group: ProjectGroup) -> Optional[Project]:
        """
        Get the pre-edit version from a project group.

        Args:
            project_group: The project group to search in

        Returns:
            Project object for pre-edit version or None if not found
        """
        return next(
            (
                project
                for project in project_group.get_all_versions()
                if self.project_service.get_folder_alias(project.parent) == "preedit"
            ),
            None,
        )

    def has_file(self, project: Project, file_name: str) -> bool:
        """
        Check if a project has a file.

        Args:
            project: The project to check
            file_name: The name of the file to check for

        Returns:
            True if file exists, False otherwise
        """
        file_path = project.path / file_name
        return file_path.exists() and file_path.is_file()

    def copy_file(
        self, source_project: Project, target_project: Project, file_name: str
    ) -> bool:
        """
        Copy a file from source project to target project.

        Args:
            source_project: Project to copy from
            target_project: Project to copy to
            file_name: The name of the file to copy

        Returns:
            True if copy was successful, False otherwise
        """
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
            # Return False for any copy errors (permissions, disk space, etc.)
            return False

    def get_non_pre_edit_versions(self, project_group: ProjectGroup) -> List[Project]:
        """
        Get all versions in a project group except the pre-edit version.

        Args:
            project_group: The project group to filter

        Returns:
            List of projects excluding pre-edit version
        """
        return [
            project
            for project in project_group.get_all_versions()
            if project.parent != "pre-edit"
        ]
