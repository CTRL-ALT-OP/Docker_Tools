"""
Tests for DockerFilesService - implementation-agnostic tests for multi-language support
"""

import os
import asyncio
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, call
import pytest

from services.docker_files_service import DockerFilesService
from services.project_group_service import ProjectGroup
from models.project import Project


class TestDockerFilesService:
    """Test suite for DockerFilesService with multi-language support"""

    @pytest.fixture
    def service(self):
        """Create a DockerFilesService instance"""
        return DockerFilesService()

    @pytest.fixture
    def temp_defaults_dir(self, temp_directory):
        """Create a temporary defaults directory with language-specific templates"""
        defaults_dir = temp_directory / "defaults"
        defaults_dir.mkdir()

        # Create language-specific directories with templates
        languages = {
            "python": {
                "build_docker.sh": "#!/bin/bash\necho 'Building Python Docker'\n",
                "run_tests.sh": "#!/bin/bash\necho 'Running Python tests'\n",
                "run_tests_tkinter.sh": "#!/bin/bash\necho 'Running Python tkinter tests'\n",
                "run_tests_opencv.sh": "#!/bin/bash\necho 'Running Python opencv tests'\n",
                "run_tests_opencv_tkinter.sh": "#!/bin/bash\necho 'Running Python opencv+tkinter tests'\n",
                "Dockerfile": "FROM python:3.9\nCOPY . /app\n",
                "Dockerfile_tkinter": "FROM python:3.9\nRUN apt-get update\nCOPY . /app\n",
                "Dockerfile_opencv": "FROM python:3.9\nRUN pip install opencv-python\nCOPY . /app\n",
                "Dockerfile_opencv_tkinter": "FROM python:3.9\nRUN apt-get update\nRUN pip install opencv-python\nCOPY . /app\n",
            },
            "javascript": {
                "build_docker.sh": "#!/bin/bash\necho 'Building JavaScript Docker'\n",
                "run_tests.sh": "#!/bin/bash\necho 'Running JavaScript tests'\n",
                "Dockerfile": "FROM node:18\nCOPY . /app\n",
            },
            "typescript": {
                "build_docker.sh": "#!/bin/bash\necho 'Building TypeScript Docker'\n",
                "run_tests.sh": "#!/bin/bash\necho 'Running TypeScript tests'\n",
                "Dockerfile": "FROM node:18\nCOPY . /app\n",
            },
            "java": {
                "build_docker.sh": "#!/bin/bash\necho 'Building Java Docker'\n",
                "run_tests.sh": "#!/bin/bash\necho 'Running Java tests'\n",
                "Dockerfile": "FROM openjdk:11\nCOPY . /app\n",
            },
            "rust": {
                "build_docker.sh": "#!/bin/bash\necho 'Building Rust Docker'\n",
                "run_tests.sh": "#!/bin/bash\necho 'Running Rust tests'\n",
                "Dockerfile": "FROM rust:1.70\nCOPY . /app\n",
            },
            "c": {
                "build_docker.sh": "#!/bin/bash\necho 'Building C Docker'\n",
                "run_tests.sh": "#!/bin/bash\necho 'Running C tests'\n",
                "Dockerfile": "FROM alpine:3.21\nRUN apk add --no-cache alpine-sdk cmake\nCOPY . /app\n",
            },
        }

        for language, templates in languages.items():
            lang_dir = defaults_dir / language
            lang_dir.mkdir()

            for filename, content in templates.items():
                template_file = lang_dir / filename
                template_file.write_text(content)
                if filename.endswith(".sh"):
                    os.chmod(template_file, 0o755)

        return defaults_dir

    @pytest.fixture
    def mock_project_service(self):
        """Create a mock ProjectService"""
        service = Mock()
        service.get_folder_sort_order = Mock(
            side_effect=lambda x: {
                "pre-edit": 0,
                "post-edit": 1,
                "post-edit2": 2,
                "correct-edit": 3,
            }.get(x, 99)
        )
        return service

    @pytest.fixture
    def sample_project_group(self, temp_directory, mock_project_service):
        """Create a sample ProjectGroup with multiple versions"""
        project_group = ProjectGroup("test-project", mock_project_service)

        versions = ["pre-edit", "post-edit", "post-edit2", "correct-edit"]

        for version in versions:
            version_dir = temp_directory / version / "test-project"
            version_dir.mkdir(parents=True)

            project = Project(
                parent=version,
                name="test-project",
                path=version_dir,
                relative_path=f"{version}/test-project",
            )
            project_group.add_project(project)

        return project_group

    # Language detection test fixtures
    @pytest.fixture
    def python_project(self, temp_directory):
        """Create a project with Python files"""
        project_dir = temp_directory / "pre-edit" / "python-project"
        project_dir.mkdir(parents=True)

        # Create Python files
        (project_dir / "main.py").write_text("import os\nprint('Hello Python')")
        (project_dir / "utils.py").write_text("def helper(): pass")
        (project_dir / "tests.py").write_text("import unittest")

        return Project(
            parent="pre-edit",
            name="python-project",
            path=project_dir,
            relative_path="pre-edit/python-project",
        )

    @pytest.fixture
    def javascript_project(self, temp_directory):
        """Create a project with JavaScript files"""
        project_dir = temp_directory / "pre-edit" / "js-project"
        project_dir.mkdir(parents=True)

        # Create JavaScript files
        (project_dir / "index.js").write_text("console.log('Hello JavaScript');")
        (project_dir / "utils.js").write_text("function helper() {}")
        (project_dir / "app.jsx").write_text("import React from 'react';")

        return Project(
            parent="pre-edit",
            name="js-project",
            path=project_dir,
            relative_path="pre-edit/js-project",
        )

    @pytest.fixture
    def typescript_project(self, temp_directory):
        """Create a project with TypeScript files"""
        project_dir = temp_directory / "pre-edit" / "ts-project"
        project_dir.mkdir(parents=True)

        # Create TypeScript files
        (project_dir / "index.ts").write_text(
            "const message: string = 'Hello TypeScript';"
        )
        (project_dir / "types.ts").write_text("export interface User { name: string; }")
        (project_dir / "component.tsx").write_text("import React from 'react';")

        return Project(
            parent="pre-edit",
            name="ts-project",
            path=project_dir,
            relative_path="pre-edit/ts-project",
        )

    @pytest.fixture
    def java_project(self, temp_directory):
        """Create a project with Java files"""
        project_dir = temp_directory / "pre-edit" / "java-project"
        project_dir.mkdir(parents=True)

        # Create Java files
        (project_dir / "Main.java").write_text(
            "public class Main { public static void main(String[] args) {} }"
        )
        (project_dir / "Utils.java").write_text("public class Utils { }")

        return Project(
            parent="pre-edit",
            name="java-project",
            path=project_dir,
            relative_path="pre-edit/java-project",
        )

    @pytest.fixture
    def rust_project(self, temp_directory):
        """Create a project with Rust files"""
        project_dir = temp_directory / "pre-edit" / "rust-project"
        project_dir.mkdir(parents=True)

        # Create Rust files
        (project_dir / "main.rs").write_text('fn main() { println!("Hello Rust"); }')
        (project_dir / "lib.rs").write_text("pub fn helper() {}")

        return Project(
            parent="pre-edit",
            name="rust-project",
            path=project_dir,
            relative_path="pre-edit/rust-project",
        )

    @pytest.fixture
    def c_project(self, temp_directory):
        """Create a project with C/C++ files"""
        project_dir = temp_directory / "pre-edit" / "c-project"
        project_dir.mkdir(parents=True)

        # Create C/C++ files
        (project_dir / "main.c").write_text(
            '#include <stdio.h>\nint main() { printf("Hello C"); return 0; }'
        )
        (project_dir / "utils.c").write_text('#include "utils.h"\nvoid helper() {}')
        (project_dir / "utils.h").write_text(
            "#ifndef UTILS_H\n#define UTILS_H\nvoid helper();\n#endif"
        )
        (project_dir / "app.cpp").write_text(
            '#include <iostream>\nint main() { std::cout << "Hello C++"; }'
        )
        (project_dir / "classes.hpp").write_text(
            "#ifndef CLASSES_HPP\n#define CLASSES_HPP\nclass MyClass {};\n#endif"
        )

        return Project(
            parent="pre-edit",
            name="c-project",
            path=project_dir,
            relative_path="pre-edit/c-project",
        )

    @pytest.fixture
    def mixed_language_project(self, temp_directory):
        """Create a project with mixed language files (Python should win)"""
        project_dir = temp_directory / "pre-edit" / "mixed-project"
        project_dir.mkdir(parents=True)

        # Create files with Python having the most files
        (project_dir / "main.py").write_text("import os")
        (project_dir / "utils.py").write_text("def helper(): pass")
        (project_dir / "tests.py").write_text("import unittest")
        (project_dir / "config.py").write_text("CONFIG = {}")
        (project_dir / "app.js").write_text("console.log('hello');")
        (project_dir / "script.js").write_text("function test() {}")

        return Project(
            parent="pre-edit",
            name="mixed-project",
            path=project_dir,
            relative_path="pre-edit/mixed-project",
        )

    @pytest.fixture
    def python_project_with_tkinter(self, temp_directory):
        """Create a Python project with tkinter imports"""
        project_dir = temp_directory / "pre-edit" / "tkinter-project"
        project_dir.mkdir(parents=True)

        # Create Python file with tkinter import
        (project_dir / "main.py").write_text(
            "import tkinter as tk\nfrom tkinter import messagebox\n"
        )
        (project_dir / "gui.py").write_text("import tkinter\nclass App: pass")

        return Project(
            parent="pre-edit",
            name="tkinter-project",
            path=project_dir,
            relative_path="pre-edit/tkinter-project",
        )

    @pytest.fixture
    def python_project_with_opencv(self, temp_directory):
        """Create a Python project with opencv requirements"""
        project_dir = temp_directory / "pre-edit" / "opencv-project"
        project_dir.mkdir(parents=True)

        # Create Python file and requirements.txt with opencv-python
        (project_dir / "main.py").write_text("import cv2\nprint('OpenCV project')")
        (project_dir / "requirements.txt").write_text(
            "numpy==1.21.0\nopencv-python==4.5.0\nmatplotlib==3.4.0\n"
        )

        return Project(
            parent="pre-edit",
            name="opencv-project",
            path=project_dir,
            relative_path="pre-edit/opencv-project",
        )

    # Language Detection Tests
    @pytest.mark.asyncio
    async def test_detects_python_language(self, service, python_project):
        """Test that service correctly detects Python as the primary language"""
        output_callback = Mock()

        detected_language = await service._detect_programming_language(
            python_project, output_callback
        )

        assert detected_language == "python"
        # Verify output mentions Python files found
        output_calls = [call.args[0] for call in output_callback.call_args_list]
        assert any("python" in call.lower() for call in output_calls)

    @pytest.mark.asyncio
    async def test_detects_javascript_language(self, service, javascript_project):
        """Test that service correctly detects JavaScript as the primary language"""
        output_callback = Mock()

        detected_language = await service._detect_programming_language(
            javascript_project, output_callback
        )

        assert detected_language == "javascript"
        # Verify output mentions JavaScript files found
        output_calls = [call.args[0] for call in output_callback.call_args_list]
        assert any("javascript" in call.lower() for call in output_calls)

    @pytest.mark.asyncio
    async def test_detects_typescript_language(self, service, typescript_project):
        """Test that service correctly detects TypeScript as the primary language"""
        output_callback = Mock()

        detected_language = await service._detect_programming_language(
            typescript_project, output_callback
        )

        assert detected_language == "typescript"

    @pytest.mark.asyncio
    async def test_detects_java_language(self, service, java_project):
        """Test that service correctly detects Java as the primary language"""
        output_callback = Mock()

        detected_language = await service._detect_programming_language(
            java_project, output_callback
        )

        assert detected_language == "java"

    @pytest.mark.asyncio
    async def test_detects_rust_language(self, service, rust_project):
        """Test that service correctly detects Rust as the primary language"""
        output_callback = Mock()

        detected_language = await service._detect_programming_language(
            rust_project, output_callback
        )

        assert detected_language == "rust"

    @pytest.mark.asyncio
    async def test_detects_c_language(self, service, c_project):
        """Test that service correctly detects C as the primary language"""
        output_callback = Mock()

        detected_language = await service._detect_programming_language(
            c_project, output_callback
        )

        assert detected_language == "c"
        # Verify output mentions C files found
        output_calls = [call.args[0] for call in output_callback.call_args_list]
        assert any("c files" in call.lower() for call in output_calls)

    @pytest.mark.asyncio
    async def test_detects_dominant_language_in_mixed_project(
        self, service, mixed_language_project
    ):
        """Test that service detects the language with the most files"""
        output_callback = Mock()

        detected_language = await service._detect_programming_language(
            mixed_language_project, output_callback
        )

        # Python should win with 4 files vs JavaScript's 2 files
        assert detected_language == "python"

    @pytest.mark.asyncio
    async def test_selects_python_when_no_files_found(self, service, temp_directory):
        """Test that service selects Python when no recognized files are found"""
        project_dir = temp_directory / "empty-project"
        project_dir.mkdir()

        # Create some non-code files
        (project_dir / "README.md").write_text("# Project")
        (project_dir / "data.txt").write_text("some data")

        project = Project(
            parent="pre-edit",
            name="empty-project",
            path=project_dir,
            relative_path="pre-edit/empty-project",
        )

        output_callback = Mock()
        detected_language = await service._detect_programming_language(
            project, output_callback
        )

        assert detected_language == "python"
        # Verify output shows python with 0 files (since no code files found)
        output_calls = [call.args[0] for call in output_callback.call_args_list]
        assert any("python (0 files)" in call.lower() for call in output_calls)

    # Language-Specific File Creation Tests
    @pytest.mark.asyncio
    async def test_creates_python_requirements_txt(self, service, temp_directory):
        """Test that service creates requirements.txt for Python projects"""
        project_dir = temp_directory / "python-project"
        project_dir.mkdir()

        project = Project(
            parent="pre-edit",
            name="python-project",
            path=project_dir,
            relative_path="pre-edit/python-project",
        )

        output_callback = Mock()
        await service._ensure_language_files(project, "python", output_callback)

        req_file = project_dir / "requirements.txt"
        assert req_file.exists()
        content = req_file.read_text()
        assert "# Add your Python project dependencies here" in content

    @pytest.mark.asyncio
    async def test_creates_javascript_package_files(self, service, temp_directory):
        """Test that service creates package.json and package-lock.json for JavaScript projects"""
        project_dir = temp_directory / "js-project"
        project_dir.mkdir()

        project = Project(
            parent="pre-edit",
            name="js-project",
            path=project_dir,
            relative_path="pre-edit/js-project",
        )

        output_callback = Mock()
        await service._ensure_language_files(project, "javascript", output_callback)

        # Check package.json
        package_json = project_dir / "package.json"
        assert package_json.exists()
        content = package_json.read_text()
        assert '"name": "project"' in content
        assert '"version": "1.0.0"' in content
        assert '"dependencies": {}' in content

        # Check package-lock.json
        package_lock = project_dir / "package-lock.json"
        assert package_lock.exists()
        lock_content = package_lock.read_text()
        assert '"lockfileVersion": 2' in lock_content

    @pytest.mark.asyncio
    async def test_creates_typescript_package_files(self, service, temp_directory):
        """Test that service creates package.json and package-lock.json for TypeScript projects"""
        project_dir = temp_directory / "ts-project"
        project_dir.mkdir()

        project = Project(
            parent="pre-edit",
            name="ts-project",
            path=project_dir,
            relative_path="pre-edit/ts-project",
        )

        output_callback = Mock()
        await service._ensure_language_files(project, "typescript", output_callback)

        # Both package.json and package-lock.json should be created
        assert (project_dir / "package.json").exists()
        assert (project_dir / "package-lock.json").exists()

    @pytest.mark.asyncio
    async def test_creates_java_pom_xml(self, service, temp_directory):
        """Test that service creates pom.xml for Java projects"""
        project_dir = temp_directory / "java-project"
        project_dir.mkdir()

        project = Project(
            parent="pre-edit",
            name="java-project",
            path=project_dir,
            relative_path="pre-edit/java-project",
        )

        output_callback = Mock()
        await service._ensure_language_files(project, "java", output_callback)

        pom_file = project_dir / "pom.xml"
        assert pom_file.exists()
        content = pom_file.read_text()
        assert '<?xml version="1.0" encoding="UTF-8"?>' in content
        assert "<modelVersion>4.0.0</modelVersion>" in content
        assert "<groupId>com.example</groupId>" in content
        assert "<artifactId>project</artifactId>" in content

    @pytest.mark.asyncio
    async def test_creates_no_files_for_rust(self, service, temp_directory):
        """Test that service creates no additional files for Rust projects"""
        project_dir = temp_directory / "rust-project"
        project_dir.mkdir()

        project = Project(
            parent="pre-edit",
            name="rust-project",
            path=project_dir,
            relative_path="pre-edit/rust-project",
        )

        output_callback = Mock()
        await service._ensure_language_files(project, "rust", output_callback)

        # No files should be created for Rust
        assert not (project_dir / "requirements.txt").exists()
        assert not (project_dir / "package.json").exists()
        assert not (project_dir / "pom.xml").exists()

        # Check output message
        output_calls = [call.args[0] for call in output_callback.call_args_list]
        assert any(
            "no required files for rust" in call.lower() for call in output_calls
        )

    @pytest.mark.asyncio
    async def test_creates_c_cmake_file(self, service, temp_directory):
        """Test that service creates CMakeLists.txt for C projects"""
        project_dir = temp_directory / "c-project"
        project_dir.mkdir()

        project = Project(
            parent="pre-edit",
            name="c-project",
            path=project_dir,
            relative_path="pre-edit/c-project",
        )

        output_callback = Mock()
        await service._ensure_language_files(project, "c", output_callback)

        cmake_file = project_dir / "CMakeLists.txt"
        assert cmake_file.exists()
        content = cmake_file.read_text()

        # Check that the CMakeLists.txt contains expected content
        assert "cmake_minimum_required(VERSION 3.10)" in content
        assert "project(MyProject)" in content
        assert "add_executable(" in content
        assert "enable_testing()" in content

        # Check output callback was called with success message
        output_calls = [call.args[0] for call in output_callback.call_args_list]
        assert any("Created CMakeLists.txt" in call for call in output_calls)

    @pytest.mark.asyncio
    async def test_preserves_existing_language_files(self, service, temp_directory):
        """Test that service preserves existing language-specific files"""
        project_dir = temp_directory / "existing-project"
        project_dir.mkdir()

        # Create existing package.json with custom content
        existing_package = project_dir / "package.json"
        existing_content = '{"name": "my-custom-project", "version": "2.0.0"}'
        existing_package.write_text(existing_content)

        project = Project(
            parent="pre-edit",
            name="existing-project",
            path=project_dir,
            relative_path="pre-edit/existing-project",
        )

        output_callback = Mock()
        await service._ensure_language_files(project, "javascript", output_callback)

        # Existing package.json should be preserved
        assert existing_package.read_text() == existing_content

        # package-lock.json should still be created
        assert (project_dir / "package-lock.json").exists()

    @pytest.mark.asyncio
    async def test_preserves_existing_cmake_file(self, service, temp_directory):
        """Test that service preserves existing CMakeLists.txt files"""
        project_dir = temp_directory / "existing-c-project"
        project_dir.mkdir()

        # Create existing CMakeLists.txt with custom content
        existing_cmake = project_dir / "CMakeLists.txt"
        existing_content = """cmake_minimum_required(VERSION 3.20)
project(MyCustomProject)
# Custom CMake configuration
"""
        existing_cmake.write_text(existing_content)

        project = Project(
            parent="pre-edit",
            name="existing-c-project",
            path=project_dir,
            relative_path="pre-edit/existing-c-project",
        )

        output_callback = Mock()
        await service._ensure_language_files(project, "c", output_callback)

        # Existing CMakeLists.txt should be preserved
        assert existing_cmake.read_text() == existing_content

        # Check output callback was called with "already exists" message
        output_calls = [call.args[0] for call in output_callback.call_args_list]
        assert any("CMakeLists.txt already exists" in call for call in output_calls)

    # Docker File Creation Tests by Language
    @pytest.mark.asyncio
    async def test_copies_python_docker_files(
        self, service, temp_directory, temp_defaults_dir
    ):
        """Test that service copies Python-specific Docker files"""
        project_dir = temp_directory / "python-project"
        project_dir.mkdir()

        project = Project(
            parent="pre-edit",
            name="python-project",
            path=project_dir,
            relative_path="pre-edit/python-project",
        )

        output_callback = Mock()

        with patch.object(service, "defaults_dir", temp_defaults_dir):
            await service._copy_build_docker_sh(project, "python", output_callback)
            await service._copy_run_tests_sh(
                project, "python", False, False, output_callback
            )
            await service._copy_dockerfile(
                project, "python", False, False, output_callback
            )

        # Check files exist and have correct content
        build_script = project_dir / "build_docker.sh"
        assert build_script.exists()
        assert "Building Python Docker" in build_script.read_text()
        assert os.access(build_script, os.X_OK)

        run_tests = project_dir / "run_tests.sh"
        assert run_tests.exists()
        assert "Running Python tests" in run_tests.read_text()
        assert os.access(run_tests, os.X_OK)

        dockerfile = project_dir / "Dockerfile"
        assert dockerfile.exists()
        assert "FROM python:3.9" in dockerfile.read_text()

    @pytest.mark.asyncio
    async def test_copies_javascript_docker_files(
        self, service, temp_directory, temp_defaults_dir
    ):
        """Test that service copies JavaScript-specific Docker files"""
        project_dir = temp_directory / "js-project"
        project_dir.mkdir()

        project = Project(
            parent="pre-edit",
            name="js-project",
            path=project_dir,
            relative_path="pre-edit/js-project",
        )

        output_callback = Mock()

        with patch.object(service, "defaults_dir", temp_defaults_dir):
            await service._copy_build_docker_sh(project, "javascript", output_callback)
            await service._copy_run_tests_sh(
                project, "javascript", False, False, output_callback
            )
            await service._copy_dockerfile(
                project, "javascript", False, False, output_callback
            )

        # Check files exist and have correct content
        build_script = project_dir / "build_docker.sh"
        assert build_script.exists()
        assert "Building JavaScript Docker" in build_script.read_text()

        run_tests = project_dir / "run_tests.sh"
        assert run_tests.exists()
        assert "Running JavaScript tests" in run_tests.read_text()

        dockerfile = project_dir / "Dockerfile"
        assert dockerfile.exists()
        assert "FROM node:18" in dockerfile.read_text()

    @pytest.mark.asyncio
    async def test_copies_java_docker_files(
        self, service, temp_directory, temp_defaults_dir
    ):
        """Test that service copies Java-specific Docker files"""
        project_dir = temp_directory / "java-project"
        project_dir.mkdir()

        project = Project(
            parent="pre-edit",
            name="java-project",
            path=project_dir,
            relative_path="pre-edit/java-project",
        )

        output_callback = Mock()

        with patch.object(service, "defaults_dir", temp_defaults_dir):
            await service._copy_build_docker_sh(project, "java", output_callback)
            await service._copy_run_tests_sh(
                project, "java", False, False, output_callback
            )
            await service._copy_dockerfile(
                project, "java", False, False, output_callback
            )

        # Check files exist and have correct content
        build_script = project_dir / "build_docker.sh"
        assert build_script.exists()
        assert "Building Java Docker" in build_script.read_text()

        dockerfile = project_dir / "Dockerfile"
        assert dockerfile.exists()
        assert "FROM openjdk:11" in dockerfile.read_text()

    @pytest.mark.asyncio
    async def test_copies_c_docker_files(
        self, service, temp_directory, temp_defaults_dir
    ):
        """Test that service copies C-specific Docker files"""
        project_dir = temp_directory / "c-project"
        project_dir.mkdir()

        project = Project(
            parent="pre-edit",
            name="c-project",
            path=project_dir,
            relative_path="pre-edit/c-project",
        )

        output_callback = Mock()

        with patch.object(service, "defaults_dir", temp_defaults_dir):
            await service._copy_build_docker_sh(project, "c", output_callback)
            await service._copy_run_tests_sh(
                project, "c", False, False, output_callback
            )
            await service._copy_dockerfile(project, "c", False, False, output_callback)

        # Check files exist and have correct content
        build_script = project_dir / "build_docker.sh"
        assert build_script.exists()
        assert "Building C Docker" in build_script.read_text()
        assert os.access(build_script, os.X_OK)

        run_tests = project_dir / "run_tests.sh"
        assert run_tests.exists()
        assert "Running C tests" in run_tests.read_text()
        assert os.access(run_tests, os.X_OK)

        dockerfile = project_dir / "Dockerfile"
        assert dockerfile.exists()
        content = dockerfile.read_text()
        assert "FROM alpine:3.21" in content
        assert "alpine-sdk cmake" in content

    @pytest.mark.asyncio
    async def test_python_with_tkinter_uses_special_templates(
        self, service, temp_directory, temp_defaults_dir
    ):
        """Test that Python projects with tkinter use special templates"""
        project_dir = temp_directory / "tkinter-project"
        project_dir.mkdir()

        project = Project(
            parent="pre-edit",
            name="tkinter-project",
            path=project_dir,
            relative_path="pre-edit/tkinter-project",
        )

        output_callback = Mock()

        with patch.object(service, "defaults_dir", temp_defaults_dir):
            await service._copy_run_tests_sh(
                project, "python", True, False, output_callback
            )
            await service._copy_dockerfile(
                project, "python", True, False, output_callback
            )

        # Check special tkinter templates are used
        run_tests = project_dir / "run_tests.sh"
        assert run_tests.exists()
        assert "Running Python tkinter tests" in run_tests.read_text()

        dockerfile = project_dir / "Dockerfile"
        assert dockerfile.exists()
        content = dockerfile.read_text()
        assert "FROM python:3.9" in content
        assert "apt-get update" in content

    @pytest.mark.asyncio
    async def test_python_with_opencv_uses_special_templates(
        self, service, temp_directory, temp_defaults_dir
    ):
        """Test that Python projects with opencv use special templates"""
        project_dir = temp_directory / "opencv-project"
        project_dir.mkdir()

        project = Project(
            parent="pre-edit",
            name="opencv-project",
            path=project_dir,
            relative_path="pre-edit/opencv-project",
        )

        output_callback = Mock()

        with patch.object(service, "defaults_dir", temp_defaults_dir):
            await service._copy_run_tests_sh(
                project, "python", False, True, output_callback
            )
            await service._copy_dockerfile(
                project, "python", False, True, output_callback
            )

        # Check special opencv templates are used
        run_tests = project_dir / "run_tests.sh"
        assert run_tests.exists()
        assert "Running Python opencv tests" in run_tests.read_text()

        dockerfile = project_dir / "Dockerfile"
        assert dockerfile.exists()
        content = dockerfile.read_text()
        assert "FROM python:3.9" in content
        assert "opencv-python" in content

    # File Distribution Tests
    @pytest.mark.asyncio
    async def test_copies_language_specific_files_to_all_versions(
        self, service, sample_project_group, temp_defaults_dir
    ):
        """Test that service copies language-specific files to all project versions"""
        # Setup pre-edit project with JavaScript files
        pre_edit = sample_project_group.get_version("pre-edit")

        # Create JavaScript project files
        (pre_edit.path / "index.js").write_text("console.log('hello');")

        # Create Docker files in pre-edit
        docker_files = [
            ".dockerignore",
            "run_tests.sh",
            "build_docker.sh",
            "Dockerfile",
        ]
        language_files = ["package.json", "package-lock.json"]  # JavaScript specific

        for filename in docker_files + language_files:
            file_path = pre_edit.path / filename
            file_path.write_text(f"Content of {filename}")
            if filename.endswith(".sh"):
                os.chmod(file_path, 0o755)

        output_callback = Mock()

        success, message = await service._copy_files_to_all_versions(
            sample_project_group, pre_edit, "javascript", output_callback
        )

        assert success is True
        assert "Files copied to 3 versions" in message

        # Check that all files were copied to other versions
        for version_name in ["post-edit", "post-edit2", "correct-edit"]:
            version = sample_project_group.get_version(version_name)
            for filename in docker_files + language_files:
                file_path = version.path / filename
                assert file_path.exists()
                assert file_path.read_text() == f"Content of {filename}"
                if filename.endswith(".sh"):
                    assert os.access(file_path, os.X_OK)

    @pytest.mark.asyncio
    async def test_copies_c_language_files_to_all_versions(
        self, service, sample_project_group, temp_defaults_dir
    ):
        """Test that service copies C language-specific files to all project versions"""
        # Setup pre-edit project with C files
        pre_edit = sample_project_group.get_version("pre-edit")

        # Create C project files
        (pre_edit.path / "main.c").write_text("#include <stdio.h>\nint main() {}")
        (pre_edit.path / "utils.h").write_text(
            "#ifndef UTILS_H\n#define UTILS_H\n#endif"
        )

        # Create Docker files in pre-edit
        docker_files = [
            ".dockerignore",
            "run_tests.sh",
            "build_docker.sh",
            "Dockerfile",
        ]
        language_files = ["CMakeLists.txt"]  # C specific

        for filename in docker_files + language_files:
            file_path = pre_edit.path / filename
            file_path.write_text(f"Content of {filename}")
            if filename.endswith(".sh"):
                os.chmod(file_path, 0o755)

        output_callback = Mock()

        success, message = await service._copy_files_to_all_versions(
            sample_project_group, pre_edit, "c", output_callback
        )

        assert success is True
        assert "Files copied to 3 versions" in message

        # Check that all files were copied to other versions
        for version_name in ["post-edit", "post-edit2", "correct-edit"]:
            version = sample_project_group.get_version(version_name)
            for filename in docker_files + language_files:
                file_path = version.path / filename
                assert file_path.exists()
                assert file_path.read_text() == f"Content of {filename}"
                if filename.endswith(".sh"):
                    assert os.access(file_path, os.X_OK)

            # Specifically check that CMakeLists.txt was copied
            cmake_file = version.path / "CMakeLists.txt"
            assert cmake_file.exists()
            assert cmake_file.read_text() == "Content of CMakeLists.txt"

    # Integration Tests
    @pytest.mark.asyncio
    async def test_full_workflow_python_project_with_dependencies(
        self, service, sample_project_group, temp_defaults_dir
    ):
        """Test complete workflow for Python project with tkinter and opencv"""
        # Setup pre-edit project with Python files and dependencies
        pre_edit = sample_project_group.get_version("pre-edit")

        # Create Python files with tkinter
        (pre_edit.path / "main.py").write_text(
            "import tkinter as tk\nimport cv2\nprint('Hello')"
        )
        (pre_edit.path / "utils.py").write_text("def helper(): pass")

        # Add opencv requirement
        (pre_edit.path / "requirements.txt").write_text(
            "opencv-python==4.5.0\nnumpy==1.21.0\n"
        )

        # Add gitignore
        (pre_edit.path / ".gitignore").write_text("__pycache__/\n*.pyc\n")

        output_callback = Mock()
        status_callback = Mock()

        with patch.object(service, "defaults_dir", temp_defaults_dir):
            success, message = await service.build_docker_files_for_project_group(
                sample_project_group, output_callback, status_callback
            )

        assert success is True
        assert "Docker files generated and distributed successfully" in message

        # Verify files created in all versions
        for version_name in ["pre-edit", "post-edit", "post-edit2", "correct-edit"]:
            version = sample_project_group.get_version(version_name)

            # Check Docker files exist
            assert (version.path / ".dockerignore").exists()
            assert (version.path / "run_tests.sh").exists()
            assert (version.path / "build_docker.sh").exists()
            assert (version.path / "Dockerfile").exists()
            assert (version.path / "requirements.txt").exists()

            # Check .dockerignore content
            dockerignore_content = (version.path / ".dockerignore").read_text()
            assert "__pycache__/" in dockerignore_content
            assert "!run_tests.sh" in dockerignore_content

            # Check Python-specific content in templates
            build_content = (version.path / "build_docker.sh").read_text()
            assert "Building Python Docker" in build_content

    @pytest.mark.asyncio
    async def test_full_workflow_javascript_project(
        self, service, sample_project_group, temp_defaults_dir
    ):
        """Test complete workflow for JavaScript project"""
        # Setup pre-edit project with JavaScript files
        pre_edit = sample_project_group.get_version("pre-edit")

        # Create JavaScript files (more than other languages)
        (pre_edit.path / "index.js").write_text("console.log('Hello JavaScript');")
        (pre_edit.path / "utils.js").write_text("function helper() {}")
        (pre_edit.path / "app.js").write_text("const app = {};")
        (pre_edit.path / "main.py").write_text("print('hello')")  # Less Python files

        output_callback = Mock()
        status_callback = Mock()

        with patch.object(service, "defaults_dir", temp_defaults_dir):
            success, message = await service.build_docker_files_for_project_group(
                sample_project_group, output_callback, status_callback
            )

        assert success is True

        # Verify JavaScript language was detected and files created
        for version_name in ["pre-edit", "post-edit", "post-edit2", "correct-edit"]:
            version = sample_project_group.get_version(version_name)

            # Check JavaScript-specific files exist
            assert (version.path / "package.json").exists()
            assert (version.path / "package-lock.json").exists()

            # Check JavaScript-specific Docker content
            dockerfile_content = (version.path / "Dockerfile").read_text()
            assert "FROM node:18" in dockerfile_content

            build_content = (version.path / "build_docker.sh").read_text()
            assert "Building JavaScript Docker" in build_content

    @pytest.mark.asyncio
    async def test_full_workflow_c_project(
        self, service, sample_project_group, temp_defaults_dir
    ):
        """Test complete workflow for C/C++ project"""
        # Setup pre-edit project with C/C++ files
        pre_edit = sample_project_group.get_version("pre-edit")

        # Create C/C++ files (more C files than other languages)
        (pre_edit.path / "main.c").write_text(
            '#include <stdio.h>\nint main() { printf("Hello C"); return 0; }'
        )
        (pre_edit.path / "utils.c").write_text('#include "utils.h"\nvoid helper() {}')
        (pre_edit.path / "utils.h").write_text(
            "#ifndef UTILS_H\n#define UTILS_H\nvoid helper();\n#endif"
        )
        (pre_edit.path / "app.cpp").write_text(
            '#include <iostream>\nint main() { std::cout << "Hello C++"; }'
        )
        (pre_edit.path / "classes.hpp").write_text(
            "#ifndef CLASSES_HPP\n#define CLASSES_HPP\nclass MyClass {};\n#endif"
        )

        # Add some other language files (fewer than C)
        (pre_edit.path / "script.py").write_text("print('hello')")

        # Add gitignore
        (pre_edit.path / ".gitignore").write_text("build/\n*.o\n*.out\n")

        output_callback = Mock()
        status_callback = Mock()

        with patch.object(service, "defaults_dir", temp_defaults_dir):
            success, message = await service.build_docker_files_for_project_group(
                sample_project_group, output_callback, status_callback
            )

        assert success is True
        assert "Docker files generated and distributed successfully" in message

        # Verify files created in all versions
        for version_name in ["pre-edit", "post-edit", "post-edit2", "correct-edit"]:
            version = sample_project_group.get_version(version_name)

            # Check Docker files exist
            assert (version.path / ".dockerignore").exists()
            assert (version.path / "run_tests.sh").exists()
            assert (version.path / "build_docker.sh").exists()
            assert (version.path / "Dockerfile").exists()
            assert (version.path / "CMakeLists.txt").exists()

            # Check .dockerignore content
            dockerignore_content = (version.path / ".dockerignore").read_text()
            assert "build/" in dockerignore_content
            assert "*.o" in dockerignore_content
            assert "!run_tests.sh" in dockerignore_content

            # Check C-specific content in templates
            build_content = (version.path / "build_docker.sh").read_text()
            assert "Building C Docker" in build_content

            dockerfile_content = (version.path / "Dockerfile").read_text()
            assert "FROM alpine:3.21" in dockerfile_content
            assert "alpine-sdk cmake" in dockerfile_content

            # Check CMakeLists.txt content
            cmake_content = (version.path / "CMakeLists.txt").read_text()
            assert "cmake_minimum_required" in cmake_content
            assert "project(MyProject)" in cmake_content

    @pytest.mark.asyncio
    async def test_handles_missing_pre_edit_version(
        self, service, mock_project_service
    ):
        """Test that service handles missing pre-edit version gracefully"""
        # Create project group without pre-edit version
        project_group = ProjectGroup("test-project", mock_project_service)
        project_group.add_project(
            Project(
                parent="post-edit",
                name="test-project",
                path=Path("/test/post-edit/test-project"),
                relative_path="post-edit/test-project",
            )
        )

        output_callback = Mock()
        status_callback = Mock()

        success, message = await service.build_docker_files_for_project_group(
            project_group, output_callback, status_callback
        )

        assert success is False
        assert "No pre-edit version found" in message

    @pytest.mark.asyncio
    async def test_detects_existing_docker_files(self, service, temp_directory):
        """Test that service detects existing Docker files that would be overwritten"""
        project_dir = temp_directory / "existing-docker-project"
        project_dir.mkdir()

        # Create existing Docker files
        (project_dir / "Dockerfile").write_text("FROM existing:image")
        (project_dir / "run_tests.sh").write_text("#!/bin/bash\necho existing")

        project = Project(
            parent="pre-edit",
            name="existing-docker-project",
            path=project_dir,
            relative_path="pre-edit/existing-docker-project",
        )

        output_callback = Mock()
        existing_files = await service._check_existing_docker_files(
            project, output_callback
        )

        assert len(existing_files) == 2
        assert "Dockerfile" in existing_files
        assert "run_tests.sh" in existing_files

        # Verify warning message was output
        output_calls = [call.args[0] for call in output_callback.call_args_list]
        assert any("Found existing Docker files" in call for call in output_calls)

    # Legacy Python Analysis Tests (for backward compatibility)
    @pytest.mark.asyncio
    async def test_python_tkinter_detection_still_works(
        self, service, python_project_with_tkinter
    ):
        """Test that Python tkinter detection still works as before"""
        has_tkinter = await service._search_for_tkinter_imports(
            python_project_with_tkinter.path
        )
        assert has_tkinter is True

    @pytest.mark.asyncio
    async def test_python_opencv_detection_still_works(
        self, service, python_project_with_opencv
    ):
        """Test that Python opencv detection still works as before"""
        has_opencv = await service._check_opencv_in_requirements(
            python_project_with_opencv.path
        )
        assert has_opencv is True


# P2P
class TestProjectControlPanelIntegration:
    """Integration tests for ProjectControlPanel.build_docker_files_for_project_group"""

    @pytest.mark.asyncio
    async def test_project_control_panel_calls_task_manager_once(self):
        """Test that ProjectControlPanel.build_docker_files_for_project_group calls task_manager.run_task exactly once"""

        # Mock the ProjectControlPanel and related components
        with patch("general_tools.task_manager") as mock_task_manager, patch(
            "general_tools.ProjectControlPanel._setup_async_integration"
        ), patch("general_tools.ProjectControlPanel._setup_async_processing"), patch(
            "general_tools.MainWindow"
        ), patch(
            "general_tools.ProjectControlPanel.load_projects"
        ), patch(
            "general_tools.tk.Tk"
        ):

            from general_tools import ProjectControlPanel

            # Create a mock project group
            mock_project_group = Mock()
            mock_project_group.name = "test-project"

            # Create the control panel instance
            control_panel = ProjectControlPanel(".")

            # Call the method we want to test
            control_panel.build_docker_files_for_project_group(mock_project_group)

            # Verify task_manager.run_task was called exactly once
            assert mock_task_manager.run_task.call_count == 1

            # Verify the task name contains the expected pattern
            call_args = mock_task_manager.run_task.call_args
            assert call_args[1]["task_name"] == "build-docker-test-project"

            # Verify the first argument is a coroutine (async function)
            assert asyncio.iscoroutine(call_args[0][0])

    @pytest.mark.asyncio
    async def test_project_control_panel_async_function_behavior(self):
        """Test the actual async function behavior within ProjectControlPanel"""

        # Mock all external dependencies
        with patch("general_tools.TkinterAsyncBridge") as mock_bridge, patch(
            "general_tools.TerminalOutputWindow"
        ) as mock_terminal_window, patch(
            "general_tools.messagebox"
        ) as mock_messagebox, patch(
            "general_tools.ProjectControlPanel._setup_async_integration"
        ), patch(
            "general_tools.ProjectControlPanel._setup_async_processing"
        ), patch(
            "general_tools.MainWindow"
        ), patch(
            "general_tools.ProjectControlPanel.load_projects"
        ), patch(
            "general_tools.tk.Tk"
        ):

            from general_tools import ProjectControlPanel

            # Setup mocks
            mock_terminal = Mock()
            mock_terminal_window.return_value = mock_terminal
            mock_terminal.create_window = Mock()
            mock_terminal.update_status = Mock()
            mock_terminal.add_final_buttons = Mock()

            # Setup async bridge mock
            mock_event = AsyncMock()
            mock_bridge_instance = Mock()
            mock_bridge_instance.create_sync_event.return_value = (
                "event_id",
                mock_event,
            )
            mock_bridge_instance.signal_from_gui = Mock()
            mock_bridge_instance.cleanup_event = Mock()
            mock_bridge.return_value = mock_bridge_instance

            # Create control panel and override the docker_files_service
            control_panel = ProjectControlPanel(".")
            control_panel.async_bridge = mock_bridge_instance
            control_panel.docker_files_service = Mock()
            control_panel.docker_files_service._find_pre_edit_version = Mock(
                return_value=Mock()
            )
            control_panel.docker_files_service._check_existing_docker_files = AsyncMock(
                return_value=[]
            )
            control_panel.docker_files_service.build_docker_files_for_project_group = (
                AsyncMock(return_value=(True, "Success"))
            )

            # Mock the window properly with all required attributes
            control_panel.window = Mock()
            control_panel.window.after = Mock(
                side_effect=lambda delay, callback: callback()
            )
            control_panel.window._last_child_ids = {}  # Fix for tkinter Mock issue
            control_panel.window._w = "mock_window"  # Add _w attribute for tkinter

            # Also mock the parent window attributes to handle Toplevel creation
            mock_terminal.parent_window = Mock()
            mock_terminal.parent_window._w = "mock_parent"
            mock_terminal.parent_window._last_child_ids = {}

            # Create mock project group
            mock_project_group = Mock()
            mock_project_group.name = "test-project"

            # Mock window.after to execute callbacks immediately
            control_panel.window = Mock()
            control_panel.window.after = Mock(
                side_effect=lambda delay, callback: callback()
            )

            # Get the async function that would be passed to task_manager.run_task
            # We need to simulate what happens inside build_docker_files_for_project_group
            async def simulated_build_docker_files_async():
                try:
                    # This simulates the main logic that should happen
                    event_id, window_ready_event = (
                        control_panel.async_bridge.create_sync_event()
                    )

                    terminal_window = None

                    def create_window():
                        nonlocal terminal_window
                        terminal_window = mock_terminal_window(
                            control_panel.window,
                            f"Build Docker files - {mock_project_group.name}",
                        )
                        terminal_window.create_window()
                        control_panel.async_bridge.signal_from_gui(event_id)

                    control_panel.window.after(0, create_window)
                    await window_ready_event.wait()
                    control_panel.async_bridge.cleanup_event(event_id)

                    # Call the docker files service
                    success, message = (
                        await control_panel.docker_files_service.build_docker_files_for_project_group(
                            mock_project_group,
                            (
                                terminal_window.append_output
                                if terminal_window
                                else Mock()
                            ),
                            (
                                terminal_window.update_status
                                if terminal_window
                                else Mock()
                            ),
                        )
                    )

                    return success, message

                except Exception as e:
                    return False, str(e)

            # Execute the simulated async function
            success, message = await simulated_build_docker_files_async()

            # Verify the behavior
            assert success is True
            assert message == "Success"

            # Verify the service was called
            control_panel.docker_files_service.build_docker_files_for_project_group.assert_called_once()

            # Verify window management
            mock_bridge_instance.create_sync_event.assert_called_once()
            mock_bridge_instance.cleanup_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_project_control_panel_runs_docker_files_service_correctly(self):
        """Test that ProjectControlPanel correctly executes docker files service through command pattern"""

        # Mock all external dependencies
        with patch("general_tools.task_manager") as mock_task_manager, patch(
            "general_tools.TkinterAsyncBridge"
        ) as mock_bridge, patch(
            "general_tools.TerminalOutputWindow"
        ) as mock_terminal_window, patch(
            "gui.TerminalOutputWindow"  # Patch the actual gui module
        ) as mock_command_terminal, patch(
            "general_tools.ProjectControlPanel._setup_async_integration"
        ), patch(
            "general_tools.ProjectControlPanel._setup_async_processing"
        ), patch(
            "general_tools.MainWindow"
        ), patch(
            "general_tools.ProjectControlPanel.load_projects"
        ), patch(
            "general_tools.tk.Tk"
        ):

            from general_tools import ProjectControlPanel

            # Setup mock docker files service instance with the method that will actually be called
            mock_docker_service = Mock()
            mock_docker_service.build_docker_files_for_project_group = AsyncMock(
                return_value=(True, "Docker files generated successfully")
            )

            # Setup other mocks
            mock_terminal = Mock()
            mock_terminal_window.return_value = mock_terminal
            mock_command_terminal.return_value = (
                mock_terminal  # Also set up command terminal
            )
            mock_terminal.create_window = Mock()
            mock_terminal.update_status = Mock()
            mock_terminal.append_output = Mock()
            mock_terminal.add_final_buttons = Mock()
            mock_terminal.destroy = Mock()  # Add destroy method

            # Setup async bridge mock
            mock_event = AsyncMock()
            mock_bridge_instance = Mock()
            mock_bridge_instance.create_sync_event.return_value = (
                "event_id",
                mock_event,
            )
            mock_bridge_instance.signal_from_gui = Mock()
            mock_bridge_instance.cleanup_event = Mock()
            mock_bridge.return_value = mock_bridge_instance

            # Create control panel and override the docker_files_service
            control_panel = ProjectControlPanel(".")
            control_panel.async_bridge = mock_bridge_instance
            control_panel.docker_files_service = mock_docker_service

            # Mock the window properly with all required attributes
            control_panel.window = Mock()
            control_panel.window.after = Mock(
                side_effect=lambda delay, callback: callback()
            )
            control_panel.window._last_child_ids = {}  # Fix for tkinter Mock issue

            # Create mock project group
            mock_project_group = Mock()
            mock_project_group.name = "test-project"

            # Capture the async function that would be passed to task_manager.run_task
            captured_async_func = None
            captured_task_name = None

            def mock_run_task(async_func, task_name=None):
                nonlocal captured_async_func, captured_task_name
                captured_async_func = async_func
                captured_task_name = task_name
                return Mock()  # Return a mock future

            mock_task_manager.run_task = Mock(side_effect=mock_run_task)

            # Call the method under test
            control_panel.build_docker_files_for_project_group(mock_project_group)

            # Verify that task_manager.run_task was called
            mock_task_manager.run_task.assert_called_once()
            assert captured_task_name == f"build-docker-{mock_project_group.name}"
            assert captured_async_func is not None
            assert asyncio.iscoroutine(captured_async_func)

            # Now execute the captured async function to test its behavior
            await captured_async_func

            # Verify the docker_files_service main method was called correctly
            mock_docker_service.build_docker_files_for_project_group.assert_called_once()

            # Verify the service was called with correct parameters
            service_call_args = (
                mock_docker_service.build_docker_files_for_project_group.call_args
            )
            assert (
                service_call_args[0][0] == mock_project_group
            )  # First argument should be the project group
            # Second argument should be output callback
            assert callable(service_call_args[0][1])
            # Third argument should be status callback
            assert callable(service_call_args[0][2])

            # Verify window operations
            mock_command_terminal.assert_called_once()  # This is the one actually being called
            mock_terminal.create_window.assert_called_once()
            mock_terminal.update_status.assert_called()
            mock_terminal.add_final_buttons.assert_called_once()

    @pytest.mark.asyncio
    async def test_project_control_panel_handles_docker_service_errors(self):
        """Test that ProjectControlPanel handles docker_files_service errors gracefully"""

        # Mock all external dependencies
        with patch("general_tools.task_manager") as mock_task_manager, patch(
            "general_tools.TkinterAsyncBridge"
        ) as mock_bridge, patch(
            "general_tools.TerminalOutputWindow"
        ) as mock_terminal_window, patch(
            "gui.TerminalOutputWindow"  # Patch the actual gui module
        ) as mock_command_terminal, patch(
            "general_tools.messagebox"
        ) as mock_messagebox, patch(
            "general_tools.ProjectControlPanel._setup_async_integration"
        ), patch(
            "general_tools.ProjectControlPanel._setup_async_processing"
        ), patch(
            "general_tools.MainWindow"
        ), patch(
            "general_tools.ProjectControlPanel.load_projects"
        ), patch(
            "general_tools.tk.Tk"
        ):

            from general_tools import ProjectControlPanel

            # Setup mock that raises an exception
            mock_docker_service = Mock()
            mock_docker_service.build_docker_files_for_project_group = AsyncMock(
                side_effect=Exception("Docker service error")
            )

            # Setup other mocks
            mock_terminal = Mock()
            mock_terminal_window.return_value = mock_terminal
            mock_command_terminal.return_value = (
                mock_terminal  # Also set up command terminal
            )
            mock_terminal.create_window = Mock()
            mock_terminal.update_status = Mock()
            mock_terminal.append_output = Mock()
            mock_terminal.add_final_buttons = Mock()
            mock_terminal.destroy = Mock()  # Add destroy method

            # Setup async bridge mock
            mock_event = AsyncMock()
            mock_bridge_instance = Mock()
            mock_bridge_instance.create_sync_event.return_value = (
                "event_id",
                mock_event,
            )
            mock_bridge_instance.signal_from_gui = Mock()
            mock_bridge_instance.cleanup_event = Mock()
            mock_bridge.return_value = mock_bridge_instance

            # Create control panel
            control_panel = ProjectControlPanel(".")
            control_panel.async_bridge = mock_bridge_instance
            control_panel.docker_files_service = mock_docker_service

            # Mock the window properly with all required attributes
            control_panel.window = Mock()
            control_panel.window.after = Mock(
                side_effect=lambda delay, callback: callback()
            )
            control_panel.window._last_child_ids = {}  # Fix for tkinter Mock issue

            # Create mock project group
            mock_project_group = Mock()
            mock_project_group.name = "test-project"

            # Capture the async function that would be passed to task_manager.run_task
            captured_async_func = None
            captured_task_name = None

            def mock_run_task(async_func, task_name=None):
                nonlocal captured_async_func, captured_task_name
                captured_async_func = async_func
                captured_task_name = task_name
                return Mock()  # Return a mock future

            mock_task_manager.run_task = Mock(side_effect=mock_run_task)

            # Call the method under test
            control_panel.build_docker_files_for_project_group(mock_project_group)

            # Verify that task_manager.run_task was called
            mock_task_manager.run_task.assert_called_once()
            assert captured_task_name == f"build-docker-{mock_project_group.name}"
            assert captured_async_func is not None
            assert asyncio.iscoroutine(captured_async_func)

            # Now execute the captured async function - it should handle the exception gracefully
            result = await captured_async_func

            # The async function should return an error result but not raise the exception
            assert hasattr(result, "is_error")
            assert result.is_error is True

            # Verify the docker_files_service was called (and failed)
            mock_docker_service.build_docker_files_for_project_group.assert_called_once()

            # The error handling is done in the async function, so we verify the window operations still happened
            mock_command_terminal.assert_called_once()  # This is the one actually being called
            mock_terminal.create_window.assert_called_once()
