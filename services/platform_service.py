"""
Platform-specific operations service
"""

import os
import platform
import subprocess
from typing import List, Tuple, Optional

from config.commands import BASH_PATHS, ARCHIVE_COMMANDS, ERROR_MESSAGES, SHELL_COMMANDS


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

        # Try to find bash on Windows
        for path in BASH_PATHS["windows"]:
            if os.path.exists(path):
                return path

        return None

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
            bash_exe = PlatformService.find_bash_executable()
            if bash_exe:
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
