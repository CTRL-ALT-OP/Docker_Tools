"""
Service for building Docker files based on codebase analysis
"""

import os
import shutil
import asyncio
from pathlib import Path
from typing import Tuple, List, Callable, Optional

from config.settings import FOLDER_ALIASES
from services.project_group_service import ProjectGroup
from models.project import Project


class DockerFilesService:
    """Service for building and distributing Docker files across project versions"""

    def __init__(self):
        self.defaults_dir = Path("defaults")

    async def build_docker_files_for_project_group(
        self,
        project_group: ProjectGroup,
        output_callback: Callable[[str], None],
        status_callback: Callable[[str, str], None],
    ) -> Tuple[bool, str]:
        """
        Build Docker files for a project group based on pre-edit version analysis
        Returns (success, message)
        """
        return False, "Not implemented"

    def _find_pre_edit_version(self, project_group: ProjectGroup) -> Optional[Project]:
        return None

    async def _check_existing_docker_files(
        self, project: Project, output_callback: Callable[[str], None]
    ) -> List[str]:
        return []

    async def _search_for_tkinter_imports(self, project_path: Path) -> bool:
        return False

    async def _check_opencv_in_requirements(self, project_path: Path) -> bool:
        return False

    async def _build_dockerignore(
        self, project: Project, output_callback: Callable[[str], None]
    ):
        pass

    async def _ensure_requirements_txt(
        self, project: Project, output_callback: Callable[[str], None]
    ):
        pass

    async def _copy_build_docker_sh(
        self, project: Project, output_callback: Callable[[str], None]
    ):
        pass

    async def _copy_run_tests_sh(
        self,
        project: Project,
        has_tkinter: bool,
        has_opencv: bool,
        output_callback: Callable[[str], None],
    ):
        pass

    async def _copy_dockerfile(
        self,
        project: Project,
        has_tkinter: bool,
        has_opencv: bool,
        output_callback: Callable[[str], None],
    ):
        pass

    async def _copy_files_to_all_versions(
        self,
        project_group: ProjectGroup,
        source_project: Project,
        output_callback: Callable[[str], None],
    ) -> Tuple[bool, str]:
        return False, "Not implemented"

    async def remove_existing_docker_files(
        self, project: Project, output_callback: Callable[[str], None]
    ) -> bool:
        return False
