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
        for alias, folder_list in FOLDER_ALIASES.items():
            if folder_name in folder_list:
                return alias
        return None

    def get_archive_name(self, parent_folder: str, project_name: str) -> str:
        """Generate archive name based on the specified naming convention"""
        project_clean = project_name.replace("-", "")

        # Check if parent folder has an alias
        alias = self.get_folder_alias(parent_folder)
        if alias:
            return f"{project_clean}_{alias}.zip"
        else:
            # Default behavior for folders without aliases
            parent_clean = parent_folder.replace("-", "")
            return f"{project_clean}_{parent_clean}.zip"

    def get_docker_tag(self, parent_folder: str, project_name: str) -> str:
        """Generate Docker tag based on parent folder and project name"""
        project_clean = project_name.replace("-", "")

        # Check if parent folder has an alias
        alias = self.get_folder_alias(parent_folder)
        if alias:
            return f"{project_clean}:{alias}"
        else:
            # Default behavior for folders without aliases
            parent_clean = parent_folder.replace("-", "")
            return f"{project_clean}:{parent_clean}"

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
