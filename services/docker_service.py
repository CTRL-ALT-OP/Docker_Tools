"""
Service for Docker operations
"""

import os
import subprocess
import time
from pathlib import Path
from typing import Callable, Optional, Tuple

from services.platform_service import PlatformService
from config.commands import DOCKER_COMMANDS


class DockerService:
    """Service for Docker operations"""

    def __init__(self):
        self.platform_service = PlatformService()

    def analyze_test_results(self, stdout: str, stderr: str, return_code: int) -> str:
        """Analyze pytest output to determine actual test status"""
        output_text = (stdout + stderr).lower()

        if any(
            indicator in output_text
            for indicator in [
                "collected",
                "passed",
                "failed",
                "error",
                "::test_",
                "pytest",
            ]
        ):
            if "failed" in output_text and "passed" in output_text:
                return "COMPLETED (Some Tests Failed)"
            elif "failed" in output_text and "passed" not in output_text:
                return "COMPLETED (All Tests Failed)"
            elif "passed" in output_text and "failed" not in output_text:
                return "COMPLETED (All Tests Passed)"
            elif return_code == 0:
                return "COMPLETED (Success)"
            else:
                return "COMPLETED (With Issues)"
        else:
            if return_code != 0:
                return "FAILED TO RUN"
            else:
                return "COMPLETED (No Output)"

    def build_docker_image(
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
            # Change to project directory
            original_cwd = os.getcwd()
            os.chdir(project_path)

            try:
                # Step 1: Build Docker image with real-time output
                build_cmd = DOCKER_COMMANDS["build_script"].format(tag=docker_tag)

                # Get platform-specific bash command
                cmd_list, cmd_display = self.platform_service.create_bash_command(
                    build_cmd
                )

                # Determine if we need shell execution
                use_shell = isinstance(cmd_list[0], str) and "bash -c" in cmd_list[0]

                if use_shell:
                    build_process = subprocess.Popen(
                        cmd_list[0],
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        cwd=project_path,
                        bufsize=1,
                        universal_newlines=True,
                    )
                else:
                    build_process = subprocess.Popen(
                        cmd_list,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        cwd=project_path,
                        bufsize=1,
                        universal_newlines=True,
                    )

                output_callback(f"=== DOCKER BUILD ===\n")
                output_callback(f"Command: {cmd_display}\n\n")

                # Stream build output in real-time
                build_output = ""
                while True:
                    output = build_process.stdout.readline()
                    if output == "" and build_process.poll() is not None:
                        break
                    if output:
                        build_output += output
                        output_callback(output)

                build_return_code = build_process.wait()

                if build_return_code != 0:
                    status_callback("Build Failed", "#e74c3c")
                    error_msg = f"\nBuild failed with exit code: {build_return_code}\n"
                    output_callback(error_msg)

                    # Use centralized error message
                    error_message = self.platform_service.get_error_message(
                        "bash_not_found"
                    )
                    output_callback(f"{error_message}\n")

                    return False, f"Build failed with exit code: {build_return_code}"

                return True, ""

            finally:
                os.chdir(original_cwd)

        except Exception as e:
            return False, f"Error during Docker build: {str(e)}"

    def run_docker_tests(
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
            # Change to project directory
            original_cwd = os.getcwd()
            os.chdir(project_path)

            try:
                # Step 2: Run tests in container
                status_callback("Running Tests...", "#3498db")
                output_callback(f"\n=== DOCKER TEST ===\n")

                test_cmd = DOCKER_COMMANDS["run_tests"].format(tag=docker_tag)
                output_callback(f"Command: {test_cmd}\n\n")

                test_result = subprocess.run(
                    test_cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    cwd=project_path,
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
                    output_callback(f"\nTest Errors/Warnings:\n{test_result.stderr}\n")

                return True, raw_test_output, test_status

            finally:
                os.chdir(original_cwd)

        except Exception as e:
            error_msg = f"Error during Docker test: {str(e)}"
            status_callback("Test Failed", "#e74c3c")
            output_callback(f"\n{error_msg}\n")
            return False, "", f"FAILED: {str(e)}"

    def build_and_test(
        self,
        project_path: Path,
        docker_tag: str,
        output_callback: Callable[[str], None],
        status_callback: Callable[[str, str], None],
    ) -> Tuple[bool, Optional[str]]:
        """
        Complete Docker build and test workflow
        Returns (success, raw_test_output)
        """
        # Build Docker image
        build_success, build_error = self.build_docker_image(
            project_path, docker_tag, output_callback, status_callback
        )

        if not build_success:
            return False, None

        # Run tests
        test_success, raw_test_output, test_status = self.run_docker_tests(
            project_path, docker_tag, output_callback, status_callback
        )

        return test_success, raw_test_output if test_success else None
