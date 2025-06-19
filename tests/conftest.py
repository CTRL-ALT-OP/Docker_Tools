"""
Pytest configuration and fixtures for Docker Tools tests
"""

import os
import sys
import asyncio
import tempfile
import shutil
from pathlib import Path
import pytest
from unittest.mock import Mock

# Add parent directory to path to import modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


# Configure asyncio for tests
@pytest.fixture(scope="session")
def event_loop_policy():
    """Set event loop policy for tests"""
    from services.platform_service import PlatformService

    if PlatformService.is_windows():
        # Windows requires special handling
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    return asyncio.get_event_loop_policy()


@pytest.fixture
def temp_directory():
    """Create a temporary directory for tests"""
    temp_dir = tempfile.mkdtemp(prefix="docker_tools_test_")
    yield Path(temp_dir)
    # Cleanup
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.fixture
def mock_project_service():
    """Create a mock ProjectService"""
    from services.project_service import ProjectService

    service = Mock(spec=ProjectService)

    # Mock common methods
    service.get_folder_alias = Mock(return_value=None)
    service.get_folder_sort_order = Mock(
        side_effect=lambda x: {
            "pre-edit": 0,
            "post-edit": 1,
            "post-edit2": 2,
            "correct-edit": 3,
        }.get(x, 99)
    )

    service.get_archive_name = Mock(
        side_effect=lambda parent, name: f"{name.replace('-', '')}_{parent.replace('-', '')}.zip"
    )

    service.get_docker_tag = Mock(
        side_effect=lambda parent, name: f"{name.replace('-', '')}:{parent.replace('-', '')}"
    )

    return service


@pytest.fixture
def sample_project():
    """Create a sample Project instance"""
    from models.project import Project

    return Project(
        parent="pre-edit",
        name="test-project",
        path=Path("/test/pre-edit/test-project"),
        relative_path="pre-edit/test-project",
    )


@pytest.fixture
def sample_projects():
    """Create a list of sample Project instances"""
    from models.project import Project

    versions = ["pre-edit", "post-edit", "post-edit2", "correct-edit"]
    projects = []

    for version in versions:
        project = Project(
            parent=version,
            name="test-project",
            path=Path(f"/test/{version}/test-project"),
            relative_path=f"{version}/test-project",
        )
        projects.append(project)

    return projects


@pytest.fixture
def mock_platform_service():
    """Create a mock PlatformService"""
    from services.platform_service import PlatformService

    service = Mock(spec=PlatformService)

    # Mock static methods
    service.get_platform = Mock(return_value="linux")
    service.is_windows = Mock(return_value=False)
    service.find_bash_executable = Mock(return_value="/bin/bash")
    service.create_archive_command = Mock(
        return_value=(["zip", "-r", "archive.zip", "."], False)
    )
    service.create_bash_command = Mock(
        return_value=(["bash", "-c", "echo test"], 'bash -c "echo test"')
    )
    service.get_error_message = Mock(return_value="Error occurred")

    return service


@pytest.fixture
def async_task_manager():
    """Create and setup an async task manager for tests"""
    from utils.async_utils import ImprovedAsyncTaskManager

    manager = ImprovedAsyncTaskManager()
    manager.setup_event_loop()

    yield manager

    # Cleanup
    manager.shutdown(timeout=2.0)


# Test markers
def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")
    config.addinivalue_line("markers", "asyncio: marks tests as async tests")


# Async test helpers
@pytest.fixture
async def async_client():
    """Create an async client for testing"""
    # This would be used if we had an async API to test
    pass


# Logging configuration for tests
@pytest.fixture(autouse=True)
def configure_logging():
    """Configure logging for tests"""
    import logging

    # Set log level for tests
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


# Performance timing
@pytest.fixture
def timer():
    """Simple timer fixture for performance testing"""
    import time

    class Timer:
        def __init__(self):
            self.start_time = None
            self.elapsed = None

        def start(self):
            self.start_time = time.time()

        def stop(self):
            if self.start_time:
                self.elapsed = time.time() - self.start_time
                return self.elapsed
            return None

    return Timer()


# Mock file system helpers
@pytest.fixture
def mock_file_system(temp_directory):
    """Create a mock file system structure"""

    class MockFileSystem:
        def __init__(self, base_path):
            self.base_path = base_path

        def create_project_structure(self, versions, projects):
            """Create a project directory structure"""
            created_paths = []

            for version in versions:
                version_path = self.base_path / version
                version_path.mkdir(exist_ok=True)

                for project in projects:
                    project_path = version_path / project
                    project_path.mkdir(exist_ok=True)
                    created_paths.append(project_path)

                    # Add some default files
                    (project_path / "README.md").write_text(f"# {project}")
                    (project_path / "main.py").write_text("print('Hello')")

            return created_paths

        def create_file(self, path, content=""):
            """Create a file with content"""
            file_path = self.base_path / path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)
            return file_path

    return MockFileSystem(temp_directory)


# Cleanup helpers
@pytest.fixture(autouse=True)
def cleanup_async_resources():
    """Ensure async resources are cleaned up after each test"""
    yield

    # Force cleanup of any remaining async tasks
    try:
        loop = asyncio.get_running_loop()
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
    except RuntimeError:
        pass  # No loop running


# Test data generators
@pytest.fixture
def generate_test_commits():
    """Generate test git commits"""

    def generator(count=5):
        commits = []
        for i in range(count):
            commits.append(
                {
                    "hash": f"abc{i:03d}",
                    "author": f"Developer {i}",
                    "date": f"2023-12-{i+1:02d}",
                    "subject": f"Commit message {i}",
                }
            )
        return commits

    return generator
