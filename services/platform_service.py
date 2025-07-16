"""
Platform-specific operations service
"""

import contextlib
import os
import platform
import subprocess
from typing import List, Tuple, Optional, Union, Dict, Any, Callable

from config.config import get_config

COMMANDS = get_config().commands.commands
BASH_PATHS = get_config().commands.bash_paths
ERROR_MESSAGES = get_config().commands.error_messages

# Import async utilities if available
try:
    from utils.async_utils import (
        run_subprocess_async,
        run_subprocess_streaming_async,
        run_in_executor,
    )

    ASYNC_AVAILABLE = True
except ImportError:
    ASYNC_AVAILABLE = False


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
            return COMMANDS["SHELL_COMMANDS"][
                "bash"
            ]  # Available natively on Unix systems

        return next(
            (path for path in BASH_PATHS["windows"] if os.path.exists(path)), None
        )

    @staticmethod
    def create_archive_command(archive_name: str) -> Tuple[List[str], bool]:
        """
        Create platform-specific archive command using command keys
        Returns (command, use_shell)
        """
        current_platform = PlatformService.get_platform()

        if current_platform not in COMMANDS["ARCHIVE_COMMANDS"]["create"]:
            current_platform = "linux"  # Default fallback

        archive_cmd_template = COMMANDS["ARCHIVE_COMMANDS"]["create"][current_platform]

        # Use PowerShell Compress-Archive on Windows
        # Format the command template
        formatted_cmd = []
        if current_platform == "windows":
            formatted_cmd.extend(
                cmd_part.format(archive_name=archive_name)
                for cmd_part in archive_cmd_template
            )
            return (formatted_cmd, True)
        else:
            formatted_cmd.extend(
                cmd_part.format(archive_name=archive_name)
                for cmd_part in archive_cmd_template
            )
            return (formatted_cmd, False)

    @staticmethod
    def create_bash_command(command: str) -> Tuple[List[str], str]:
        """
        Create platform-specific bash command using command keys
        Returns (command_list, display_command)
        """
        if PlatformService.is_windows():
            if bash_exe := PlatformService.find_bash_executable():
                # Use the bash_execute template with found bash executable
                formatted_cmd = [bash_exe, "-c", command]
                return (formatted_cmd, f"'{bash_exe}' -c \"{command}\"")
            else:
                # Fallback to system bash
                bash_cmd_template = COMMANDS["SHELL_COMMANDS"]["bash_execute"]
                formatted_cmd = [
                    part.format(command=command) if "{command}" in part else part
                    for part in bash_cmd_template
                ]
                return (formatted_cmd, f'bash -c "{command}"')
        else:
            # Use the standardized bash_execute template
            bash_cmd_template = COMMANDS["SHELL_COMMANDS"]["bash_execute"]
            formatted_cmd = [
                part.format(command=command) if "{command}" in part else part
                for part in bash_cmd_template
            ]
            return (formatted_cmd, f'bash -c "{command}"')

    @staticmethod
    def get_error_message(error_type: str) -> str:
        """Get platform-specific error message"""
        current_platform = PlatformService.get_platform()
        platform_errors = ERROR_MESSAGES.get(current_platform, ERROR_MESSAGES["linux"])
        return platform_errors.get(error_type, f"Error: {error_type}")

    @staticmethod
    def _prepare_command(
        command_key: str, subkey: Optional[str] = None, **kwargs
    ) -> Tuple[Union[List[str], str], bool]:
        """
        Prepare command from COMMANDS dictionary with formatting
        Returns (command, use_shell)
        """
        # Get command template from COMMANDS dictionary
        if command_key not in COMMANDS:
            raise ValueError(f"Unknown command key: {command_key}")

        cmd_template = COMMANDS[command_key]

        # Handle subkey access
        if subkey is not None:
            if not isinstance(cmd_template, dict):
                raise ValueError(f"Command key {command_key} does not support subkeys")
            if subkey not in cmd_template:
                raise ValueError(
                    f"Unknown subkey '{subkey}' for command key '{command_key}'"
                )
            cmd_template = cmd_template[subkey]

        current_platform = PlatformService.get_platform()

        # Handle platform-specific commands
        if isinstance(cmd_template, dict):
            if current_platform in cmd_template:
                cmd_template = cmd_template[current_platform]
            else:
                # Default to linux for unknown platforms
                cmd_template = cmd_template.get("linux", cmd_template.get("unix"))

        # Format command template with kwargs
        if isinstance(cmd_template, str):
            # String commands - format directly
            formatted_cmd = cmd_template.format(**kwargs)
            use_shell = current_platform == "windows"
            return (formatted_cmd, use_shell)
        elif isinstance(cmd_template, list):
            # List commands - format each part
            cmd = [
                (
                    part.format(**kwargs)
                    if isinstance(part, str)
                    and any(f"{{{key}}}" in part for key in kwargs)
                    else part
                )
                for part in cmd_template
            ]
            use_shell = current_platform == "windows" and cmd[0] == "start"
            return (cmd, use_shell)
        else:
            raise ValueError(f"Invalid command template type: {type(cmd_template)}")

    @staticmethod
    def run_command(
        command_key: str,
        subkey: Optional[str] = None,
        cmd: Optional[List[str]] = None,
        use_shell: bool = False,
        **kwargs,
    ) -> Union[Tuple[bool, str], subprocess.CompletedProcess]:
        """
        Run a command with platform-appropriate settings and template formatting

        Args:
            command_key: Key to look up command template in COMMANDS dict
            subkey: Optional subkey within the command group (e.g., 'version' for DOCKER_COMMANDS)
            cmd: Optional direct command list (for backwards compatibility)
            use_shell: Whether to use shell execution
            **kwargs: Template variables to format into the command

        Returns:
            Either (success, error_message) tuple or CompletedProcess depending on usage
        """
        # If direct command provided, use it (backwards compatibility)
        if cmd is not None:
            return subprocess.run(cmd, shell=use_shell, **kwargs)

        # Prepare command
        cmd, use_shell = PlatformService._prepare_command(command_key, subkey, **kwargs)
        return subprocess.run(cmd, shell=use_shell, **kwargs)

    @staticmethod
    def run_command_with_result(
        command_key: str, subkey: Optional[str] = None, **kwargs
    ) -> Tuple[bool, str]:
        """
        Run a command and return success/error tuple

        Args:
            command_key: Key to look up command template in COMMANDS dict (e.g., "FILE_OPEN_COMMANDS")
            subkey: Optional subkey within the command group (e.g., 'version' for DOCKER_COMMANDS)
            **kwargs: Template variables to format into the command

        Returns:
            (success, error_message) tuple
        """
        try:
            # Prepare command
            cmd, use_shell = PlatformService._prepare_command(
                command_key, subkey, **kwargs
            )

            # Special handling for FILE_OPEN_COMMANDS to improve reliability
            if command_key == "FILE_OPEN_COMMANDS":
                return PlatformService._handle_file_open_command(
                    cmd, use_shell, **kwargs
                )

            result = subprocess.run(
                cmd, shell=use_shell, capture_output=True, text=True, timeout=30
            )

            if result.returncode == 0:
                return True, result.stdout.strip() if result.stdout else ""
            error_msg = (
                result.stderr.strip()
                if result.stderr
                else f"Command failed with exit code {result.returncode}"
            )
            return False, error_msg

        except subprocess.TimeoutExpired as e:
            return False, f"Command timed out after 30 seconds: {e}"
        except subprocess.CalledProcessError as e:
            error_msg = (
                e.stderr.strip()
                if e.stderr
                else f"Command failed with exit code {e.returncode}"
            )
            return False, f"Command failed: {error_msg}"
        except Exception as e:
            return False, f"Error: {str(e)}"

    @staticmethod
    def _handle_file_open_command(
        cmd: Union[List[str], str], use_shell: bool, **kwargs
    ) -> Tuple[bool, str]:
        """
        Special handling for file open commands to improve reliability and error reporting
        """
        import os
        from pathlib import Path

        # Extract file path from kwargs
        file_path = kwargs.get("file_path", "")
        if not file_path:
            return False, "No file path provided"

        # Validate that the path exists
        path_obj = Path(file_path)
        if not path_obj.exists():
            return False, f"Path does not exist: {file_path}"

        current_platform = PlatformService.get_platform()

        try:
            if current_platform == "windows":
                # For Windows, we need special handling of the start command
                # Quote the path to handle spaces and special characters
                quoted_path = f'"{file_path}"'

                # Use explorer.exe directly as a more reliable alternative to start
                # start command can be unreliable, especially with paths containing spaces
                explorer_cmd = ["explorer.exe", file_path]

                # Try explorer.exe first
                with contextlib.suppress(
                    subprocess.TimeoutExpired, subprocess.CalledProcessError
                ):
                    result = subprocess.run(
                        explorer_cmd,
                        capture_output=True,
                        text=True,
                        timeout=10,
                        check=False,  # Don't raise on non-zero exit
                    )

                    # Explorer.exe usually returns 1 even on success, so we check differently
                    # If it starts within timeout, consider it successful
                    if result.returncode in [
                        0,
                        1,
                    ]:  # Both 0 and 1 can indicate success for explorer.exe
                        return True, "File explorer opened successfully"
                # Fallback: Use cmd /c start with proper quoting
                start_cmd = ["cmd", "/c", "start", "", quoted_path]
                result = subprocess.run(
                    start_cmd, capture_output=True, text=True, timeout=10, check=False
                )

                if result.returncode == 0:
                    return True, "File explorer opened successfully"
                error_msg = (
                    result.stderr.strip()
                    if result.stderr
                    else f"Start command failed with exit code {result.returncode}"
                )
                return False, f"Failed to open file explorer: {error_msg}"

            else:
                # For Unix-like systems (Linux, macOS)
                result = subprocess.run(
                    cmd,
                    shell=use_shell,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )

                if result.returncode == 0:
                    return True, "File manager opened successfully"
                error_msg = (
                    result.stderr.strip()
                    if result.stderr
                    else f"Command failed with exit code {result.returncode}"
                )
                return False, f"Failed to open file manager: {error_msg}"

        except subprocess.TimeoutExpired:
            return False, "File manager command timed out"
        except Exception as e:
            return False, f"Error opening file manager: {str(e)}"

    # ========== ASYNC METHODS ==========

    @staticmethod
    async def run_command_async(
        command_key: str,
        subkey: Optional[str] = None,
        cmd: Optional[List[str]] = None,
        use_shell: bool = False,
        **kwargs,
    ) -> subprocess.CompletedProcess:
        """
        Async version of run_command

        Args:
            command_key: Key to look up command template in COMMANDS dict
            subkey: Optional subkey within the command group
            cmd: Optional direct command list (for backwards compatibility)
            use_shell: Whether to use shell execution
            **kwargs: Template variables to format into the command and subprocess args

        Returns:
            CompletedProcess result
        """
        if not ASYNC_AVAILABLE:
            raise RuntimeError("Async utilities not available")

        # If direct command provided, use it (backwards compatibility)
        if cmd is not None:
            # Extract subprocess-specific kwargs
            subprocess_kwargs = {
                k: v
                for k, v in kwargs.items()
                if k
                in [
                    "capture_output",
                    "text",
                    "encoding",
                    "errors",
                    "cwd",
                    "timeout",
                    "check",
                ]
            }
            return await run_subprocess_async(cmd, shell=use_shell, **subprocess_kwargs)

        # Prepare command
        cmd, determined_shell = await run_in_executor(
            PlatformService._prepare_command, command_key, subkey, **kwargs
        )

        # Use determined shell unless explicitly overridden
        final_shell = use_shell if "shell" in kwargs else determined_shell

        # Extract subprocess-specific kwargs
        subprocess_kwargs = {
            k: v
            for k, v in kwargs.items()
            if k
            in [
                "capture_output",
                "text",
                "encoding",
                "errors",
                "cwd",
                "timeout",
                "check",
            ]
        }

        return await run_subprocess_async(cmd, shell=final_shell, **subprocess_kwargs)

    @staticmethod
    async def run_command_with_result_async(
        command_key: str, subkey: Optional[str] = None, **kwargs
    ) -> Tuple[bool, str]:
        """
        Async version of run_command_with_result

        Args:
            command_key: Key to look up command template in COMMANDS dict
            subkey: Optional subkey within the command group
            **kwargs: Template variables to format into the command and subprocess args

        Returns:
            (success, error_message) tuple
        """
        if not ASYNC_AVAILABLE:
            raise RuntimeError("Async utilities not available")

        try:
            # Prepare command
            cmd, use_shell = await run_in_executor(
                PlatformService._prepare_command, command_key, subkey, **kwargs
            )

            # Special handling for FILE_OPEN_COMMANDS to improve reliability
            if command_key == "FILE_OPEN_COMMANDS":
                return await PlatformService._handle_file_open_command_async(
                    cmd, use_shell, **kwargs
                )

            # Extract subprocess-specific kwargs
            subprocess_kwargs = {
                k: v
                for k, v in kwargs.items()
                if k
                in [
                    "capture_output",
                    "text",
                    "encoding",
                    "errors",
                    "cwd",
                    "timeout",
                    "check",
                ]
            }

            result = await run_subprocess_async(
                cmd, shell=use_shell, **subprocess_kwargs
            )

            if result.returncode == 0:
                return True, result.stdout.strip() if result.stdout else ""
            else:
                return (
                    False,
                    result.stderr or f"Command failed with code {result.returncode}",
                )

        except subprocess.CalledProcessError as e:
            return False, f"Command failed: {e}"
        except Exception as e:
            return False, f"Error: {str(e)}"

    @staticmethod
    async def _handle_file_open_command_async(
        cmd: Union[List[str], str], use_shell: bool, **kwargs
    ) -> Tuple[bool, str]:
        """
        Special handling for file open commands to improve reliability and error reporting
        """
        import os
        from pathlib import Path

        # Extract file path from kwargs
        file_path = kwargs.get("file_path", "")
        if not file_path:
            return False, "No file path provided"

        # Validate that the path exists
        path_obj = Path(file_path)
        if not path_obj.exists():
            return False, f"Path does not exist: {file_path}"

        current_platform = PlatformService.get_platform()

        try:
            if current_platform == "windows":
                # For Windows, we need special handling of the start command
                # Quote the path to handle spaces and special characters
                quoted_path = f'"{file_path}"'

                # Use explorer.exe directly as a more reliable alternative to start
                # start command can be unreliable, especially with paths containing spaces
                explorer_cmd = ["explorer.exe", file_path]

                # Try explorer.exe first
                with contextlib.suppress(
                    subprocess.TimeoutExpired, subprocess.CalledProcessError
                ):
                    result = await run_subprocess_async(
                        explorer_cmd,
                        capture_output=True,
                        text=True,
                        timeout=10,
                        check=False,  # Don't raise on non-zero exit
                    )

                    # Explorer.exe usually returns 1 even on success, so we check differently
                    # If it starts within timeout, consider it successful
                    if result.returncode in [
                        0,
                        1,
                    ]:  # Both 0 and 1 can indicate success for explorer.exe
                        return True, "File explorer opened successfully"
                # Fallback: Use cmd /c start with proper quoting
                start_cmd = ["cmd", "/c", "start", "", quoted_path]
                result = await run_subprocess_async(
                    start_cmd, capture_output=True, text=True, timeout=10, check=False
                )

                if result.returncode == 0:
                    return True, "File explorer opened successfully"
                error_msg = (
                    result.stderr.strip()
                    if result.stderr
                    else f"Start command failed with exit code {result.returncode}"
                )
                return False, f"Failed to open file explorer: {error_msg}"

            else:
                # For Unix-like systems (Linux, macOS)
                result = await run_subprocess_async(
                    cmd,
                    shell=use_shell,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )

                if result.returncode == 0:
                    return True, "File manager opened successfully"
                error_msg = (
                    result.stderr.strip()
                    if result.stderr
                    else f"Command failed with exit code {result.returncode}"
                )
                return False, f"Failed to open file manager: {error_msg}"

        except subprocess.TimeoutExpired:
            return False, "File manager command timed out"
        except Exception as e:
            return False, f"Error opening file manager: {str(e)}"

    @staticmethod
    async def run_command_streaming_async(
        command_key: str,
        subkey: Optional[str] = None,
        output_callback: Optional[Callable[[str], None]] = None,
        **kwargs,
    ) -> Tuple[int, str]:
        """
        Run command with streaming output asynchronously

        Args:
            command_key: Key to look up command template in COMMANDS dict
            subkey: Optional subkey within the command group
            output_callback: Callback for streaming output
            **kwargs: Template variables to format into the command and subprocess args

        Returns:
            (return_code, full_output) tuple
        """
        if not ASYNC_AVAILABLE:
            raise RuntimeError("Async utilities not available")

        # Prepare command
        cmd, use_shell = await run_in_executor(
            PlatformService._prepare_command, command_key, subkey, **kwargs
        )

        # Extract subprocess-specific kwargs
        subprocess_kwargs = {
            k: v
            for k, v in kwargs.items()
            if k in ["text", "encoding", "errors", "cwd", "timeout"]
        }

        return await run_subprocess_streaming_async(
            cmd, shell=use_shell, output_callback=output_callback, **subprocess_kwargs
        )

    @staticmethod
    async def run_bash_command_async(command: str, **kwargs) -> Tuple[bool, str]:
        """
        Async version of run_bash_command
        """
        return await PlatformService.run_command_with_result_async(
            "SHELL_COMMANDS", subkey="bash_execute", command=command, **kwargs
        )

    @staticmethod
    async def run_docker_command_async(
        docker_cmd_key: str, **kwargs
    ) -> Tuple[bool, str]:
        """
        Async version of run_docker_command
        """
        return await PlatformService.run_command_with_result_async(
            "DOCKER_COMMANDS", subkey=docker_cmd_key, **kwargs
        )

    # ========== EXISTING SYNC METHODS (unchanged) ==========

    @staticmethod
    def run_bash_command(command: str, **kwargs) -> Tuple[bool, str]:
        """
        Execute a bash command using the standardized approach
        Returns (success, error_message)
        """
        return PlatformService.run_command_with_result(
            "SHELL_COMMANDS", subkey="bash_execute", command=command, **kwargs
        )

    @staticmethod
    def open_file_with_default_application(file_path: str) -> Tuple[bool, str]:
        """
        Open a file with the default system application
        Returns (success, error_message)
        """
        return PlatformService.run_command_with_result(
            "FILE_OPEN_COMMANDS", file_path=file_path
        )

    @staticmethod
    def is_unix_like() -> bool:
        """Check if running on a Unix-like system (Linux/macOS)"""
        return PlatformService.get_platform() in ["linux", "darwin"]

    @staticmethod
    def get_pwd_command() -> List[str]:
        """Get platform-specific command to print working directory using command keys"""
        current_platform = PlatformService.get_platform()
        pwd_template = COMMANDS["SYSTEM_COMMANDS"]["pwd"]

        if current_platform == "windows":
            return pwd_template["windows"]
        else:
            return pwd_template["unix"]

    @staticmethod
    def run_pwd_command(**kwargs) -> Tuple[bool, str]:
        """
        Execute pwd command using the standardized approach
        Returns (success, error_message)
        """
        try:
            result = PlatformService.run_command(
                "SYSTEM_COMMANDS",
                subkey="pwd",
                capture_output=True,
                text=True,
                **kwargs,
            )
            if result.returncode == 0:
                return True, result.stdout.strip()
            else:
                return False, result.stderr or "Failed to get current directory"
        except Exception as e:
            return False, f"Error getting current directory: {str(e)}"

    @staticmethod
    def create_git_init_command() -> List[str]:
        """Create git initialization command using correct command key"""
        return COMMANDS["GIT_COMMANDS"]["init"]

    @staticmethod
    def run_git_init(**kwargs) -> Tuple[bool, str]:
        """
        Execute git init using the standardized approach
        Returns (success, error_message)
        """
        return PlatformService.run_command_with_result(
            "GIT_COMMANDS", subkey="init", **kwargs
        )

    @staticmethod
    def create_pytest_command(
        verbose: bool = False, with_coverage: bool = False
    ) -> List[str]:
        """
        Create pytest command based on options using command keys
        Returns command list for subprocess execution
        """
        if with_coverage:
            return COMMANDS["TEST_COMMANDS"]["pytest_with_coverage"].copy()
        elif verbose:
            return COMMANDS["TEST_COMMANDS"]["pytest_verbose"].copy()
        else:
            return COMMANDS["TEST_COMMANDS"]["pytest"].copy()

    @staticmethod
    def run_pytest(
        verbose: bool = False, with_coverage: bool = False, **kwargs
    ) -> Tuple[bool, str]:
        """
        Execute pytest using the standardized approach
        Returns (success, error_message)
        """
        if with_coverage:
            subkey = "pytest_with_coverage"
        elif verbose:
            subkey = "pytest_verbose"
        else:
            subkey = "pytest"

        return PlatformService.run_command_with_result(
            "TEST_COMMANDS", subkey=subkey, **kwargs
        )

    @staticmethod
    def check_docker_available() -> Tuple[bool, str]:
        """
        Check if Docker is available on the system using command keys
        Returns (available, error_message)
        """
        return PlatformService.run_command_with_result(
            "DOCKER_COMMANDS", subkey="version", capture_output=True, check=True
        )

    @staticmethod
    def run_docker_command(docker_cmd_key: str, **kwargs) -> Tuple[bool, str]:
        """
        Execute a docker command using the standardized approach
        Args:
            docker_cmd_key: Subkey within DOCKER_COMMANDS (e.g., 'version', 'info', 'images')
            **kwargs: Additional arguments for command formatting and subprocess
        Returns (success, error_message)
        """
        return PlatformService.run_command_with_result(
            "DOCKER_COMMANDS", subkey=docker_cmd_key, **kwargs
        )

    # ========== FILE SYSTEM OPERATIONS ==========

    @staticmethod
    def check_file_exists(file_path: str, **kwargs) -> Tuple[bool, str]:
        """
        Check if a file exists using platform-specific commands
        Returns (exists, error_message)
        """
        return PlatformService.run_command_with_result(
            "FILE_SYSTEM_COMMANDS",
            subkey="check_file_exists",
            file_path=file_path,
            capture_output=True,
            text=True,
            **kwargs,
        )

    @staticmethod
    def check_dir_exists(dir_path: str, **kwargs) -> Tuple[bool, str]:
        """
        Check if a directory exists using platform-specific commands
        Returns (exists, error_message)
        """
        return PlatformService.run_command_with_result(
            "FILE_SYSTEM_COMMANDS",
            subkey="check_dir_exists",
            dir_path=dir_path,
            capture_output=True,
            text=True,
            **kwargs,
        )

    @staticmethod
    def copy_file(
        source_path: str, target_path: str, preserve_attrs: bool = False, **kwargs
    ) -> Tuple[bool, str]:
        """
        Copy a file using platform-specific commands
        Args:
            source_path: Source file path
            target_path: Target file path
            preserve_attrs: Whether to preserve file attributes/timestamps
        Returns (success, error_message)
        """
        subkey = "copy_file_preserve" if preserve_attrs else "copy_file"

        if not preserve_attrs or not PlatformService.is_windows():
            return PlatformService.run_command_with_result(
                "FILE_SYSTEM_COMMANDS",
                subkey=subkey,
                source_path=source_path,
                target_path=target_path,
                capture_output=True,
                text=True,
                **kwargs,
            )
        # For Windows robocopy, we need to extract directory and filename
        from pathlib import Path

        source_path_obj = Path(source_path)
        target_path_obj = Path(target_path)

        return PlatformService.run_command_with_result(
            "FILE_SYSTEM_COMMANDS",
            subkey=subkey,
            source_dir=str(source_path_obj.parent),
            target_dir=str(target_path_obj.parent),
            file_name=source_path_obj.name,
            capture_output=True,
            text=True,
            **kwargs,
        )

    @staticmethod
    def create_directory(dir_path: str, **kwargs) -> Tuple[bool, str]:
        """
        Create a directory using platform-specific commands
        Returns (success, error_message)
        """
        return PlatformService.run_command_with_result(
            "FILE_SYSTEM_COMMANDS",
            subkey="create_dir",
            dir_path=dir_path,
            capture_output=True,
            text=True,
            **kwargs,
        )

    @staticmethod
    def get_file_stat(file_path: str, **kwargs) -> Tuple[bool, str]:
        """
        Get file statistics using platform-specific commands
        Returns (success, stat_output)
        """
        from pathlib import Path

        file_path_obj = Path(file_path)

        return PlatformService.run_command_with_result(
            "FILE_SYSTEM_COMMANDS",
            subkey="get_file_stat",
            file_path=file_path,
            dir_path=str(file_path_obj.parent),
            file_name=file_path_obj.name,
            capture_output=True,
            text=True,
            **kwargs,
        )

    # ========== ASYNC FILE SYSTEM OPERATIONS ==========

    @staticmethod
    async def check_file_exists_async(file_path: str, **kwargs) -> Tuple[bool, str]:
        """
        Async version of check_file_exists
        """
        return await PlatformService.run_command_with_result_async(
            "FILE_SYSTEM_COMMANDS",
            subkey="check_file_exists",
            file_path=file_path,
            capture_output=True,
            text=True,
            **kwargs,
        )

    @staticmethod
    async def check_dir_exists_async(dir_path: str, **kwargs) -> Tuple[bool, str]:
        """
        Async version of check_dir_exists
        """
        return await PlatformService.run_command_with_result_async(
            "FILE_SYSTEM_COMMANDS",
            subkey="check_dir_exists",
            dir_path=dir_path,
            capture_output=True,
            text=True,
            **kwargs,
        )

    @staticmethod
    async def copy_file_async(
        source_path: str, target_path: str, preserve_attrs: bool = False, **kwargs
    ) -> Tuple[bool, str]:
        """
        Async version of copy_file
        """
        if not ASYNC_AVAILABLE:
            raise RuntimeError("Async utilities not available")

        subkey = "copy_file_preserve" if preserve_attrs else "copy_file"

        if not preserve_attrs or not PlatformService.is_windows():
            return await PlatformService.run_command_with_result_async(
                "FILE_SYSTEM_COMMANDS",
                subkey=subkey,
                source_path=source_path,
                target_path=target_path,
                capture_output=True,
                text=True,
                **kwargs,
            )
        # For Windows robocopy, we need to extract directory and filename
        from pathlib import Path

        source_path_obj = Path(source_path)
        target_path_obj = Path(target_path)

        return await PlatformService.run_command_with_result_async(
            "FILE_SYSTEM_COMMANDS",
            subkey=subkey,
            source_dir=str(source_path_obj.parent),
            target_dir=str(target_path_obj.parent),
            file_name=source_path_obj.name,
            capture_output=True,
            text=True,
            **kwargs,
        )

    @staticmethod
    async def create_directory_async(dir_path: str, **kwargs) -> Tuple[bool, str]:
        """
        Async version of create_directory
        """
        return await PlatformService.run_command_with_result_async(
            "FILE_SYSTEM_COMMANDS",
            subkey="create_dir",
            dir_path=dir_path,
            capture_output=True,
            text=True,
            **kwargs,
        )

    @staticmethod
    async def get_file_stat_async(file_path: str, **kwargs) -> Tuple[bool, str]:
        """
        Async version of get_file_stat
        """
        from pathlib import Path

        file_path_obj = Path(file_path)

        return await PlatformService.run_command_with_result_async(
            "FILE_SYSTEM_COMMANDS",
            subkey="get_file_stat",
            file_path=file_path,
            dir_path=str(file_path_obj.parent),
            file_name=file_path_obj.name,
            capture_output=True,
            text=True,
            **kwargs,
        )
