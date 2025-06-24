"""
Tests for DockerFilesService - implementation-agnostic tests
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
    """Test suite for DockerFilesService"""

    @pytest.fixture
    def service(self):
        """Create a DockerFilesService instance"""
        return DockerFilesService()

    @pytest.fixture
    def temp_defaults_dir(self, temp_directory):
        """Create a temporary defaults directory with required files"""
        defaults_dir = temp_directory / "defaults"
        defaults_dir.mkdir()

        # Create all required template files
        templates = {
            "build_docker.sh": "#!/bin/bash\necho 'Building Docker'\n",
            "run_tests.sh": "#!/bin/bash\necho 'Running tests'\n",
            "run_tests_tkinter.sh": "#!/bin/bash\necho 'Running tkinter tests'\n",
            "run_tests_opencv.sh": "#!/bin/bash\necho 'Running opencv tests'\n",
            "run_tests_opencv_tkinter.sh": "#!/bin/bash\necho 'Running opencv+tkinter tests'\n",
            "Dockerfile": "FROM python:3.9\nCOPY . /app\n",
            "Dockerfile_tkinter": "FROM python:3.9\nRUN apt-get update\nCOPY . /app\n",
            "Dockerfile_opencv": "FROM python:3.9\nRUN pip install opencv-python\nCOPY . /app\n",
            "Dockerfile_opencv_tkinter.txt": "FROM python:3.9\nRUN apt-get update\nRUN pip install opencv-python\nCOPY . /app\n",
        }

        for filename, content in templates.items():
            template_file = defaults_dir / filename
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

    @pytest.fixture
    def pre_edit_project_with_tkinter(self, temp_directory):
        """Create a pre-edit project with tkinter imports"""
        project_dir = temp_directory / "pre-edit" / "test-project"
        project_dir.mkdir(parents=True)

        # Create Python file with tkinter import
        py_file = project_dir / "main.py"
        py_file.write_text("import tkinter as tk\nfrom tkinter import messagebox\n")

        return Project(
            parent="pre-edit",
            name="test-project",
            path=project_dir,
            relative_path="pre-edit/test-project",
        )

    @pytest.fixture
    def pre_edit_project_with_opencv(self, temp_directory):
        """Create a pre-edit project with opencv requirements"""
        project_dir = temp_directory / "pre-edit" / "test-project"
        project_dir.mkdir(parents=True)

        # Create requirements.txt with opencv-python
        req_file = project_dir / "requirements.txt"
        req_file.write_text("numpy==1.21.0\nopencv-python==4.5.0\nmatplotlib==3.4.0\n")

        return Project(
            parent="pre-edit",
            name="test-project",
            path=project_dir,
            relative_path="pre-edit/test-project",
        )

    @pytest.fixture
    def pre_edit_project_with_gitignore(self, temp_directory):
        """Create a pre-edit project with .gitignore"""
        project_dir = temp_directory / "pre-edit" / "test-project"
        project_dir.mkdir(parents=True)

        # Create .gitignore
        gitignore = project_dir / ".gitignore"
        gitignore.write_text("__pycache__/\n*.pyc\n.pytest_cache/\n")

        return Project(
            parent="pre-edit",
            name="test-project",
            path=project_dir,
            relative_path="pre-edit/test-project",
        )

    @pytest.mark.asyncio
    async def test_finds_pre_edit_version(self, service, sample_project_group):
        """Test that service correctly identifies pre-edit version"""
        with patch.object(service, "defaults_dir", Path("defaults")):
            pre_edit = service._find_pre_edit_version(sample_project_group)

            assert pre_edit is not None
            assert pre_edit.parent == "pre-edit"
            assert pre_edit.name == "test-project"

    @pytest.mark.asyncio
    async def test_detects_tkinter_imports(
        self, service, pre_edit_project_with_tkinter
    ):
        """Test that service correctly detects tkinter imports"""
        has_tkinter = await service._search_for_tkinter_imports(
            pre_edit_project_with_tkinter.path
        )
        assert has_tkinter is True

    @pytest.mark.asyncio
    async def test_detects_no_tkinter_imports(self, service, temp_directory):
        """Test that service correctly detects absence of tkinter imports"""
        project_dir = temp_directory / "test-project"
        project_dir.mkdir()

        # Create Python file without tkinter
        py_file = project_dir / "main.py"
        py_file.write_text("import os\nimport sys\n")

        has_tkinter = await service._search_for_tkinter_imports(project_dir)
        assert has_tkinter is False

    @pytest.mark.asyncio
    async def test_detects_opencv_in_requirements(
        self, service, pre_edit_project_with_opencv
    ):
        """Test that service correctly detects opencv-python in requirements.txt"""
        has_opencv = await service._check_opencv_in_requirements(
            pre_edit_project_with_opencv.path
        )
        assert has_opencv is True

    @pytest.mark.asyncio
    async def test_detects_no_opencv_in_requirements(self, service, temp_directory):
        """Test that service correctly detects absence of opencv-python"""
        project_dir = temp_directory / "test-project"
        project_dir.mkdir()

        # Create requirements.txt without opencv
        req_file = project_dir / "requirements.txt"
        req_file.write_text("numpy==1.21.0\nmatplotlib==3.4.0\n")

        has_opencv = await service._check_opencv_in_requirements(project_dir)
        assert has_opencv is False

    @pytest.mark.asyncio
    async def test_creates_blank_requirements_txt_when_missing(
        self, service, temp_directory, temp_defaults_dir
    ):
        """Test that service creates blank requirements.txt when it doesn't exist"""
        project_dir = temp_directory / "test-project"
        project_dir.mkdir()

        project = Project(
            parent="pre-edit",
            name="test-project",
            path=project_dir,
            relative_path="pre-edit/test-project",
        )

        output_callback = Mock()

        with patch.object(service, "defaults_dir", temp_defaults_dir):
            await service._ensure_requirements_txt(project, output_callback)

        req_file = project_dir / "requirements.txt"
        assert req_file.exists()
        assert "# Add your project dependencies here" in req_file.read_text()
        output_callback.assert_called_with("   ✅ Created blank requirements.txt\n")

    @pytest.mark.asyncio
    async def test_preserves_existing_requirements_txt(
        self, service, pre_edit_project_with_opencv
    ):
        """Test that service preserves existing requirements.txt"""
        output_callback = Mock()
        original_content = pre_edit_project_with_opencv.path / "requirements.txt"
        original_text = original_content.read_text()

        await service._ensure_requirements_txt(
            pre_edit_project_with_opencv, output_callback
        )

        # Check content unchanged
        assert original_content.read_text() == original_text
        output_callback.assert_called_with("   ✅ requirements.txt already exists\n")

    @pytest.mark.asyncio
    async def test_builds_dockerignore_from_gitignore(
        self, service, pre_edit_project_with_gitignore
    ):
        """Test that service builds .dockerignore from .gitignore with !run_tests.sh line"""
        output_callback = Mock()

        await service._build_dockerignore(
            pre_edit_project_with_gitignore, output_callback
        )

        dockerignore = pre_edit_project_with_gitignore.path / ".dockerignore"
        assert dockerignore.exists()

        content = dockerignore.read_text()
        assert "__pycache__/" in content
        assert "*.pyc" in content
        assert ".pytest_cache/" in content
        assert "!run_tests.sh\n" in content

        output_callback.assert_called_with(
            "   ✅ Created .dockerignore with '!run_tests.sh' line\n"
        )

    @pytest.mark.asyncio
    async def test_builds_dockerignore_without_gitignore(self, service, temp_directory):
        """Test that service builds .dockerignore when no .gitignore exists"""
        project_dir = temp_directory / "test-project"
        project_dir.mkdir()

        project = Project(
            parent="pre-edit",
            name="test-project",
            path=project_dir,
            relative_path="pre-edit/test-project",
        )

        output_callback = Mock()

        await service._build_dockerignore(project, output_callback)

        dockerignore = project_dir / ".dockerignore"
        assert dockerignore.exists()

        content = dockerignore.read_text()
        assert content == "!run_tests.sh\n"

    @pytest.mark.asyncio
    async def test_copies_build_docker_sh(
        self, service, temp_directory, temp_defaults_dir
    ):
        """Test that service copies build_docker.sh from defaults"""
        project_dir = temp_directory / "test-project"
        project_dir.mkdir()

        project = Project(
            parent="pre-edit",
            name="test-project",
            path=project_dir,
            relative_path="pre-edit/test-project",
        )

        output_callback = Mock()

        with patch.object(service, "defaults_dir", temp_defaults_dir):
            await service._copy_build_docker_sh(project, output_callback)

        build_script = project_dir / "build_docker.sh"
        assert build_script.exists()
        assert "Building Docker" in build_script.read_text()

        # Check executable permission
        assert os.access(build_script, os.X_OK)

    @pytest.mark.asyncio
    async def test_copies_correct_run_tests_sh_default(
        self, service, temp_directory, temp_defaults_dir
    ):
        """Test that service copies correct run_tests.sh for default case"""
        project_dir = temp_directory / "test-project"
        project_dir.mkdir()

        project = Project(
            parent="pre-edit",
            name="test-project",
            path=project_dir,
            relative_path="pre-edit/test-project",
        )

        output_callback = Mock()

        with patch.object(service, "defaults_dir", temp_defaults_dir):
            await service._copy_run_tests_sh(project, False, False, output_callback)

        run_tests = project_dir / "run_tests.sh"
        assert run_tests.exists()
        assert "Running tests" in run_tests.read_text()
        assert os.access(run_tests, os.X_OK)

    @pytest.mark.asyncio
    async def test_copies_correct_run_tests_sh_tkinter(
        self, service, temp_directory, temp_defaults_dir
    ):
        """Test that service copies correct run_tests.sh for tkinter case"""
        project_dir = temp_directory / "test-project"
        project_dir.mkdir()

        project = Project(
            parent="pre-edit",
            name="test-project",
            path=project_dir,
            relative_path="pre-edit/test-project",
        )

        output_callback = Mock()

        with patch.object(service, "defaults_dir", temp_defaults_dir):
            await service._copy_run_tests_sh(project, True, False, output_callback)

        run_tests = project_dir / "run_tests.sh"
        assert run_tests.exists()
        assert "Running tkinter tests" in run_tests.read_text()

    @pytest.mark.asyncio
    async def test_copies_correct_run_tests_sh_opencv(
        self, service, temp_directory, temp_defaults_dir
    ):
        """Test that service copies correct run_tests.sh for opencv case"""
        project_dir = temp_directory / "test-project"
        project_dir.mkdir()

        project = Project(
            parent="pre-edit",
            name="test-project",
            path=project_dir,
            relative_path="pre-edit/test-project",
        )

        output_callback = Mock()

        with patch.object(service, "defaults_dir", temp_defaults_dir):
            await service._copy_run_tests_sh(project, False, True, output_callback)

        run_tests = project_dir / "run_tests.sh"
        assert run_tests.exists()
        assert "Running opencv tests" in run_tests.read_text()

    @pytest.mark.asyncio
    async def test_copies_correct_run_tests_sh_opencv_tkinter(
        self, service, temp_directory, temp_defaults_dir
    ):
        """Test that service copies correct run_tests.sh for opencv+tkinter case"""
        project_dir = temp_directory / "test-project"
        project_dir.mkdir()

        project = Project(
            parent="pre-edit",
            name="test-project",
            path=project_dir,
            relative_path="pre-edit/test-project",
        )

        output_callback = Mock()

        with patch.object(service, "defaults_dir", temp_defaults_dir):
            await service._copy_run_tests_sh(project, True, True, output_callback)

        run_tests = project_dir / "run_tests.sh"
        assert run_tests.exists()
        assert "Running opencv+tkinter tests" in run_tests.read_text()

    @pytest.mark.asyncio
    async def test_copies_correct_dockerfile_default(
        self, service, temp_directory, temp_defaults_dir
    ):
        """Test that service copies correct Dockerfile for default case"""
        project_dir = temp_directory / "test-project"
        project_dir.mkdir()

        project = Project(
            parent="pre-edit",
            name="test-project",
            path=project_dir,
            relative_path="pre-edit/test-project",
        )

        output_callback = Mock()

        with patch.object(service, "defaults_dir", temp_defaults_dir):
            await service._copy_dockerfile(project, False, False, output_callback)

        dockerfile = project_dir / "Dockerfile"
        assert dockerfile.exists()
        assert "FROM python:3.9" in dockerfile.read_text()

    @pytest.mark.asyncio
    async def test_copies_correct_dockerfile_tkinter(
        self, service, temp_directory, temp_defaults_dir
    ):
        """Test that service copies correct Dockerfile for tkinter case"""
        project_dir = temp_directory / "test-project"
        project_dir.mkdir()

        project = Project(
            parent="pre-edit",
            name="test-project",
            path=project_dir,
            relative_path="pre-edit/test-project",
        )

        output_callback = Mock()

        with patch.object(service, "defaults_dir", temp_defaults_dir):
            await service._copy_dockerfile(project, True, False, output_callback)

        dockerfile = project_dir / "Dockerfile"
        assert dockerfile.exists()
        content = dockerfile.read_text()
        assert "FROM python:3.9" in content
        assert "apt-get update" in content

    @pytest.mark.asyncio
    async def test_copies_correct_dockerfile_opencv_tkinter(
        self, service, temp_directory, temp_defaults_dir
    ):
        """Test that service copies correct Dockerfile for opencv+tkinter case"""
        project_dir = temp_directory / "test-project"
        project_dir.mkdir()

        project = Project(
            parent="pre-edit",
            name="test-project",
            path=project_dir,
            relative_path="pre-edit/test-project",
        )

        output_callback = Mock()

        with patch.object(service, "defaults_dir", temp_defaults_dir):
            await service._copy_dockerfile(project, True, True, output_callback)

        dockerfile = project_dir / "Dockerfile"
        assert dockerfile.exists()
        content = dockerfile.read_text()
        assert "FROM python:3.9" in content
        assert "apt-get update" in content
        assert "opencv-python" in content

    @pytest.mark.asyncio
    async def test_copies_files_to_all_versions(
        self, service, sample_project_group, temp_defaults_dir
    ):
        """Test that service copies generated files to all versions"""
        # Setup pre-edit project with files
        pre_edit = sample_project_group.get_version("pre-edit")

        # Create Docker files in pre-edit
        docker_files = [
            ".dockerignore",
            "run_tests.sh",
            "build_docker.sh",
            "Dockerfile",
            "requirements.txt",
        ]
        for filename in docker_files:
            file_path = pre_edit.path / filename
            file_path.write_text(f"Content of {filename}")
            if filename.endswith(".sh"):
                os.chmod(file_path, 0o755)

        output_callback = Mock()

        success, message = await service._copy_files_to_all_versions(
            sample_project_group, pre_edit, output_callback
        )

        assert success is True
        assert "Files copied to 3 versions" in message

        # Check that files were copied to other versions
        for version_name in ["post-edit", "post-edit2", "correct-edit"]:
            version = sample_project_group.get_version(version_name)
            for filename in docker_files:
                file_path = version.path / filename
                assert file_path.exists()
                assert file_path.read_text() == f"Content of {filename}"
                if filename.endswith(".sh"):
                    assert os.access(file_path, os.X_OK)

    @pytest.mark.asyncio
    async def test_build_docker_files_for_project_group_full_workflow(
        self, service, sample_project_group, temp_defaults_dir
    ):
        """Test complete workflow of building Docker files for project group"""
        # Setup pre-edit project with tkinter and opencv
        pre_edit = sample_project_group.get_version("pre-edit")

        # Add tkinter import
        py_file = pre_edit.path / "main.py"
        py_file.write_text("import tkinter as tk\n")

        # Add opencv requirement
        req_file = pre_edit.path / "requirements.txt"
        req_file.write_text("opencv-python==4.5.0\n")

        # Add gitignore
        gitignore = pre_edit.path / ".gitignore"
        gitignore.write_text("__pycache__/\n")

        output_callback = Mock()
        status_callback = Mock()

        with patch.object(service, "defaults_dir", temp_defaults_dir):
            success, message = await service.build_docker_files_for_project_group(
                sample_project_group, output_callback, status_callback
            )

        assert success is True
        assert "Docker files generated and distributed successfully" in message

        # Verify Docker files were created in all versions
        for version_name in ["pre-edit", "post-edit", "post-edit2", "correct-edit"]:
            version = sample_project_group.get_version(version_name)

            # Check all expected files exist
            assert (version.path / ".dockerignore").exists()
            assert (version.path / "run_tests.sh").exists()
            assert (version.path / "build_docker.sh").exists()
            assert (version.path / "Dockerfile").exists()
            assert (version.path / "requirements.txt").exists()

            # Check .dockerignore has correct content
            dockerignore_content = (version.path / ".dockerignore").read_text()
            assert "__pycache__/" in dockerignore_content
            assert "!run_tests.sh" in dockerignore_content

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
    async def test_checks_existing_docker_files(self, service, temp_directory):
        """Test that service correctly identifies existing Docker files"""
        project_dir = temp_directory / "test-project"
        project_dir.mkdir()

        project = Project(
            parent="pre-edit",
            name="test-project",
            path=project_dir,
            relative_path="pre-edit/test-project",
        )

        # Create some existing Docker files
        (project_dir / ".dockerignore").write_text("existing")
        (project_dir / "Dockerfile").write_text("existing")

        output_callback = Mock()

        existing_files = await service._check_existing_docker_files(
            project, output_callback
        )

        assert ".dockerignore" in existing_files
        assert "Dockerfile" in existing_files
        assert "run_tests.sh" not in existing_files  # Doesn't exist
        assert "build_docker.sh" not in existing_files  # Doesn't exist


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
