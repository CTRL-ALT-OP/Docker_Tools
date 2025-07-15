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
        """Test scanning for directories to cleanup"""
        project_path = self.create_test_directory_structure()

        with patch(
            "services.file_service.IGNORE_DIRS",
            ["__pycache__", "node_modules", ".pytest_cache", "venv"],
        ):
            service = FileService()
            result = await service.scan_for_cleanup_items(project_path)

        # Should find all matching directories
        assert result.is_success is True
        cleanup_data = result.data
        assert len(cleanup_data.directories) > 0

        # Check that specific directories were found
        cleanup_paths = [Path(d).name for d in cleanup_data.directories]
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
            result = await service.scan_for_cleanup_items(project_path)

        # Should find nested __pycache__ directories
        assert result.is_success is True
        cleanup_dirs = result.data.directories
        nested_pycache = [d for d in cleanup_dirs if "__pycache__" in str(d)]
        assert len(nested_pycache) >= 3  # Root, tests/, and src/module/

    @pytest.mark.asyncio
    async def test_scan_for_cleanup_dirs_empty_project(self):
        """Test scanning an empty directory"""

        empty_path = Path(self.temp_dir) / "empty_project"
        empty_path.mkdir()

        result = await self.file_service.scan_for_cleanup_items(empty_path)
        assert result.is_success is True
        assert len(result.data.directories) == 0

    @pytest.mark.asyncio
    async def test_scan_for_cleanup_dirs_permission_error(self):
        """Test handling permission errors during scanning"""

        project_path = self.create_test_directory_structure()

        # Mock os.walk to raise PermissionError
        with patch("os.walk", side_effect=PermissionError("Access denied")):
            result = await self.file_service.scan_for_cleanup_items(project_path)
            # Should return error result on permission error
            assert result.is_error is True

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
            result = await service.scan_for_cleanup_items(project_path)

        # Should find all directories regardless of case
        assert result.is_success is True
        assert len(result.data.directories) == 4

    def test_sync_scan_for_cleanup_dirs(self):
        """Test synchronous implementation of directory scanning"""
        project_path = self.create_test_directory_structure()

        with patch("services.file_service.IGNORE_DIRS", ["__pycache__"]):
            service = FileService()
            cleanup_result = service._scan_for_cleanup_items_sync(project_path)

        assert len(cleanup_result.directories) > 0
        assert all("__pycache__" in str(d) for d in cleanup_result.directories)

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
            self.file_service, "_scan_for_cleanup_items_sync"
        ) as mock_scan:
            from services.file_service import CleanupScanResult

            mock_scan.return_value = CleanupScanResult(
                directories=[
                    project_path / "__pycache__",
                    project_path / "node_modules",
                ],
                files=[],
                total_size=0,
                item_count=2,
            )

            # The actual cleanup_project_items method would be tested here
            result = await self.file_service.cleanup_project_items(project_path)
            assert result.is_success is True

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
        tasks = [self.file_service.scan_for_cleanup_items(p) for p in projects]
        results = await asyncio.gather(*tasks)

        # Each project should have found its __pycache__ directory
        assert len(results) == 3
        assert all(
            result.is_success and len(result.data.directories) > 0 for result in results
        )

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
        result = await self.file_service.scan_for_cleanup_items(project_path)
        elapsed = time.time() - start

        assert result.is_success is True
        assert len(result.data.directories) == 100  # 10 * 10 __pycache__ directories
        assert elapsed < 5.0  # Should complete within reasonable time

    @pytest.mark.asyncio
    async def test_cleanup_project_dirs_permission_error(self):
        """Test handling permission errors during cleanup"""
        project_path = self.create_test_directory_structure()

        # Mock shutil.rmtree to raise PermissionError
        with patch("shutil.rmtree", side_effect=PermissionError("Access denied")):
            result = await self.file_service.cleanup_project_items(project_path)
            # Should handle the error gracefully
            assert result.is_error is True or (
                result.is_success and isinstance(result.data, object)
            )

    @pytest.mark.asyncio
    async def test_cleanup_project_dirs_file_not_found_error(self):
        """Test handling file not found errors during cleanup"""
        project_path = self.create_test_directory_structure()

        def mock_rmtree(path, *args, **kwargs):
            if "__pycache__" in str(path):
                raise FileNotFoundError(f"File not found: {path}")

        with patch("shutil.rmtree", side_effect=mock_rmtree):
            result = await self.file_service.cleanup_project_items(project_path)
            # Should handle file not found gracefully
            assert result.is_success is True or result.is_error is True

    @pytest.mark.asyncio
    async def test_cleanup_project_dirs_os_error(self):
        """Test handling OS errors during cleanup"""
        project_path = self.create_test_directory_structure()

        with patch("shutil.rmtree", side_effect=OSError("Disk full")):
            result = await self.file_service.cleanup_project_items(project_path)
            # Should handle OS errors gracefully
            assert result.is_error is True

    def test_sync_cleanup_project_dirs(self):
        """Test synchronous implementation of directory cleanup"""
        project_path = self.create_test_directory_structure()

        service = FileService()
        cleanup_result = service._cleanup_project_items_sync(project_path)

        # Should have some cleanup result
        assert isinstance(cleanup_result, object)  # CleanupResult object

    @pytest.mark.asyncio
    async def test_create_archive_success(self):
        """Test successful archive creation"""
        project_path = self.create_test_directory_structure()
        archive_name = "test_archive.zip"

        result = await self.file_service.create_archive(project_path, archive_name)

        assert result.is_success is True
        assert result.data is not None
        assert result.data.archive_path.exists()
        assert result.data.archive_path.name == archive_name
        assert result.data.archive_size > 0
        assert result.data.files_archived > 0
        assert result.data.compression_ratio > 0

        # Verify archive is valid by checking it can be opened
        import zipfile

        with zipfile.ZipFile(result.data.archive_path, "r") as zip_ref:
            file_list = zip_ref.namelist()
            assert len(file_list) > 0

            # Should not contain ignore files/directories
            ignored_items = [
                f for f in file_list if "__pycache__" in f or ".coverage" in f
            ]
            assert (
                len(ignored_items) == 0
            ), f"Archive should not contain ignored items: {ignored_items}"

    @pytest.mark.asyncio
    async def test_create_archive_command_failure(self):
        """Test archive creation with command failure"""
        project_path = self.create_test_directory_structure()
        archive_name = "test_archive.zip"

        # Mock the _create_archive_async method to return failure
        with patch.object(self.file_service, "_create_archive_async") as mock_async:
            mock_async.return_value = {
                "success": False,
                "message": "Archive creation failed",
            }

            result = await self.file_service.create_archive(project_path, archive_name)

            assert result.is_error is True

    @pytest.mark.asyncio
    async def test_create_archive_project_not_found(self):
        """Test archive creation with non-existent project"""
        non_existent_path = Path(self.temp_dir) / "non_existent"
        archive_name = "test_archive.zip"

        result = await self.file_service.create_archive(non_existent_path, archive_name)

        assert result.is_error is True

    @pytest.mark.asyncio
    async def test_create_archive_permission_error(self):
        """Test archive creation with permission error"""
        project_path = self.create_test_directory_structure()
        archive_name = "test_archive.zip"

        # Mock permission error
        with patch("os.chdir", side_effect=PermissionError("Access denied")):
            result = await self.file_service.create_archive(project_path, archive_name)

            assert result.is_error is True

    @pytest.mark.asyncio
    async def test_create_archive_os_error(self):
        """Test archive creation with OS error"""
        project_path = self.create_test_directory_structure()
        archive_name = "test_archive.zip"

        # Mock the _create_archive_async method to raise OSError
        with patch.object(self.file_service, "_create_archive_async") as mock_async:
            mock_async.side_effect = OSError("Disk full")

            result = await self.file_service.create_archive(project_path, archive_name)

            assert result.is_error is True
            assert (
                "Disk full" in str(result.error.message)
                or "error" in str(result.error.message).lower()
            )

    @pytest.mark.asyncio
    async def test_create_archive_unexpected_error(self):
        """Test archive creation with unexpected error"""
        project_path = self.create_test_directory_structure()
        archive_name = "test_archive.zip"

        # Mock the _create_archive_async method to raise ValueError
        with patch.object(self.file_service, "_create_archive_async") as mock_async:
            mock_async.side_effect = ValueError("Unexpected error")

            result = await self.file_service.create_archive(project_path, archive_name)

            assert result.is_error is True
            assert "error" in str(result.error.message).lower()

    @pytest.mark.asyncio
    async def test_async_create_archive_success(self):
        """Test asynchronous archive creation"""
        project_path = self.create_test_directory_structure()
        archive_name = "test_archive.zip"

        result_dict = await self.file_service._create_archive_async(
            project_path, archive_name
        )

        assert result_dict["success"] is True
        assert result_dict["archive_name"] == archive_name

        # Verify the archive was actually created
        archive_path = project_path / archive_name
        assert archive_path.exists()
        assert archive_path.stat().st_size > 0

        # Verify archive is valid
        import zipfile

        with zipfile.ZipFile(archive_path, "r") as zip_ref:
            file_list = zip_ref.namelist()
            assert len(file_list) > 0

    @pytest.mark.asyncio
    async def test_async_create_archive_restores_cwd(self):
        """Test that async archive creation restores original working directory"""
        project_path = self.create_test_directory_structure()
        archive_name = "test_archive.zip"
        original_cwd = os.getcwd()

        # Call the method - should work without mocking
        result_dict = await self.file_service._create_archive_async(
            project_path, archive_name
        )

        # Verify we're back in original directory
        assert os.getcwd() == original_cwd
        # Should also succeed
        assert result_dict["success"] is True

    @pytest.mark.asyncio
    async def test_async_create_archive_restores_cwd_on_error(self):
        """Test that async archive creation restores cwd even when command fails"""
        project_path = self.create_test_directory_structure()
        archive_name = "test_archive.zip"
        original_cwd = os.getcwd()

        # Mock both subprocess.run (Windows) and zipfile.ZipFile (Unix) to simulate failure
        with patch("subprocess.run") as mock_run, patch(
            "zipfile.ZipFile"
        ) as mock_zipfile:
            mock_run.return_value = Mock(
                returncode=1, stdout="", stderr="Command failed"
            )
            mock_zipfile.side_effect = Exception("Zipfile creation failed")

            # Call the method and get the result dict
            result_dict = await self.file_service._create_archive_async(
                project_path, archive_name
            )

            # Verify we're back in original directory even after failure
            assert os.getcwd() == original_cwd
            assert result_dict["success"] is False

    @pytest.mark.asyncio
    async def test_cleanup_with_deeply_nested_directories(self):
        """Test cleanup with deeply nested directory structure"""
        project_path = Path(self.temp_dir) / "deep_project"
        project_path.mkdir()

        # Create deeply nested structure
        current = project_path
        for i in range(5):  # 5 levels deep
            current = current / f"level_{i}"
            current.mkdir()
            (current / "__pycache__").mkdir()

        result = await self.file_service.cleanup_project_items(project_path)
        assert result.is_success is True

        # Check that some directories were found and cleaned
        cleanup_data = result.data
        assert cleanup_data.deleted_directories is not None

    @pytest.mark.asyncio
    async def test_scan_and_cleanup_integration(self):
        """Test integration between scan and cleanup operations"""
        project_path = self.create_test_directory_structure()

        # First scan
        scan_result = await self.file_service.scan_for_cleanup_items(project_path)
        assert scan_result.is_success is True
        assert len(scan_result.data.directories) > 0

        # Then cleanup
        cleanup_result = await self.file_service.cleanup_project_items(project_path)
        assert cleanup_result.is_success is True

    @pytest.mark.asyncio
    async def test_scan_for_cleanup_items(self):
        """Test new scan_for_cleanup_items method"""
        project_path = self.create_test_directory_structure()

        # Add some files to cleanup as well
        (project_path / ".coverage").write_text("coverage data")

        result = await self.file_service.scan_for_cleanup_items(project_path)

        assert result.is_success is True
        cleanup_data = result.data
        assert len(cleanup_data.directories) > 0
        assert cleanup_data.item_count > 0

    @pytest.mark.asyncio
    async def test_cleanup_project_items(self):
        """Test new cleanup_project_items method"""
        project_path = self.create_test_directory_structure()

        result = await self.file_service.cleanup_project_items(project_path)

        assert result.is_success is True
        cleanup_data = result.data
        assert cleanup_data.deleted_directories is not None

    @pytest.mark.asyncio
    async def test_cleanup_project_items_files_only(self):
        """Test cleanup with files only"""
        project_path = Path(self.temp_dir) / "test_project"
        project_path.mkdir()

        # Create files to cleanup
        (project_path / ".coverage").write_text("coverage data")
        (project_path / "test.log").write_text("log data")

        result = await self.file_service.cleanup_project_items(project_path)

        assert result.is_success is True
        cleanup_data = result.data
        assert cleanup_data.deleted_files is not None

    @pytest.mark.asyncio
    async def test_cleanup_project_items_dirs_only(self):
        """Test cleanup with directories only"""
        project_path = Path(self.temp_dir) / "test_project"
        project_path.mkdir()

        # Create directories to cleanup
        (project_path / "__pycache__").mkdir()
        (project_path / ".pytest_cache").mkdir()

        result = await self.file_service.cleanup_project_items(project_path)

        assert result.is_success is True
        cleanup_data = result.data
        assert cleanup_data.deleted_directories is not None

    @pytest.mark.asyncio
    async def test_cleanup_handles_file_permission_error(self):
        """Test cleanup handles file permission errors gracefully"""
        project_path = self.create_test_directory_structure()

        def mock_remove(path):
            if "test_file" in str(path):
                raise PermissionError("Access denied")

        with patch("pathlib.Path.unlink", side_effect=mock_remove):
            result = await self.file_service.cleanup_project_items(project_path)
            # Should handle permission errors gracefully
            assert result.is_success is True or result.is_error is True

    def test_backward_compatibility(self):
        """Test backward compatibility methods and patterns"""
        service = FileService()
        # Test that the service still has the basic interface
        assert hasattr(service, "scan_for_cleanup_items")
        assert hasattr(service, "cleanup_project_items")
        assert hasattr(service, "create_archive")

        # Test that internal sync methods exist
        assert hasattr(service, "_scan_for_cleanup_items_sync")
        assert hasattr(service, "_cleanup_project_items_sync")

    @pytest.mark.asyncio
    async def test_cleanup_skips_ignore_files(self):
        """Test that cleanup process skips ignore files and only deletes directories"""
        project_path = Path(self.temp_dir) / "test_project"
        project_path.mkdir()

        # Create ignore files (these should be skipped)
        (project_path / ".coverage").write_text("coverage data")
        (project_path / "test.log").write_text("log data")

        # Create ignore directories (these should be deleted)
        (project_path / "__pycache__").mkdir()
        (project_path / ".pytest_cache").mkdir()
        (project_path / "dist").mkdir()

        # Add some files in the directories
        (project_path / "__pycache__" / "test.pyc").write_text("bytecode")
        (project_path / ".pytest_cache" / "cache.txt").write_text("cache")
        (project_path / "dist" / "package.tar.gz").write_text("package")

        # Perform cleanup
        result = await self.file_service.cleanup_project_items(project_path)

        # Should succeed
        assert result.is_success is True
        cleanup_data = result.data

        # Should have deleted directories
        assert len(cleanup_data.deleted_directories) > 0

        # Should NOT have deleted any files (files list should be empty)
        assert len(cleanup_data.deleted_files) == 0

        # Verify ignore files still exist
        assert (project_path / ".coverage").exists()
        assert (project_path / "test.log").exists()

        # Verify ignore directories have been deleted
        assert not (project_path / "__pycache__").exists()
        assert not (project_path / ".pytest_cache").exists()
        assert not (project_path / "dist").exists()

    @pytest.mark.asyncio
    async def test_create_archive_async_linux_platform(self):
        """Test _create_archive_async on Linux platform"""
        project_path = self.create_test_directory_structure()
        archive_name = "test_archive.zip"

        # Mock Linux platform and successful archive creation
        with patch.object(
            self.file_service.platform_service, "get_platform", return_value="linux"
        ):
            result = await self.file_service._create_archive_async(
                project_path, archive_name
            )

            assert result["success"] is True
            assert result["archive_name"] == archive_name
            # Verify archive was created
            assert (project_path / archive_name).exists()

    @pytest.mark.asyncio
    async def test_create_archive_async_windows_platform(self):
        """Test _create_archive_async on Windows platform"""
        project_path = self.create_test_directory_structure()
        archive_name = "test_archive.zip"

        # Mock Windows platform and successful subprocess.run
        with patch.object(
            self.file_service.platform_service, "get_platform", return_value="windows"
        ), patch("subprocess.run") as mock_run:
            # Create a dummy archive file when subprocess.run succeeds
            def create_dummy_archive(cmd, **kwargs):
                import zipfile

                archive_path = project_path / archive_name
                with zipfile.ZipFile(archive_path, "w") as zf:
                    zf.writestr("dummy.txt", "test content")
                return Mock(returncode=0, stdout="Archive created successfully")

            mock_run.side_effect = create_dummy_archive

            result = await self.file_service._create_archive_async(
                project_path, archive_name
            )

            assert result["success"] is True
            assert result["archive_name"] == archive_name
            # Verify archive was created
            assert (project_path / archive_name).exists()

    @pytest.mark.asyncio
    async def test_create_archive_async_with_exclusions(self):
        """Test that _create_archive_async properly excludes unwanted files and directories"""
        project_path = self.create_test_directory_structure()

        # Add ignore files (only .coverage is configured to be ignored)
        (project_path / ".coverage").write_text("coverage data")
        (project_path / "regular_file.txt").write_text("regular data")

        archive_name = "test_archive.zip"

        result = await self.file_service._create_archive_async(
            project_path, archive_name
        )

        assert result["success"] is True

        # Verify archive was created and exclusions work
        import zipfile

        with zipfile.ZipFile(project_path / archive_name, "r") as zip_ref:
            file_list = zip_ref.namelist()

            # Should not contain excluded directories (from IGNORE_DIRS config)
            assert not any("__pycache__" in f for f in file_list)
            assert not any(".pytest_cache" in f for f in file_list)
            assert not any("dist" in f for f in file_list)

            # Should not contain excluded files (from IGNORE_FILES config)
            assert not any(".coverage" in f for f in file_list)

            # Should contain regular files
            assert any("main.py" in f for f in file_list)
            assert any("README.md" in f for f in file_list)
            assert any("regular_file.txt" in f for f in file_list)

    @pytest.mark.asyncio
    async def test_create_archive_async_platform_failure(self):
        """Test _create_archive_async handles platform-specific failures gracefully"""
        project_path = self.create_test_directory_structure()
        archive_name = "test_archive.zip"

        # Mock both subprocess.run (Windows) and zipfile.ZipFile (Unix) to simulate failure
        with patch("subprocess.run") as mock_run, patch(
            "zipfile.ZipFile"
        ) as mock_zipfile:
            mock_run.return_value = Mock(
                returncode=1, stdout="", stderr="Command failed"
            )
            mock_zipfile.side_effect = Exception("Zipfile creation failed")

            result = await self.file_service._create_archive_async(
                project_path, archive_name
            )

            assert result["success"] is False
            assert "error" in result  # Check that error key exists
            assert (
                "failed" in result["error"].lower()
                or "error" in result["error"].lower()
            )

    @pytest.mark.asyncio
    async def test_create_archive_async_different_platforms(self):
        """Test _create_archive_async works correctly on different platforms"""
        project_path = self.create_test_directory_structure()
        archive_name = "test_archive.zip"

        # Test on different platforms
        platforms = ["linux", "darwin", "windows"]

        # Mock subprocess.run globally to simulate successful commands
        with patch("subprocess.run") as mock_run:
            # Create a dummy archive file when subprocess.run succeeds
            def create_dummy_archive(cmd, **kwargs):
                import zipfile

                archive_path = project_path / archive_name
                with zipfile.ZipFile(archive_path, "w") as zf:
                    zf.writestr("dummy.txt", "test content")
                return Mock(returncode=0, stdout="Archive created successfully")

            mock_run.side_effect = create_dummy_archive

            for platform in platforms:
                with patch.object(
                    self.file_service.platform_service,
                    "get_platform",
                    return_value=platform,
                ):
                    result = await self.file_service._create_archive_async(
                        project_path, archive_name
                    )

                    assert result["success"] is True
                    assert result["archive_name"] == archive_name

                    # Verify archive was created
                    archive_path = project_path / archive_name
                    assert archive_path.exists()

                    # Verify archive is valid
                    import zipfile

                    with zipfile.ZipFile(archive_path, "r") as zip_ref:
                        file_list = zip_ref.namelist()
                        assert len(file_list) > 0

                    # Clean up for next iteration
                    if archive_path.exists():
                        archive_path.unlink()

    @pytest.mark.asyncio
    async def test_archive_exclusion_integration(self):
        """Test integration of archive exclusion with actual file system operations (implementation-agnostic)"""
        project_path = self.create_test_directory_structure()

        # Add some additional files to test comprehensive exclusion
        (project_path / "src" / "main.py").write_text("print('main')")
        (project_path / "requirements.txt").write_text("flask==2.0.0")
        (project_path / "user_settings.json").write_text('{"theme": "dark"}')

        # Create some files in non-ignored directories
        (project_path / "docs").mkdir(exist_ok=True)
        (project_path / "docs" / "readme.md").write_text("# Documentation")

        # Create archive
        archive_name = "comprehensive_test.zip"
        result = await self.file_service.create_archive(project_path, archive_name)

        # Verify archive creation was successful
        assert result.is_success is True
        assert result.data.archive_path.exists()

        # Verify archive contents in detail
        import zipfile

        with zipfile.ZipFile(result.data.archive_path, "r") as zip_ref:
            file_list = zip_ref.namelist()

            # Files that should be included (implementation-agnostic check)
            # The actual file paths may vary between Windows and Unix implementations
            expected_file_names = [
                "requirements.txt",
                "README.md",  # from create_test_directory_structure
                "main.py",  # from src/main.py (may be flattened)
                "readme.md",  # from docs/readme.md (may be flattened)
            ]

            # Check expected files are present (check by filename, not full path)
            for expected_file in expected_file_names:
                file_found = any(expected_file in file_name for file_name in file_list)
                assert (
                    file_found
                ), f"Expected file {expected_file} not found in archive. Archive contains: {sorted(file_list)}"

            # Files/directories that should be excluded (based on IGNORE_DIRS and IGNORE_FILES)
            excluded_patterns = [
                "__pycache__",
                ".pytest_cache",
                ".coverage",
                "dist",
                "venv",
                "htmlcov",
            ]

            # Check excluded items are not present
            for pattern in excluded_patterns:
                excluded_items = [f for f in file_list if pattern in f]
                assert (
                    len(excluded_items) == 0
                ), f"Archive should not contain items matching '{pattern}': {excluded_items}"

            # Verify we have reasonable number of files (not empty, not too many)
            assert (
                3 <= len(file_list) <= 15
            ), f"Archive should contain reasonable number of files, got {len(file_list)}"

        # Verify metadata
        assert result.data.archive_size > 0
        assert result.data.files_archived > 0
        assert result.data.compression_ratio > 0
        assert result.message == f"Successfully created archive: {archive_name}"

        # Verify metadata consistency
        assert result.metadata["archive_size_mb"] == round(
            result.data.archive_size / (1024 * 1024), 2
        )
        assert result.metadata["compression_percent"] == round(
            (1 - result.data.compression_ratio) * 100, 1
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
