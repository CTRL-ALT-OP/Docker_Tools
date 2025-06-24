"""
Platform-specific operations service
"""

import os
import platform
import subprocess
from typing import List, Tuple, Optional

from config.commands import (
    BASH_PATHS,
    ARCHIVE_COMMANDS,
    ERROR_MESSAGES,
    SHELL_COMMANDS,
    FILE_OPEN_COMMANDS,
    TEST_COMMANDS,
    SYSTEM_COMMANDS,
)


class PlatformService:
    """Service for handling platform-specific operations"""

    @staticmethod
    def get_platform() -> str:
        """Get the current platform (windows, linux, darwin)"""
        return platform.system().lower()

    @staticmethod
    def is_windows() -> bool:
        """Check if running on Windows"""
        return PlatformService.get_platform() == "windows"

    @staticmethod
    def find_bash_executable() -> Optional[str]:
        """Find bash executable on Windows"""
        current_platform = PlatformService.get_platform()

        if current_platform != "windows":
            return SHELL_COMMANDS["bash"]  # Available natively on Unix systems

        return next(
            (path for path in BASH_PATHS["windows"] if os.path.exists(path)), None
        )

    @staticmethod
    def create_archive_command(archive_name: str) -> Tuple[List[str], bool]:
        """
        Create platform-specific archive command
        Returns (command, use_shell)
        """
        current_platform = PlatformService.get_platform()

        if current_platform == "windows":
            # Use PowerShell Compress-Archive on Windows
            cmd = ARCHIVE_COMMANDS["windows"]["cmd"]
            # Format the archive name in the command
            formatted_cmd = [cmd[0], cmd[1], cmd[2].format(archive_name=archive_name)]
            return (formatted_cmd, True)
        else:
            # Use zip command on Mac/Linux
            archive_cmd = ARCHIVE_COMMANDS.get(
                current_platform, ARCHIVE_COMMANDS["linux"]
            )
            zip_cmd = archive_cmd["zip"]
            # Format the archive name and exclusion
            formatted_cmd = [
                zip_cmd[0],
                zip_cmd[1],
                archive_name,
                zip_cmd[3],
                zip_cmd[4],
                archive_name,
            ]
            return (formatted_cmd, False)

    @staticmethod
    def create_bash_command(command: str) -> Tuple[List[str], str]:
        """
        Create platform-specific bash command
        Returns (command_list, display_command)
        """
        if PlatformService.is_windows():
            if bash_exe := PlatformService.find_bash_executable():
                return ([bash_exe, "-c", command], f"'{bash_exe}' -c \"{command}\"")
            else:
                return ([f'bash -c "{command}"'], f'bash -c "{command}"')
        else:
            return (["bash", "-c", command], f'bash -c "{command}"')

    @staticmethod
    def get_error_message(error_type: str) -> str:
        """Get platform-specific error message"""
        current_platform = PlatformService.get_platform()
        platform_errors = ERROR_MESSAGES.get(current_platform, ERROR_MESSAGES["linux"])
        return platform_errors.get(error_type, f"Error: {error_type}")

    @staticmethod
    def run_command(
        cmd: List[str], use_shell: bool = False, **kwargs
    ) -> subprocess.CompletedProcess:
        """Run a command with platform-appropriate settings"""
        return subprocess.run(cmd, shell=use_shell, **kwargs)

    @staticmethod
    def create_file_open_command(file_path: str) -> List[str]:
        """
        Create platform-specific command to open a file
        Returns command list for subprocess execution
        """
        current_platform = PlatformService.get_platform()

        if current_platform in FILE_OPEN_COMMANDS:
            cmd_template = FILE_OPEN_COMMANDS[current_platform]
        else:
            # Default to linux behavior for unknown platforms
            cmd_template = FILE_OPEN_COMMANDS["linux"]

        # Replace {file_path} placeholder with actual file path
        return [
            part.format(file_path=file_path) if "{file_path}" in part else part
            for part in cmd_template
        ]

    @staticmethod
    def open_file_with_default_application(file_path: str) -> Tuple[bool, str]:
        """
        Open a file with the default system application
        Returns (success, error_message)
        """
        try:
            cmd = PlatformService.create_file_open_command(file_path)
            current_platform = PlatformService.get_platform()

            # Windows requires shell=True for the 'start' command
            use_shell = current_platform == "windows"

            result = PlatformService.run_command(cmd, use_shell=use_shell, check=True)
            return True, ""
        except subprocess.CalledProcessError as e:
            return False, f"Failed to open file: {e}"
        except Exception as e:
            return False, f"Error opening file: {str(e)}"

    @staticmethod
    def is_unix_like() -> bool:
        """Check if running on a Unix-like system (Linux/macOS)"""
        return PlatformService.get_platform() in ["linux", "darwin"]

    @staticmethod
    def get_pwd_command() -> List[str]:
        """Get platform-specific command to print working directory"""
        if PlatformService.is_windows():
            return SYSTEM_COMMANDS["pwd"]["windows"]
        else:
            return SYSTEM_COMMANDS["pwd"]["unix"]

    @staticmethod
    def create_git_init_command() -> List[str]:
        """Create git initialization command"""
        return TEST_COMMANDS["git_init"]

    @staticmethod
    def create_pytest_command(
        verbose: bool = False, with_coverage: bool = False
    ) -> List[str]:
        """
        Create pytest command based on options
        Returns command list for subprocess execution
        """
        if with_coverage:
            return TEST_COMMANDS["pytest_with_coverage"].copy()
        elif verbose:
            return TEST_COMMANDS["pytest_verbose"].copy()
        else:
            return TEST_COMMANDS["pytest"].copy()

    @staticmethod
    def check_docker_available() -> Tuple[bool, str]:
        """
        Check if Docker is available on the system
        Returns (available, error_message)
        """
        try:
            result = PlatformService.run_command(
                SYSTEM_COMMANDS["docker_version"], capture_output=True, check=True
            )
            return True, ""
        except subprocess.CalledProcessError:
            return False, "Docker is not available or not running"
        except FileNotFoundError:
            return False, "Docker is not installed"
        except Exception as e:
            return False, f"Error checking Docker: {str(e)}"
