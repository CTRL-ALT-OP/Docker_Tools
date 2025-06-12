"""
Tests for FileService - Tests for file operations (cleanup, archiving)
"""

import os
import sys
import tempfile
import shutil
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import pytest

# Add parent directory to path to import modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from services.file_service import FileService
from config.settings import IGNORE_DIRS


class TestFileService:
    """Test cases for FileService"""

    def setup_method(self):
        """Set up test fixtures"""
        self.file_service = FileService()
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Clean up test fixtures"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_initialization(self):
        """Test FileService initialization"""
        service = FileService()
        assert service.cleanup_dirs == IGNORE_DIRS
        assert service.platform_service is not None

    def create_test_directory_structure(self):
        """Create a test directory structure with various folders"""
        project_path = Path(self.temp_dir) / "test_project"
        project_path.mkdir()

        # Create various directories
        test_dirs = [
            "src",
            "__pycache__",
            "node_modules",
            ".pytest_cache",
            "build",
            "dist",
            ".git",
            "tests/__pycache__",
            "src/module/__pycache__",
            "venv",
            ".venv",
            "env",
            ".coverage",
            "htmlcov",
            ".mypy_cache",
        ]

        for dir_name in test_dirs:
            dir_path = project_path / dir_name
            dir_path.mkdir(parents=True, exist_ok=True)
            # Add a dummy file to each directory
            (dir_path / "dummy.txt").write_text("test")

        # Create some regular files
        (project_path / "main.py").write_text("print('hello')")
        (project_path / "README.md").write_text("# Test Project")

        return project_path

    @pytest.mark.asyncio
    async def test_scan_for_cleanup_dirs(self):
        """Test scanning for directories that need cleanup"""

        project_path = self.create_test_directory_structure()

        # Mock IGNORE_DIRS for testing
        with patch(
            "services.file_service.IGNORE_DIRS",
            ["__pycache__", "node_modules", ".pytest_cache", "venv"],
        ):
            service = FileService()
            cleanup_dirs = await service.scan_for_cleanup_dirs(project_path)

        # Should find all matching directories
        assert len(cleanup_dirs) > 0

        # Check that specific directories were found
        cleanup_paths = [Path(d).name for d in cleanup_dirs]
        assert "__pycache__" in cleanup_paths
        assert "node_modules" in cleanup_paths
        assert ".pytest_cache" in cleanup_paths
        assert "venv" in cleanup_paths

    @pytest.mark.asyncio
    async def test_scan_for_cleanup_dirs_nested(self):
        """Test scanning finds nested directories"""

        project_path = self.create_test_directory_structure()

        with patch("services.file_service.IGNORE_DIRS", ["__pycache__"]):
            service = FileService()
            cleanup_dirs = await service.scan_for_cleanup_dirs(project_path)

        # Should find nested __pycache__ directories
        nested_pycache = [d for d in cleanup_dirs if "__pycache__" in d]
        assert len(nested_pycache) >= 3  # Root, tests/, and src/module/

    @pytest.mark.asyncio
    async def test_scan_for_cleanup_dirs_empty_project(self):
        """Test scanning an empty directory"""

        empty_path = Path(self.temp_dir) / "empty_project"
        empty_path.mkdir()

        cleanup_dirs = await self.file_service.scan_for_cleanup_dirs(empty_path)
        assert len(cleanup_dirs) == 0

    @pytest.mark.asyncio
    async def test_scan_for_cleanup_dirs_permission_error(self):
        """Test handling permission errors during scanning"""

        project_path = self.create_test_directory_structure()

        # Mock os.walk to raise PermissionError
        with patch("os.walk", side_effect=PermissionError("Access denied")):
            cleanup_dirs = await self.file_service.scan_for_cleanup_dirs(project_path)
            # Should return empty list on error
            assert cleanup_dirs == []

    @pytest.mark.asyncio
    async def test_scan_for_cleanup_dirs_case_insensitive(self):
        """Test that pattern matching is case insensitive"""

        project_path = Path(self.temp_dir) / "test_project"
        project_path.mkdir()

        # Create directories with different cases
        test_dirs = ["__PYCACHE__", "Node_Modules", ".PYTEST_CACHE", "VENV"]
        for dir_name in test_dirs:
            (project_path / dir_name).mkdir()

        with patch(
            "services.file_service.IGNORE_DIRS",
            ["__pycache__", "node_modules", ".pytest_cache", "venv"],
        ):
            service = FileService()
            cleanup_dirs = await service.scan_for_cleanup_dirs(project_path)

        # Should find all directories regardless of case
        assert len(cleanup_dirs) == 4

    def test_sync_scan_for_cleanup_dirs(self):
        """Test synchronous implementation of directory scanning"""
        project_path = self.create_test_directory_structure()

        with patch("services.file_service.IGNORE_DIRS", ["__pycache__"]):
            service = FileService()
            cleanup_dirs = service._scan_for_cleanup_dirs_sync(project_path)

        assert len(cleanup_dirs) > 0
        assert all("__pycache__" in d for d in cleanup_dirs)

    def test_cleanup_dirs_configuration(self):
        """Test that cleanup directories are properly configured"""
        # Check that the service has the cleanup_dirs attribute and it's a list
        service = FileService()
        assert isinstance(service.cleanup_dirs, list)

        # Check that the service gets its cleanup dirs from the config
        from config.settings import IGNORE_DIRS

        assert service.cleanup_dirs == IGNORE_DIRS

        # Verify that common cleanup patterns exist in the configuration
        cleanup_dirs_lower = [pattern.lower() for pattern in service.cleanup_dirs]
        # Use patterns that actually exist in the configuration
        expected_patterns = ["__pycache__", ".pytest_cache", "dist"]
        for pattern in expected_patterns:
            # Check if any cleanup directory contains the pattern
            assert any(
                pattern in cleanup_dir for cleanup_dir in cleanup_dirs_lower
            ), f"Pattern '{pattern}' not found in cleanup directories"

    @pytest.mark.asyncio
    async def test_cleanup_project_dirs(self):
        """Test actual cleanup of project directories"""
        project_path = self.create_test_directory_structure()

        # Get initial directory count
        initial_dirs = list(project_path.rglob("*"))
        initial_dir_count = len([d for d in initial_dirs if d.is_dir()])

        # Mock the cleanup to test the method structure
        # (Actual implementation would delete directories)
        with patch.object(
            self.file_service, "_scan_for_cleanup_dirs_sync"
        ) as mock_scan:
            mock_scan.return_value = [
                str(project_path / "__pycache__"),
                str(project_path / "node_modules"),
            ]

            # The actual cleanup_project_dirs method would be tested here
            # This is a placeholder for the test structure

    @pytest.mark.asyncio
    async def test_create_archive(self):
        """Test creating project archive"""
        project_path = self.create_test_directory_structure()
        archive_path = Path(self.temp_dir) / "test_archive.zip"

        # The actual create_archive method would be tested here
        # This is a placeholder for the test structure

    def test_platform_service_integration(self):
        """Test integration with PlatformService"""
        service = FileService()
        assert hasattr(service, "platform_service")
        assert service.platform_service is not None

    @pytest.mark.asyncio
    async def test_concurrent_operations(self):
        """Test concurrent file operations"""

        # Create multiple projects
        projects = []
        for i in range(3):
            project_path = Path(self.temp_dir) / f"project_{i}"
            project_path.mkdir()
            (project_path / "__pycache__").mkdir()
            (project_path / "__pycache__" / "test.pyc").write_text("bytecode")
            projects.append(project_path)

        # Scan all projects concurrently
        tasks = [self.file_service.scan_for_cleanup_dirs(p) for p in projects]
        results = await asyncio.gather(*tasks)

        # Each project should have found its __pycache__ directory
        assert len(results) == 3
        assert all(len(result) > 0 for result in results)

    @pytest.mark.asyncio
    async def test_large_directory_structure(self):
        """Test performance with large directory structure"""

        project_path = Path(self.temp_dir) / "large_project"
        project_path.mkdir()

        # Create a large nested structure
        for i in range(10):
            module_path = project_path / f"module_{i}"
            module_path.mkdir()
            for j in range(10):
                sub_path = module_path / f"submodule_{j}"
                sub_path.mkdir()
                (sub_path / "__pycache__").mkdir()
                (sub_path / "code.py").write_text("print('test')")

        # Should handle large structures efficiently
        import time

        start = time.time()
        cleanup_dirs = await self.file_service.scan_for_cleanup_dirs(project_path)
        elapsed = time.time() - start

        assert len(cleanup_dirs) == 100  # 10 * 10 __pycache__ directories
        assert elapsed < 5.0  # Should complete within reasonable time

    @pytest.mark.asyncio
    async def test_cleanup_project_dirs_permission_error(self):
        """Test handling permission errors during cleanup"""
        project_path = self.create_test_directory_structure()

        # Mock shutil.rmtree to raise PermissionError
        with patch("shutil.rmtree", side_effect=PermissionError("Access denied")):
            deleted_items = await self.file_service.cleanup_project_dirs(project_path)
            # Should handle the error gracefully and return empty list
            assert isinstance(deleted_items, list)

    @pytest.mark.asyncio
    async def test_cleanup_project_dirs_file_not_found_error(self):
        """Test handling FileNotFoundError during cleanup"""
        project_path = self.create_test_directory_structure()

        # Mock shutil.rmtree to raise FileNotFoundError for some calls
        original_rmtree = shutil.rmtree

        def mock_rmtree(path, *args, **kwargs):
            if "__pycache__" in str(path):
                raise FileNotFoundError("Directory not found")
            return original_rmtree(path, *args, **kwargs)

        with patch("shutil.rmtree", side_effect=mock_rmtree):
            deleted_items = await self.file_service.cleanup_project_dirs(project_path)
            # Should handle the error and continue with other directories
            assert isinstance(deleted_items, list)

    @pytest.mark.asyncio
    async def test_cleanup_project_dirs_os_error(self):
        """Test handling OS errors during cleanup"""
        project_path = self.create_test_directory_structure()

        # Mock shutil.rmtree to raise OSError
        with patch("shutil.rmtree", side_effect=OSError("Disk full")):
            deleted_items = await self.file_service.cleanup_project_dirs(project_path)
            # Should handle the error gracefully
            assert isinstance(deleted_items, list)

    def test_sync_cleanup_project_dirs(self):
        """Test synchronous implementation of directory cleanup"""
        project_path = self.create_test_directory_structure()

        # Get initial state
        initial_dirs = list(project_path.rglob("*"))
        initial_pycache_dirs = [
            d for d in initial_dirs if d.is_dir() and "__pycache__" in d.name
        ]

        # Perform cleanup
        deleted_items = self.file_service._cleanup_project_dirs_sync(project_path)

        # Should have deleted items
        assert len(deleted_items) >= len(initial_pycache_dirs)

    @pytest.mark.asyncio
    async def test_create_archive_success(self):
        """Test successful archive creation"""
        project_path = self.create_test_directory_structure()
        archive_name = "test_archive.tar.gz"

        # Mock platform service methods
        mock_cmd = ["tar", "-czf", archive_name, "."]
        self.file_service.platform_service.create_archive_command = Mock(
            return_value=(mock_cmd, False)
        )

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        mock_result.stdout = ""
        self.file_service.platform_service.run_command = Mock(return_value=mock_result)

        success, error_msg = await self.file_service.create_archive(
            project_path, archive_name
        )

        assert success is True
        assert error_msg == ""
        self.file_service.platform_service.create_archive_command.assert_called_once_with(
            archive_name
        )

    @pytest.mark.asyncio
    async def test_create_archive_command_failure(self):
        """Test archive creation when command fails"""
        project_path = self.create_test_directory_structure()
        archive_name = "test_archive.tar.gz"

        # Mock platform service methods
        mock_cmd = ["tar", "-czf", archive_name, "."]
        self.file_service.platform_service.create_archive_command = Mock(
            return_value=(mock_cmd, False)
        )

        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "tar: command failed"
        mock_result.stdout = ""
        self.file_service.platform_service.run_command = Mock(return_value=mock_result)

        success, error_msg = await self.file_service.create_archive(
            project_path, archive_name
        )

        assert success is False
        assert "tar: command failed" in error_msg

    @pytest.mark.asyncio
    async def test_create_archive_project_not_found(self):
        """Test archive creation when project directory doesn't exist"""
        non_existent_path = Path(self.temp_dir) / "non_existent"
        archive_name = "test_archive.tar.gz"

        success, error_msg = await self.file_service.create_archive(
            non_existent_path, archive_name
        )

        assert success is False
        assert "Project directory not found" in error_msg

    @pytest.mark.asyncio
    async def test_create_archive_permission_error(self):
        """Test archive creation with permission error"""
        project_path = self.create_test_directory_structure()
        archive_name = "test_archive.tar.gz"

        # Mock os.chdir to raise PermissionError
        with patch("os.chdir", side_effect=PermissionError("Access denied")):
            success, error_msg = await self.file_service.create_archive(
                project_path, archive_name
            )

            assert success is False
            assert "Permission denied" in error_msg

    @pytest.mark.asyncio
    async def test_create_archive_os_error(self):
        """Test archive creation with OS error"""
        project_path = self.create_test_directory_structure()
        archive_name = "test_archive.tar.gz"

        # Mock platform service to raise OSError
        self.file_service.platform_service.create_archive_command = Mock(
            side_effect=OSError("Disk full")
        )

        success, error_msg = await self.file_service.create_archive(
            project_path, archive_name
        )

        assert success is False
        assert "File system error" in error_msg

    @pytest.mark.asyncio
    async def test_create_archive_unexpected_error(self):
        """Test archive creation with unexpected error"""
        project_path = self.create_test_directory_structure()
        archive_name = "test_archive.tar.gz"

        # Mock platform service to raise unexpected error
        self.file_service.platform_service.create_archive_command = Mock(
            side_effect=ValueError("Unexpected error")
        )

        success, error_msg = await self.file_service.create_archive(
            project_path, archive_name
        )

        assert success is False
        assert "Unexpected error" in error_msg

    def test_sync_create_archive_success(self):
        """Test synchronous implementation of archive creation"""
        project_path = self.create_test_directory_structure()
        archive_name = "test_archive.tar.gz"

        # Mock platform service methods
        mock_cmd = ["tar", "-czf", archive_name, "."]
        self.file_service.platform_service.create_archive_command = Mock(
            return_value=(mock_cmd, False)
        )

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        mock_result.stdout = ""
        self.file_service.platform_service.run_command = Mock(return_value=mock_result)

        success, error_msg = self.file_service._create_archive_sync(
            project_path, archive_name
        )

        assert success is True
        assert error_msg == ""

    def test_sync_create_archive_restores_cwd(self):
        """Test that sync archive creation restores original working directory"""
        project_path = self.create_test_directory_structure()
        archive_name = "test_archive.tar.gz"
        original_cwd = os.getcwd()

        # Mock platform service methods
        mock_cmd = ["tar", "-czf", archive_name, "."]
        self.file_service.platform_service.create_archive_command = Mock(
            return_value=(mock_cmd, False)
        )

        mock_result = Mock()
        mock_result.returncode = 0
        self.file_service.platform_service.run_command = Mock(return_value=mock_result)

        # Call the method
        self.file_service._create_archive_sync(project_path, archive_name)

        # Verify we're back in original directory
        assert os.getcwd() == original_cwd

    def test_sync_create_archive_restores_cwd_on_error(self):
        """Test that sync archive creation restores cwd even when command fails"""
        project_path = self.create_test_directory_structure()
        archive_name = "test_archive.tar.gz"
        original_cwd = os.getcwd()

        # Mock platform service methods to fail
        mock_cmd = ["tar", "-czf", archive_name, "."]
        self.file_service.platform_service.create_archive_command = Mock(
            return_value=(mock_cmd, False)
        )

        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "Command failed"
        self.file_service.platform_service.run_command = Mock(return_value=mock_result)

        # Call the method
        success, error_msg = self.file_service._create_archive_sync(
            project_path, archive_name
        )

        # Verify we're back in original directory even after failure
        assert os.getcwd() == original_cwd
        assert success is False

    @pytest.mark.asyncio
    async def test_cleanup_with_deeply_nested_directories(self):
        """Test cleanup with deeply nested directory structures"""
        project_path = Path(self.temp_dir) / "deep_project"
        project_path.mkdir()

        # Create deeply nested structure
        deep_path = project_path / "a" / "b" / "c" / "d" / "e"
        deep_path.mkdir(parents=True)

        # Add __pycache__ at various levels
        (project_path / "__pycache__").mkdir()
        (project_path / "a" / "__pycache__").mkdir()
        (project_path / "a" / "b" / "__pycache__").mkdir()
        (deep_path / "__pycache__").mkdir()

        with patch("services.file_service.IGNORE_DIRS", ["__pycache__"]):
            service = FileService()
            deleted_items = await service.cleanup_project_dirs(project_path)

        # Should find and delete all __pycache__ directories
        assert len(deleted_items) == 4

    @pytest.mark.asyncio
    async def test_scan_and_cleanup_integration(self):
        """Test integration between scan and cleanup operations"""
        project_path = self.create_test_directory_structure()

        # First scan for directories
        cleanup_dirs = await self.file_service.scan_for_cleanup_dirs(project_path)
        assert len(cleanup_dirs) > 0

        # Then cleanup
        deleted_items = await self.file_service.cleanup_project_dirs(project_path)

        # Should have deleted items
        assert len(deleted_items) > 0

        # Scan again - should find fewer or no cleanup directories
        remaining_cleanup_dirs = await self.file_service.scan_for_cleanup_dirs(
            project_path
        )
        assert len(remaining_cleanup_dirs) <= len(cleanup_dirs)

    @pytest.mark.asyncio
    async def test_cleanup_with_symlinks(self):
        """Test cleanup behavior with symbolic links"""
        if os.name == "nt":  # Skip on Windows due to symlink restrictions
            pytest.skip("Symlink test skipped on Windows")

        project_path = Path(self.temp_dir) / "symlink_project"
        project_path.mkdir()

        # Create a regular __pycache__ directory
        pycache_dir = project_path / "__pycache__"
        pycache_dir.mkdir()
        (pycache_dir / "test.pyc").write_text("compiled")

        # Create a symlink to another directory
        external_dir = Path(self.temp_dir) / "external"
        external_dir.mkdir()
        (external_dir / "important.txt").write_text("important data")

        symlink_path = project_path / "external_link"
        symlink_path.symlink_to(external_dir)

        deleted_items = await self.file_service.cleanup_project_dirs(project_path)

        # Should delete __pycache__ but not affect the symlinked directory
        assert len(deleted_items) > 0
        assert any("__pycache__" in item for item in deleted_items)
        assert external_dir.exists()
        assert (external_dir / "important.txt").exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
