"""
Service for Docker operations - Async version
"""

import os
from pathlib import Path
from typing import Callable, Optional, Tuple

from services.platform_service import PlatformService
from config.commands import DOCKER_COMMANDS
from utils.async_utils import (
    run_subprocess_async,
    run_subprocess_streaming_async,
    run_in_executor,
)


class DockerService:
    """Service for Docker operations - Async version"""

    def __init__(self):
        self.platform_service = PlatformService()

    def analyze_test_results(self, stdout: str, stderr: str, return_code: int) -> str:
        """Analyze pytest output to determine actual test status"""
        output_text = (stdout + stderr).lower()

        if all(
            indicator not in output_text
            for indicator in [
                "collected",
                "passed",
                "failed",
                "error",
                "::test_",
                "pytest",
            ]
        ):
            return "FAILED TO RUN" if return_code != 0 else "COMPLETED (No Output)"
        if "failed" in output_text and "passed" in output_text:
            return "COMPLETED (Some Tests Failed)"
        elif "failed" in output_text:
            return "COMPLETED (All Tests Failed)"
        elif "passed" in output_text:
            return "COMPLETED (All Tests Passed)"
        elif return_code == 0:
            return "COMPLETED (Success)"
        else:
            return "COMPLETED (With Issues)"

    async def build_docker_image(
        self,
        project_path: Path,
        docker_tag: str,
        output_callback: Callable[[str], None],
        status_callback: Callable[[str, str], None],
    ) -> Tuple[bool, str]:
        """
        Build Docker image with real-time output
        Returns (success, error_message)
        """
        try:
            # Step 1: Build Docker image with real-time output
            build_cmd = DOCKER_COMMANDS["build_script"].format(tag=docker_tag)

            # Get platform-specific bash command
            cmd_list, cmd_display = await run_in_executor(
                self.platform_service.create_bash_command, build_cmd
            )

            output_callback(f"=== DOCKER BUILD ===\n")
            output_callback(f"Command: {cmd_display}\n\n")

            # Determine if we need shell execution
            use_shell = isinstance(cmd_list[0], str) and "bash -c" in cmd_list[0]
            cmd_to_run = cmd_list[0] if use_shell else cmd_list

            # Stream build output in real-time
            return_code, build_output = await run_subprocess_streaming_async(
                cmd_to_run,
                shell=use_shell,
                cwd=str(project_path),
                output_callback=output_callback,
            )

            if return_code != 0:
                status_callback("Build Failed", "#e74c3c")
                error_msg = f"\nBuild failed with exit code: {return_code}\n"
                output_callback(error_msg)

                # Use centralized error message
                error_message = await run_in_executor(
                    self.platform_service.get_error_message, "bash_not_found"
                )
                output_callback(f"{error_message}\n")

                return False, f"Build failed with exit code: {return_code}"

            return True, ""

        except Exception as e:
            return False, f"Error during Docker build: {str(e)}"

    async def run_docker_tests(
        self,
        project_path: Path,
        docker_tag: str,
        output_callback: Callable[[str], None],
        status_callback: Callable[[str, str], None],
    ) -> Tuple[bool, str, str]:
        """
        Run tests in Docker container
        Returns (success, test_output, test_status)
        """
        try:
            # Step 2: Run tests in container
            status_callback("Running Tests...", "#3498db")
            output_callback(f"\n=== DOCKER TEST ===\n")

            test_cmd = DOCKER_COMMANDS["run_tests"].format(tag=docker_tag)
            output_callback(f"Command: {test_cmd}\n\n")

            test_result = await run_subprocess_async(
                test_cmd, shell=True, cwd=str(project_path)
            )

            # Prepare raw test output for copying
            raw_test_output = ""
            if test_result.stdout:
                raw_test_output += test_result.stdout
            if test_result.stderr:
                if raw_test_output:
                    raw_test_output += "\n"
                raw_test_output += test_result.stderr

            # Analyze test results
            test_status = self.analyze_test_results(
                test_result.stdout, test_result.stderr, test_result.returncode
            )

            # Update final status
            final_color = (
                "#27ae60"
                if "COMPLETED" in test_status and "Failed" not in test_status
                else "#e74c3c"
            )
            status_callback(test_status, final_color)

            # Add test output
            output_callback(f"Test Status: {test_status}\n")
            output_callback(f"Exit Code: {test_result.returncode}\n\n")

            if test_result.stdout:
                output_callback(f"Test Output:\n{test_result.stdout}\n")

            if test_result.stderr:
                output_callback(f"Test Errors:\n{test_result.stderr}\n")

            return True, raw_test_output, test_status

        except Exception as e:
            error_msg = f"Error during test execution: {str(e)}"
            status_callback("Test Error", "#e74c3c")
            output_callback(error_msg)
            return False, "", "ERROR"

    async def build_and_test(
        self,
        project_path: Path,
        docker_tag: str,
        output_callback: Callable[[str], None],
        status_callback: Callable[[str, str], None],
    ) -> Tuple[bool, Optional[str]]:
        """
        Build Docker image and run tests
        Returns (success, raw_test_output)
        """
        try:
            # Step 1: Build Docker image
            build_success, build_error = await self.build_docker_image(
                project_path, docker_tag, output_callback, status_callback
            )

            if not build_success:
                return False, None

            # Step 2: Run tests
            test_success, raw_test_output, test_status = await self.run_docker_tests(
                project_path, docker_tag, output_callback, status_callback
            )

            return test_success, raw_test_output

        except Exception as e:
            error_msg = f"Error during Docker build and test: {str(e)}"
            status_callback("Process Error", "#e74c3c")
            output_callback(error_msg)
            return False, None
