"""
Test to verify the test setup is working correctly
"""

import os
import sys
import pytest

# Add parent directory to path to import modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


class TestSetup:
    """Test cases to verify test setup"""

    def test_imports(self):
        """Test that all modules can be imported"""
        # Services
        from services.docker_service import DockerService
        from services.project_service import ProjectService
        from services.file_service import FileService
        from services.git_service import GitService, GitCommit
        from services.platform_service import PlatformService
        from services.sync_service import SyncService
        from services.project_group_service import ProjectGroup, ProjectGroupService
        
        # Models
        from models.project import Project
        
        # Utils
        from utils.async_utils import (
            run_subprocess_async,
            run_in_executor,
            ImprovedAsyncTaskManager
        )
        
        # Config
        from config.settings import FOLDER_ALIASES, IGNORE_DIRS
        from config.commands import DOCKER_COMMANDS, GIT_COMMANDS
        
        # If we get here, all imports worked
        assert True

    def test_fixtures_available(self, temp_directory, mock_project_service):
        """Test that pytest fixtures are available"""
        assert temp_directory.exists()
        assert temp_directory.is_dir()
        assert mock_project_service is not None

    @pytest.mark.asyncio
    async def test_async_support(self):
        """Test that async tests work"""
        import asyncio
        await asyncio.sleep(0.01)
        assert True

    def test_mock_support(self):
        """Test that mocking works"""
        from unittest.mock import Mock, patch
        
        mock_obj = Mock()
        mock_obj.method.return_value = "mocked"
        assert mock_obj.method() == "mocked"
        
        with patch("os.path.exists") as mock_exists:
            mock_exists.return_value = True
            assert os.path.exists("/fake/path") is True

    def test_path_handling(self, temp_directory):
        """Test path operations"""
        test_file = temp_directory / "test.txt"
        test_file.write_text("test content")
        
        assert test_file.exists()
        assert test_file.read_text() == "test content"

    def test_markers(self):
        """Test that pytest markers work"""
        # This test has no special markers
        assert True

    @pytest.mark.slow
    def test_slow_marker(self):
        """Test marked as slow"""
        import time
        time.sleep(0.1)
        assert True

    @pytest.mark.unit
    def test_unit_marker(self):
        """Test marked as unit test"""
        assert 1 + 1 == 2

    def test_environment(self):
        """Test that environment is set up correctly"""
        # Check Python version
        assert sys.version_info >= (3, 7)
        
        # Check current directory is in path
        assert parent_dir in sys.path
        
        # Check we can access test directory
        test_dir = os.path.dirname(__file__)
        assert os.path.exists(test_dir)
        assert os.path.isdir(test_dir)

    def test_coverage_tools(self):
        """Test that coverage tools are available"""
        try:
            import coverage
            import pytest_cov
            assert True
        except ImportError:
            # Coverage tools are optional
            pytest.skip("Coverage tools not installed")

    def test_test_discovery(self):
        """Test that pytest can discover tests"""
        test_dir = os.path.dirname(__file__)
        test_files = [f for f in os.listdir(test_dir) if f.startswith("test_") and f.endswith(".py")]
        
        # Should find at least this file and others
        assert len(test_files) >= 2
        assert "test_setup.py" in test_files
        assert "test_sync_service.py" in test_files


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
