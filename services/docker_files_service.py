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
        try:
            status_callback("Starting Docker file generation...", "#f39c12")

            # Find the pre-edit version
            pre_edit_project = self._find_pre_edit_version(project_group)
            if not pre_edit_project:
                error_msg = (
                    "No pre-edit version found in project group. Cannot proceed."
                )
                output_callback(f"❌ {error_msg}\n")
                return False, error_msg

            output_callback(
                f"📁 Found pre-edit version: {pre_edit_project.relative_path}\n"
            )

            # Check for existing Docker files
            status_callback("Checking for existing Docker files...", "#f39c12")
            existing_files = await self._check_existing_docker_files(
                pre_edit_project, output_callback
            )

            if existing_files:
                # This should be handled by the calling method with a user prompt
                return (
                    False,
                    f"Existing Docker files found: {', '.join(existing_files)}",
                )

            # Analyze codebase for dependencies
            status_callback("Analyzing codebase for dependencies...", "#f39c12")
            has_tkinter, has_opencv = await self._analyze_codebase(
                pre_edit_project, output_callback
            )

            # Build Docker files
            status_callback("Building Docker files...", "#f39c12")
            success, message = await self._build_docker_files(
                pre_edit_project, has_tkinter, has_opencv, output_callback
            )

            if not success:
                return False, message

            # Copy files to all versions
            status_callback("Copying files to all project versions...", "#f39c12")
            copy_success, copy_message = await self._copy_files_to_all_versions(
                project_group, pre_edit_project, None, output_callback
            )

            if not copy_success:
                return False, copy_message

            status_callback(
                "Docker files generation completed successfully!", "#27ae60"
            )
            output_callback("\n✅ Docker files generation completed successfully!\n")
            return True, "Docker files generated and distributed successfully"
        except Exception as e:
            error_msg = f"Error building Docker files: {str(e)}"
            output_callback(f"❌ {error_msg}\n")
            return False, error_msg

    def _find_pre_edit_version(self, project_group: ProjectGroup) -> Optional[Project]:
        """Find the pre-edit version from the project group"""
        # Look for folders that match the pre-edit aliases
        pre_edit_aliases = FOLDER_ALIASES.get("preedit", ["pre-edit", "original"])

        for alias in pre_edit_aliases:
            if version := project_group.get_version(alias):
                return version

        return None

    async def _check_existing_docker_files(
        self, project: Project, output_callback: Callable[[str], None]
    ) -> List[str]:
        """Check for existing Docker files that would be overwritten"""
        docker_files = [
            ".dockerignore",
            "run_tests.sh",
            "build_docker.sh",
            "Dockerfile",
        ]
        existing_files = []

        for file_name in docker_files:
            file_path = project.path / file_name
            if file_path.exists():
                existing_files.append(file_name)

        if existing_files:
            output_callback(
                f"⚠️  Found existing Docker files: {', '.join(existing_files)}\n"
            )

        return existing_files

    async def _detect_programming_language(
        self, project: Project, output_callback: Callable[[str], None]
    ) -> str:
        pass

    async def _analyze_codebase(
        self, project: Project, output_callback: Callable[[str], None]
    ) -> Tuple[bool, bool]:
        """Analyze codebase for tkinter and opencv dependencies"""
        has_tkinter = False
        has_opencv = False

        # Check for tkinter imports
        output_callback("🔍 Searching for tkinter imports...\n")
        has_tkinter = await self._search_for_tkinter_imports(project.path)
        if has_tkinter:
            output_callback("   ✅ Found tkinter imports - flagging as tkinter-based\n")
        else:
            output_callback("   ➖ No tkinter imports found\n")

        # Check for opencv in requirements.txt
        output_callback("🔍 Checking requirements.txt for opencv-python...\n")
        has_opencv = await self._check_opencv_in_requirements(project.path)
        if has_opencv:
            output_callback(
                "   ✅ Found opencv-python in requirements.txt - flagging as opencv-based\n"
            )
        else:
            output_callback("   ➖ No opencv-python found in requirements.txt\n")

        # Report final analysis
        if has_tkinter and has_opencv:
            output_callback("📊 Final analysis: tkinter + opencv codebase\n")
        elif has_tkinter:
            output_callback("📊 Final analysis: tkinter codebase\n")
        elif has_opencv:
            output_callback("📊 Final analysis: opencv codebase\n")
        else:
            output_callback("📊 Final analysis: standard codebase\n")

        return has_tkinter, has_opencv

    async def _search_for_tkinter_imports(self, project_path: Path) -> bool:
        """Search for tkinter imports in Python files"""
        try:
            for py_file in project_path.rglob("*.py"):
                if py_file.is_file():
                    try:
                        with open(py_file, "r", encoding="utf-8") as f:
                            content = f.read()
                            if (
                                "import tkinter" in content
                                or "from tkinter" in content
                                or "import Tkinter" in content
                                or "from Tkinter" in content
                            ):
                                return True
                    except (UnicodeDecodeError, PermissionError):
                        # Skip files that can't be read
                        continue
            return False
        except Exception:
            return False

    async def _check_opencv_in_requirements(self, project_path: Path) -> bool:
        """Check if opencv-python is in requirements.txt"""
        requirements_file = project_path / "requirements.txt"
        if not requirements_file.exists():
            return False

        try:
            with open(requirements_file, "r", encoding="utf-8") as f:
                content = f.read().lower()
                return "opencv-python" in content
        except (UnicodeDecodeError, PermissionError):
            return False

    async def _build_docker_files(
        self,
        project: Project,
        has_tkinter: bool,
        has_opencv: bool,
        output_callback: Callable[[str], None],
    ) -> Tuple[bool, str]:
        """Build the Docker files based on analysis"""
        try:
            # 0.5. Create blank requirements.txt if it doesn't exist
            output_callback("📝 Checking requirements.txt...\n")
            await self._ensure_language_files(project, None, output_callback)

            # 1. Build .dockerignore from .gitignore
            output_callback("📝 Building .dockerignore...\n")
            await self._build_dockerignore(project, output_callback)

            # 2. Copy build_docker.sh
            output_callback("📝 Copying build_docker.sh...\n")
            await self._copy_build_docker_sh(project, None, output_callback)

            # 3. Copy appropriate run_tests.sh
            output_callback("📝 Copying run_tests.sh...\n")
            await self._copy_run_tests_sh(
                project, None, has_tkinter, has_opencv, output_callback
            )

            # 4. Copy appropriate Dockerfile
            output_callback("📝 Copying Dockerfile...\n")
            await self._copy_dockerfile(
                project, has_tkinter, has_opencv, output_callback
            )

            return True, "Docker files built successfully"

        except Exception as e:
            return False, f"Error building Docker files: {str(e)}"

    async def _build_dockerignore(
        self, project: Project, output_callback: Callable[[str], None]
    ):
        """Build .dockerignore from .gitignore with additional line"""
        gitignore_path = project.path / ".gitignore"
        dockerignore_path = project.path / ".dockerignore"

        # Start with .gitignore content if it exists
        content = ""
        if gitignore_path.exists():
            with open(gitignore_path, "r", encoding="utf-8") as f:
                content = f.read()
            output_callback("   ✅ Based on existing .gitignore\n")
        else:
            output_callback("   ⚠️  No .gitignore found, creating empty .dockerignore\n")

        # Add the required line
        if not content.endswith("\n") and content:
            content += "\n"
        content += "!run_tests.sh\n"

        # Write .dockerignore
        with open(dockerignore_path, "w", encoding="utf-8") as f:
            f.write(content)

        output_callback("   ✅ Created .dockerignore with '!run_tests.sh' line\n")

    async def _ensure_language_files(
        self, project: Project, language: str, output_callback: Callable[[str], None]
    ):
        """Ensure requirements.txt exists, create blank one if it doesn't"""
        requirements_path = project.path / "requirements.txt"

        if requirements_path.exists():
            output_callback("   ✅ requirements.txt already exists\n")
        else:
            # Create blank requirements.txt
            with open(requirements_path, "w", encoding="utf-8") as f:
                f.write("# Add your project dependencies here\n")
            output_callback("   ✅ Created blank requirements.txt\n")

    async def _copy_build_docker_sh(
        self, project: Project, language: str, output_callback: Callable[[str], None]
    ):
        """Copy build_docker.sh from defaults"""
        source = self.defaults_dir / "build_docker.sh"
        dest = project.path / "build_docker.sh"

        if not source.exists():
            raise FileNotFoundError(f"Template file not found: {source}")

        shutil.copy2(source, dest)
        # Make it executable
        os.chmod(dest, 0o755)
        output_callback("   ✅ Copied and made executable: build_docker.sh\n")

    async def _copy_run_tests_sh(
        self,
        project: Project,
        language: str,
        has_tkinter: bool,
        has_opencv: bool,
        output_callback: Callable[[str], None],
    ):
        """Copy appropriate run_tests.sh based on flags"""
        # Determine which template to use
        if has_tkinter and has_opencv:
            template_name = "run_tests_opencv_tkinter.sh"
            description = "opencv + tkinter version"
        elif has_tkinter:
            template_name = "run_tests_tkinter.sh"
            description = "tkinter version"
        elif has_opencv:
            template_name = "run_tests_opencv.sh"
            description = "opencv version"
        else:
            template_name = "run_tests.sh"
            description = "default version"

        source = self.defaults_dir / template_name
        dest = project.path / "run_tests.sh"

        if not source.exists():
            raise FileNotFoundError(f"Template file not found: {source}")

        shutil.copy2(source, dest)
        # Make it executable
        os.chmod(dest, 0o755)
        output_callback(f"   ✅ Copied {description}: run_tests.sh\n")

    async def _copy_dockerfile(
        self,
        project: Project,
        has_tkinter: bool,
        has_opencv: bool,
        output_callback: Callable[[str], None],
    ):
        """Copy appropriate Dockerfile based on flags"""
        # Determine which template to use
        if has_tkinter and has_opencv:
            template_name = "Dockerfile_opencv_tkinter.txt"
            description = "opencv + tkinter version"
        elif has_tkinter:
            template_name = "Dockerfile_tkinter"
            description = "tkinter version"
        elif has_opencv:
            template_name = "Dockerfile_opencv"
            description = "opencv version"
        else:
            template_name = "Dockerfile"
            description = "default version"

        source = self.defaults_dir / template_name
        dest = project.path / "Dockerfile"

        if not source.exists():
            raise FileNotFoundError(f"Template file not found: {source}")

        shutil.copy2(source, dest)
        output_callback(f"   ✅ Copied {description}: Dockerfile\n")

    async def _copy_files_to_all_versions(
        self,
        project_group: ProjectGroup,
        source_project: Project,
        language: str,
        output_callback: Callable[[str], None],
    ) -> Tuple[bool, str]:
        """Copy generated Docker files to all other versions of the project"""
        docker_files = [
            ".dockerignore",
            "run_tests.sh",
            "build_docker.sh",
            "Dockerfile",
            "requirements.txt",
        ]
        all_versions = project_group.get_all_versions()

        # Filter out the source project
        target_versions = [v for v in all_versions if v.path != source_project.path]

        if not target_versions:
            output_callback("ℹ️  No other versions to copy to\n")
            return True, "No additional versions found"

        output_callback(f"📋 Copying to {len(target_versions)} other versions:\n")

        copied_count = 0
        for version in target_versions:
            output_callback(f"   📂 Copying to {version.relative_path}...\n")

            # Remove existing Docker files in target
            for file_name in docker_files:
                target_file = version.path / file_name
                if target_file.exists():
                    target_file.unlink()

            # Copy files from source
            for file_name in docker_files:
                source_file = source_project.path / file_name
                target_file = version.path / file_name

                if source_file.exists():
                    shutil.copy2(source_file, target_file)
                    # Preserve executable permissions for shell scripts
                    if file_name.endswith(".sh"):
                        os.chmod(target_file, 0o755)

            copied_count += 1
            output_callback(f"      ✅ Copied {len(docker_files)} files\n")

        output_callback(
            f"\n🎉 Successfully copied Docker files to {copied_count} versions!\n"
        )
        return True, f"Files copied to {copied_count} versions"

    async def remove_existing_docker_files(
        self, project: Project, output_callback: Callable[[str], None]
    ) -> bool:
        """Remove existing Docker files from the project"""
        docker_files = [
            ".dockerignore",
            "run_tests.sh",
            "build_docker.sh",
            "Dockerfile",
        ]
        removed_files = []

        for file_name in docker_files:
            file_path = project.path / file_name
            if file_path.exists():
                try:
                    file_path.unlink()
                    removed_files.append(file_name)
                except Exception as e:
                    output_callback(f"❌ Failed to remove {file_name}: {str(e)}\n")
                    return False

        if removed_files:
            output_callback(f"🗑️  Removed existing files: {', '.join(removed_files)}\n")

        return True
