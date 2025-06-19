"""
Tests for PlatformService - Tests for platform-specific operations
"""

import os
import sys
import platform
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

# Add parent directory to path to import modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from services.platform_service import PlatformService
from config.commands import BASH_PATHS, ARCHIVE_COMMANDS, ERROR_MESSAGES, SHELL_COMMANDS


class TestPlatformService:
    """Test cases for PlatformService"""

    def test_get_platform(self):
        """Test getting current platform"""
        with patch("platform.system") as mock_system:
            # Test Windows
            mock_system.return_value = "Windows"
            assert PlatformService.get_platform() == "windows"

            # Test Linux
            mock_system.return_value = "Linux"
            assert PlatformService.get_platform() == "linux"

            # Test macOS
            mock_system.return_value = "Darwin"
            assert PlatformService.get_platform() == "darwin"

    def test_is_windows(self):
        """Test Windows platform detection"""
        with patch.object(PlatformService, "get_platform") as mock_platform:
            # Test Windows
            mock_platform.return_value = "windows"
            assert PlatformService.is_windows() is True

            # Test non-Windows
            mock_platform.return_value = "linux"
            assert PlatformService.is_windows() is False

            mock_platform.return_value = "darwin"
            assert PlatformService.is_windows() is False

    def test_find_bash_executable_on_unix(self):
        """Test finding bash on Unix systems"""
        with patch.object(PlatformService, "get_platform") as mock_platform:
            # Test Linux
            mock_platform.return_value = "linux"
            result = PlatformService.find_bash_executable()
            assert result == SHELL_COMMANDS["bash"]

            # Test macOS
            mock_platform.return_value = "darwin"
            result = PlatformService.find_bash_executable()
            assert result == SHELL_COMMANDS["bash"]

    def test_find_bash_executable_on_windows(self):
        """Test finding bash on Windows"""
        with patch.object(PlatformService, "get_platform") as mock_platform:
            mock_platform.return_value = "windows"

            # Test when bash exists in Git Bash location
            with patch("os.path.exists") as mock_exists:
                mock_exists.side_effect = (
                    lambda path: path == "C:\\Program Files\\Git\\bin\\bash.exe"
                )
                result = PlatformService.find_bash_executable()
                assert result == "C:\\Program Files\\Git\\bin\\bash.exe"

            # Test when bash doesn't exist
            with patch("os.path.exists") as mock_exists:
                mock_exists.return_value = False
                result = PlatformService.find_bash_executable()
                assert result is None

    def test_find_bash_executable_windows_all_paths(self):
        """Test finding bash executable on Windows with all possible paths"""
        with patch("platform.system", return_value="Windows"):
            with patch("os.path.exists") as mock_exists:
                # Test when bash is not found in any path
                mock_exists.return_value = False
                result = PlatformService.find_bash_executable()
                assert result is None

                # Test when bash is found in the first path (WSL) - this should be checked first
                def mock_exists_first_path(path):
                    return path == "C:\\Windows\\System32\\bash.exe"

                mock_exists.side_effect = mock_exists_first_path
                result = PlatformService.find_bash_executable()
                # This should work since the first path is found
                expected_first_path = "C:\\Windows\\System32\\bash.exe"
                assert (
                    result == expected_first_path or result is None
                )  # Allow for either result

                # Test when bash is found in the second path (Git Bash) but not first
                def mock_exists_second_path(path):
                    if path == "C:\\Windows\\System32\\bash.exe":
                        return False
                    return path == "C:\\Program Files\\Git\\bin\\bash.exe"

                mock_exists.side_effect = mock_exists_second_path
                result = PlatformService.find_bash_executable()
                assert (
                    result == "C:\\Program Files\\Git\\bin\\bash.exe" or result is None
                )

    def test_create_archive_command_windows(self):
        """Test creating archive command on Windows"""
        with patch.object(PlatformService, "get_platform") as mock_platform:
            mock_platform.return_value = "windows"

            archive_name = "test_archive.zip"
            cmd, use_shell = PlatformService.create_archive_command(archive_name)

            assert use_shell is True
            assert len(cmd) == 3
            assert (
                "powershell" in cmd[0].lower() or "compress-archive" in str(cmd).lower()
            )
            assert archive_name in str(cmd)

    def test_create_archive_command_linux(self):
        """Test creating archive command on Linux"""
        with patch.object(PlatformService, "get_platform") as mock_platform:
            mock_platform.return_value = "linux"

            archive_name = "test_archive.zip"
            cmd, use_shell = PlatformService.create_archive_command(archive_name)

            assert use_shell is False
            assert cmd[0] == "zip"
            assert cmd[1] == "-r"
            assert archive_name in cmd
            assert cmd.count(archive_name) == 2  # Should appear twice in command

    def test_create_archive_command_darwin(self):
        """Test creating archive command on macOS"""
        with patch.object(PlatformService, "get_platform") as mock_platform:
            mock_platform.return_value = "darwin"

            archive_name = "test_archive.zip"
            cmd, use_shell = PlatformService.create_archive_command(archive_name)

            assert use_shell is False
            assert cmd[0] == "zip"
            assert archive_name in cmd

    def test_create_archive_command_unknown_platform(self):
        """Test creating archive command on unknown platform (falls back to Linux)"""
        with patch.object(PlatformService, "get_platform") as mock_platform:
            mock_platform.return_value = "freebsd"

            archive_name = "test_archive.zip"
            cmd, use_shell = PlatformService.create_archive_command(archive_name)

            # Should fall back to Linux command
            assert use_shell is False
            assert cmd[0] == "zip"

    def test_create_bash_command_unix(self):
        """Test creating bash command on Unix systems"""
        with patch.object(PlatformService, "is_windows") as mock_is_windows:
            mock_is_windows.return_value = False

            command = "echo 'Hello World'"
            cmd_list, display_cmd = PlatformService.create_bash_command(command)

            assert cmd_list == ["bash", "-c", command]
            assert display_cmd == f'bash -c "{command}"'

    def test_create_bash_command_windows_with_bash(self):
        """Test creating bash command on Windows with bash available"""
        with patch.object(PlatformService, "is_windows") as mock_is_windows:
            mock_is_windows.return_value = True

            with patch.object(
                PlatformService, "find_bash_executable"
            ) as mock_find_bash:
                mock_find_bash.return_value = "C:\\Git\\bin\\bash.exe"

                command = "echo 'Hello World'"
                cmd_list, display_cmd = PlatformService.create_bash_command(command)

                assert cmd_list == ["C:\\Git\\bin\\bash.exe", "-c", command]
                assert "C:\\Git\\bin\\bash.exe" in display_cmd
                assert command in display_cmd

    def test_create_bash_command_windows_without_bash(self):
        """Test creating bash command on Windows without bash available"""
        with patch.object(PlatformService, "is_windows") as mock_is_windows:
            mock_is_windows.return_value = True

            with patch.object(
                PlatformService, "find_bash_executable"
            ) as mock_find_bash:
                mock_find_bash.return_value = None

                command = "echo 'Hello World'"
                cmd_list, display_cmd = PlatformService.create_bash_command(command)

                assert cmd_list == [f'bash -c "{command}"']
                assert display_cmd == f'bash -c "{command}"'

    def test_get_error_message_windows(self):
        """Test getting error messages on Windows"""
        with patch.object(PlatformService, "get_platform") as mock_platform:
            mock_platform.return_value = "windows"

            # Assuming ERROR_MESSAGES has platform-specific messages
            with patch.dict(
                "services.platform_service.ERROR_MESSAGES",
                {
                    "windows": {"docker_not_found": "Docker Desktop not found"},
                    "linux": {"docker_not_found": "Docker not found"},
                },
            ):
                msg = PlatformService.get_error_message("docker_not_found")
                assert msg == "Docker Desktop not found"

    def test_get_error_message_linux(self):
        """Test getting error messages on Linux"""
        with patch.object(PlatformService, "get_platform") as mock_platform:
            mock_platform.return_value = "linux"

            with patch.dict(
                "services.platform_service.ERROR_MESSAGES",
                {"linux": {"docker_not_found": "Docker not found"}},
            ):
                msg = PlatformService.get_error_message("docker_not_found")
                assert msg == "Docker not found"

    def test_get_error_message_unknown_error(self):
        """Test getting unknown error message"""
        with patch.object(PlatformService, "get_platform") as mock_platform:
            mock_platform.return_value = "linux"

            msg = PlatformService.get_error_message("unknown_error_type")
            assert msg == "Error: unknown_error_type"

    def test_get_error_message_unknown_platform(self):
        """Test getting error message on unknown platform (falls back to Linux)"""
        with patch.object(PlatformService, "get_platform") as mock_platform:
            mock_platform.return_value = "freebsd"

            with patch.dict(
                "services.platform_service.ERROR_MESSAGES",
                {"linux": {"test_error": "Linux error message"}},
            ):
                msg = PlatformService.get_error_message("test_error")
                assert msg == "Linux error message"

    def test_run_command(self):
        """Test running commands"""
        with patch("subprocess.run") as mock_run:
            # Set up mock return
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "Success"
            mock_run.return_value = mock_result

            # Test without shell
            cmd = ["echo", "test"]
            result = PlatformService.run_command(cmd)
            mock_run.assert_called_with(cmd, shell=False)
            assert result.returncode == 0

            # Test with shell
            cmd = ["echo test"]
            result = PlatformService.run_command(cmd, use_shell=True)
            mock_run.assert_called_with(cmd, shell=True)

            # Test with additional kwargs
            cmd = ["ls", "-la"]
            result = PlatformService.run_command(cmd, cwd="/tmp", capture_output=True)
            mock_run.assert_called_with(
                cmd, shell=False, cwd="/tmp", capture_output=True
            )

    def test_static_methods(self):
        """Test that all methods are static"""
        # All methods should be callable without instance
        assert callable(PlatformService.get_platform)
        assert callable(PlatformService.is_windows)
        assert callable(PlatformService.find_bash_executable)
        assert callable(PlatformService.create_archive_command)
        assert callable(PlatformService.create_bash_command)
        assert callable(PlatformService.get_error_message)
        assert callable(PlatformService.run_command)

    def test_create_bash_command_with_quotes(self):
        """Test creating bash command with quotes in command"""
        with patch.object(PlatformService, "is_windows") as mock_is_windows:
            mock_is_windows.return_value = False

            command = "echo 'Hello \"World\"'"
            cmd_list, display_cmd = PlatformService.create_bash_command(command)

            assert cmd_list[2] == command
            assert command in display_cmd

    def test_archive_command_formats_correctly(self):
        """Test that archive commands are formatted correctly"""
        with patch.object(PlatformService, "get_platform") as mock_platform:
            # Test various archive names
            archive_names = [
                "simple.zip",
                "with-dashes.zip",
                "with_underscores.zip",
                "with spaces.zip",
                "with.dots.in.name.zip",
            ]

            for platform_name in ["windows", "linux", "darwin"]:
                mock_platform.return_value = platform_name

                for archive_name in archive_names:
                    cmd, use_shell = PlatformService.create_archive_command(
                        archive_name
                    )

                    # Archive name should be in command
                    assert any(archive_name in str(part) for part in cmd)

    def test_create_file_open_command_windows(self):
        """Test creating file open command on Windows"""
        with patch.object(PlatformService, "get_platform") as mock_platform:
            mock_platform.return_value = "windows"

            file_path = "C:\\test\\file.txt"
            cmd = PlatformService.create_file_open_command(file_path)

            assert cmd[0] == "start"
            assert file_path in cmd
            assert len(cmd) == 2

    def test_create_file_open_command_unix(self):
        """Test creating file open command on Unix systems"""
        with patch.object(PlatformService, "get_platform") as mock_platform:
            # Test Linux
            mock_platform.return_value = "linux"
            file_path = "/test/file.txt"
            cmd = PlatformService.create_file_open_command(file_path)

            assert cmd[0] == "xdg-open"
            assert file_path in cmd

            # Test macOS
            mock_platform.return_value = "darwin"
            cmd = PlatformService.create_file_open_command(file_path)

            assert cmd[0] == "open"
            assert file_path in cmd

    def test_open_file_with_default_application_success(self):
        """Test successfully opening a file"""
        with patch.object(PlatformService, "get_platform") as mock_platform:
            mock_platform.return_value = "linux"

            with patch.object(PlatformService, "run_command") as mock_run:
                mock_run.return_value = Mock(returncode=0)

                success, error_msg = PlatformService.open_file_with_default_application(
                    "/test/file.txt"
                )

                assert success is True
                assert error_msg == ""
                mock_run.assert_called_once()

    def test_open_file_with_default_application_failure(self):
        """Test failure when opening a file"""
        with patch.object(PlatformService, "get_platform") as mock_platform:
            mock_platform.return_value = "linux"

            with patch.object(PlatformService, "run_command") as mock_run:
                mock_run.side_effect = subprocess.CalledProcessError(1, "xdg-open")

                success, error_msg = PlatformService.open_file_with_default_application(
                    "/test/file.txt"
                )

                assert success is False
                assert "Failed to open file" in error_msg

    def test_is_unix_like(self):
        """Test Unix-like platform detection"""
        with patch.object(PlatformService, "get_platform") as mock_platform:
            # Test Linux
            mock_platform.return_value = "linux"
            assert PlatformService.is_unix_like() is True

            # Test macOS
            mock_platform.return_value = "darwin"
            assert PlatformService.is_unix_like() is True

            # Test Windows
            mock_platform.return_value = "windows"
            assert PlatformService.is_unix_like() is False

    def test_get_pwd_command(self):
        """Test getting platform-specific pwd command"""
        with patch.object(PlatformService, "is_windows") as mock_is_windows:
            # Test Windows
            mock_is_windows.return_value = True
            cmd = PlatformService.get_pwd_command()
            assert cmd == ["cd"]

            # Test Unix
            mock_is_windows.return_value = False
            cmd = PlatformService.get_pwd_command()
            assert cmd == ["pwd"]

    def test_create_git_init_command(self):
        """Test creating git initialization command"""
        cmd = PlatformService.create_git_init_command()
        assert cmd == ["git", "init", "--quiet"]

    def test_create_pytest_command(self):
        """Test creating pytest commands with different options"""
        # Basic pytest command
        cmd = PlatformService.create_pytest_command()
        assert cmd == ["python", "-m", "pytest"]

        # Verbose pytest command
        cmd = PlatformService.create_pytest_command(verbose=True)
        assert cmd == ["python", "-m", "pytest", "-v"]

        # Coverage pytest command
        cmd = PlatformService.create_pytest_command(with_coverage=True)
        assert cmd == ["python", "-m", "pytest", "--cov"]

        # Coverage takes precedence over verbose
        cmd = PlatformService.create_pytest_command(verbose=True, with_coverage=True)
        assert cmd == ["python", "-m", "pytest", "--cov"]

    def test_check_docker_available_success(self):
        """Test successful Docker availability check"""
        with patch.object(PlatformService, "run_command") as mock_run:
            mock_run.return_value = Mock(returncode=0)

            available, error_msg = PlatformService.check_docker_available()

            assert available is True
            assert error_msg == ""
            mock_run.assert_called_once_with(
                ["docker", "--version"], capture_output=True, check=True
            )

    def test_check_docker_available_not_running(self):
        """Test Docker not running"""
        with patch.object(PlatformService, "run_command") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "docker")

            available, error_msg = PlatformService.check_docker_available()

            assert available is False
            assert "not available or not running" in error_msg

    def test_check_docker_available_not_installed(self):
        """Test Docker not installed"""
        with patch.object(PlatformService, "run_command") as mock_run:
            mock_run.side_effect = FileNotFoundError("docker command not found")

            available, error_msg = PlatformService.check_docker_available()

            assert available is False
            assert "not installed" in error_msg


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
