"""
Service for building Docker files based on codebase analysis
"""

import shutil
import asyncio
from pathlib import Path
from typing import Tuple, List, Callable, Optional

from config.config import get_config
from services.project_group_service import ProjectGroup
from services.platform_service import PlatformService
from models.project import Project

LANGUAGE_EXTENSIONS = get_config().language.extensions
LANGUAGE_REQUIRED_FILES = get_config().language.required_files
COLORS = get_config().gui.colors


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
            status_callback("Starting Docker file generation...", COLORS["warning"])

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
            status_callback("Checking for existing Docker files...", COLORS["warning"])
            existing_files = await self._check_existing_docker_files(
                pre_edit_project, output_callback
            )

            if existing_files:
                # This should be handled by the calling method with a user prompt
                return (
                    False,
                    f"Existing Docker files found: {', '.join(existing_files)}",
                )

            # Detect programming language
            status_callback("Detecting programming language...", COLORS["warning"])
            detected_language = await self._detect_programming_language(
                pre_edit_project, output_callback
            )
            output_callback(f"🔍 Detected language: {detected_language}\n")

            # Analyze codebase for language-specific dependencies
            status_callback("Analyzing codebase for dependencies...", COLORS["warning"])
            if detected_language == "python":
                has_tkinter, has_opencv = await self._analyze_python_codebase(
                    pre_edit_project, output_callback
                )
            else:
                has_tkinter, has_opencv = False, False
                output_callback(
                    f"📊 Skipping Python-specific analysis for {detected_language} project\n"
                )

            # Build Docker files
            status_callback("Building Docker files...", COLORS["warning"])
            success, message = await self._build_docker_files(
                pre_edit_project,
                detected_language,
                has_tkinter,
                has_opencv,
                output_callback,
            )

            if not success:
                return False, message

            # Copy files to all versions
            status_callback(
                "Copying files to all project versions...", COLORS["warning"]
            )
            copy_success, copy_message = await self._copy_files_to_all_versions(
                project_group, pre_edit_project, detected_language, output_callback
            )

            if not copy_success:
                return False, copy_message

            status_callback(
                "Docker files generation completed successfully!", COLORS["success"]
            )
            output_callback("\n✅ Docker files generation completed successfully!\n")
            return True, "Docker files generated and distributed successfully"
        except Exception as e:
            error_msg = f"Error building Docker files: {str(e)}"
            output_callback(f"❌ {error_msg}\n")
            return False, error_msg

    def _find_pre_edit_version(self, project_group: ProjectGroup) -> Optional[Project]:
        """Find the pre-edit version from the project group"""
        # Check all versions in the project group to find one with preedit alias
        for version in project_group.get_all_versions():
            alias = project_group.project_service.get_folder_alias(version.parent)
            if alias == "preedit":
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
        """Detect the programming language based on file extensions"""
        from utils.language_detection import detect_project_language

        return detect_project_language(project.path, output_callback)

    async def _analyze_python_codebase(
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
        language: str,
        has_tkinter: bool,
        has_opencv: bool,
        output_callback: Callable[[str], None],
    ) -> Tuple[bool, str]:
        """Build the Docker files based on analysis"""
        try:
            # 1. Ensure language-specific required files exist
            output_callback(f"📝 Ensuring {language} required files...\n")
            await self._ensure_language_files(project, language, output_callback)

            # 2. Build .dockerignore from .gitignore
            output_callback("📝 Building .dockerignore...\n")
            await self._build_dockerignore(project, output_callback)

            # 3. Copy build_docker.sh
            output_callback("📝 Copying build_docker.sh...\n")
            await self._copy_build_docker_sh(project, language, output_callback)

            # 4. Copy appropriate run_tests.sh
            output_callback("📝 Copying run_tests.sh...\n")
            await self._copy_run_tests_sh(
                project, language, has_tkinter, has_opencv, output_callback
            )

            # 5. Copy appropriate Dockerfile
            output_callback("📝 Copying Dockerfile...\n")
            await self._copy_dockerfile(
                project, language, has_tkinter, has_opencv, output_callback
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
        """Ensure language-specific required files exist"""
        required_files = LANGUAGE_REQUIRED_FILES.get(language, [])

        if not required_files:
            output_callback(f"   ➖ No required files for {language}\n")
            return

        for file_name in required_files:
            file_path = project.path / file_name

            if file_path.exists():
                output_callback(f"   ✅ {file_name} already exists\n")
            else:
                # Create the required file with appropriate content
                await self._create_language_file(
                    project, file_name, language, output_callback
                )

    async def _create_language_file(
        self,
        project: Project,
        file_name: str,
        language: str,
        output_callback: Callable[[str], None],
    ):
        """Create a language-specific required file with appropriate content"""
        file_path = project.path / file_name

        if file_name == "CMakeLists.txt":
            content = """cmake_minimum_required(VERSION 3.10)

# Project name
project(MyProject)

# Set C++ standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find all source files
file(GLOB_RECURSE SOURCES "src/*.cpp" "src/*.c")
file(GLOB_RECURSE HEADERS "src/*.h" "src/*.hpp")

# Add executable
add_executable(${PROJECT_NAME} ${SOURCES} ${HEADERS})

# Add include directories
target_include_directories(${PROJECT_NAME} PRIVATE src)

# Add any additional libraries here
# target_link_libraries(${PROJECT_NAME} library_name)

# Enable testing
enable_testing()

# Add tests if they exist
if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/tests")
    add_subdirectory(tests)
endif()
"""
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            output_callback(f"   ✅ Created {file_name}\n")
        elif file_name == "go.mod":
            # Get the project directory name for the module name
            project_name = project.path.name
            content = f"""module {project_name}

go 1.23

require (
	// Add your dependencies here
)
"""
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            output_callback(f"   ✅ Created {file_name}\n")
        elif file_name == "package-lock.json":
            content = """{
  "name": "project",
  "version": "1.0.0",
  "lockfileVersion": 2,
  "requires": true,
  "packages": {
    "": {
      "name": "project",
      "version": "1.0.0"
    }
  }
}
"""
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            output_callback(f"   ✅ Created {file_name}\n")

        elif file_name == "package.json":
            content = """{
  "name": "project",
  "version": "1.0.0",
  "description": "",
  "main": "index.js",
  "scripts": {
    "test": "echo \\"Error: no test specified\\" && exit 1"
  },
  "dependencies": {},
  "devDependencies": {}
}
"""
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            output_callback(f"   ✅ Created {file_name}\n")

        elif file_name == "pom.xml":
            content = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    
    <groupId>com.example</groupId>
    <artifactId>project</artifactId>
    <version>1.0.0</version>
    <packaging>jar</packaging>
    
    <properties>
        <maven.compiler.source>11</maven.compiler.source>
        <maven.compiler.target>11</maven.compiler.target>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    </properties>
    
    <dependencies>
        <!-- Add your dependencies here -->
    </dependencies>
</project>
"""
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            output_callback(f"   ✅ Created {file_name}\n")
        elif file_name == "requirements.txt":
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("# Add your Python project dependencies here\n")
            output_callback(f"   ✅ Created blank {file_name}\n")

    async def _copy_build_docker_sh(
        self, project: Project, language: str, output_callback: Callable[[str], None]
    ):
        """Copy build_docker.sh from language-specific defaults"""
        source = self.defaults_dir / language / "build_docker.sh"
        dest = project.path / "build_docker.sh"

        if not source.exists():
            raise FileNotFoundError(f"Template file not found: {source}")

        # Read source content and normalize line endings
        source_content = source.read_text(encoding="utf-8")
        normalized_content = source_content.replace("\r\n", "\n").replace("\r", "\n")

        # Write with Unix line endings
        dest.write_text(normalized_content, encoding="utf-8", newline="\n")

        # Make it executable using platform service
        success, error = await PlatformService.run_command_with_result_async(
            "FILE_PERMISSION_COMMANDS",
            subkey="make_executable",
            file_path=str(dest),
            capture_output=True,
            text=True,
        )

        if success:
            output_callback(
                f"   ✅ Copied {language} build_docker.sh with Unix line endings and made executable\n"
            )
        else:
            output_callback(
                f"   ⚠️  Copied {language} build_docker.sh but failed to make executable: {error}\n"
            )

    async def _copy_run_tests_sh(
        self,
        project: Project,
        language: str,
        has_tkinter: bool,
        has_opencv: bool,
        output_callback: Callable[[str], None],
    ):
        """Copy appropriate run_tests.sh based on language and flags"""
        # For Python projects, use the old logic with tkinter/opencv variants
        if language == "python":
            if has_tkinter and has_opencv:
                template_name = "run_tests_opencv_tkinter.sh"
                description = "python opencv + tkinter version"
            elif has_tkinter:
                template_name = "run_tests_tkinter.sh"
                description = "python tkinter version"
            elif has_opencv:
                template_name = "run_tests_opencv.sh"
                description = "python opencv version"
            else:
                template_name = "run_tests.sh"
                description = "python default version"
        else:
            # For other languages, use the default run_tests.sh from their language directory
            template_name = "run_tests.sh"
            description = f"{language} version"

        source = self.defaults_dir / language / template_name
        dest = project.path / "run_tests.sh"

        if not source.exists():
            raise FileNotFoundError(f"Template file not found: {source}")

        # Read source content and normalize line endings
        source_content = source.read_text(encoding="utf-8")
        normalized_content = source_content.replace("\r\n", "\n").replace("\r", "\n")

        # Write with Unix line endings
        dest.write_text(normalized_content, encoding="utf-8", newline="\n")

        # Make it executable using platform service
        success, error = await PlatformService.run_command_with_result_async(
            "FILE_PERMISSION_COMMANDS",
            subkey="make_executable",
            file_path=str(dest),
            capture_output=True,
            text=True,
        )

        if success:
            output_callback(
                f"   ✅ Copied {description}: run_tests.sh with Unix line endings\n"
            )
        else:
            output_callback(
                f"   ⚠️  Copied {description}: run_tests.sh but failed to make executable: {error}\n"
            )

    async def _copy_dockerfile(
        self,
        project: Project,
        language: str,
        has_tkinter: bool,
        has_opencv: bool,
        output_callback: Callable[[str], None],
    ):
        """Copy appropriate Dockerfile based on language and flags"""
        # For Python projects, use the old logic with tkinter/opencv variants
        if language == "python":
            if has_tkinter and has_opencv:
                template_name = "Dockerfile_opencv_tkinter"
                description = "python opencv + tkinter version"
            elif has_tkinter:
                template_name = "Dockerfile_tkinter"
                description = "python tkinter version"
            elif has_opencv:
                template_name = "Dockerfile_opencv"
                description = "python opencv version"
            else:
                template_name = "Dockerfile"
                description = "python default version"
        else:
            # For other languages, use the default Dockerfile from their language directory
            template_name = "Dockerfile"
            description = f"{language} version"

        source = self.defaults_dir / language / template_name
        dest = project.path / "Dockerfile"

        if not source.exists():
            raise FileNotFoundError(f"Template file not found: {source}")

        # Use platform service for standardized file copying
        copy_success, copy_error = PlatformService.copy_file(
            str(source), str(dest), preserve_attrs=True
        )
        if not copy_success:
            raise RuntimeError(f"Failed to copy Dockerfile: {copy_error}")
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
        ]

        # Add language-specific files that should be copied
        required_files = LANGUAGE_REQUIRED_FILES.get(language, [])
        docker_files.extend(required_files)
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
                    if file_name.endswith(".sh"):
                        # For shell scripts, read and normalize line endings
                        source_content = source_file.read_text(encoding="utf-8")
                        normalized_content = source_content.replace(
                            "\r\n", "\n"
                        ).replace("\r", "\n")

                        # Only write if target doesn't exist or content is different
                        write_file = True
                        if target_file.exists():
                            existing_content = target_file.read_text(encoding="utf-8")
                            if existing_content == normalized_content:
                                write_file = False

                        if write_file:
                            target_file.write_text(
                                normalized_content, encoding="utf-8", newline="\n"
                            )
                    else:
                        # For other files, use platform service for standardized copying
                        copy_success, copy_error = PlatformService.copy_file(
                            str(source_file), str(target_file), preserve_attrs=True
                        )
                        if not copy_success:
                            raise RuntimeError(
                                f"Failed to copy {file_name}: {copy_error}"
                            )

                    # Preserve executable permissions for shell scripts
                    if file_name.endswith(".sh"):
                        success, error = (
                            await PlatformService.run_command_with_result_async(
                                "FILE_PERMISSION_COMMANDS",
                                subkey="make_executable",
                                file_path=str(target_file),
                                capture_output=True,
                                text=True,
                            )
                        )
                        if not success:
                            output_callback(
                                f"      ⚠️  Failed to make {file_name} executable: {error}\n"
                            )

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
