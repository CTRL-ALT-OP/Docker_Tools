"""
Service for managing projects and folder aliases
"""

from pathlib import Path
from typing import List, Optional

from config.settings import FOLDER_ALIASES
from models.project import Project


class ProjectService:
    """Service for managing projects and folder aliases"""

    def __init__(self, root_dir: str = "."):
        self.root_dir = Path(root_dir).resolve()

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
