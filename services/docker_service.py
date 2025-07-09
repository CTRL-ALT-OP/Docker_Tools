"""
Docker Service - Standardized Async Version
"""

from pathlib import Path
from typing import Callable, Dict, Any

from services.platform_service import PlatformService
from utils.async_base import (
    AsyncServiceInterface,
    ServiceResult,
    ProcessError,
    ValidationError,
    AsyncServiceContext,
)
from utils.async_utils import (
    run_in_executor,
)
from config.settings import COLORS


class DockerService(AsyncServiceInterface):
    """Standardized Docker service with consistent async interface"""

    def __init__(self):
        super().__init__("DockerService")
        self.platform_service = PlatformService()

    async def health_check(self) -> ServiceResult[Dict[str, Any]]:
        """Check Docker service health"""
        async with self.operation_context("health_check", timeout=10.0) as ctx:
            try:
                # Check if Docker is available using new async method
                success, result_output = (
                    await PlatformService.run_command_with_result_async(
                        "DOCKER_COMMANDS",
                        subkey="version",
                        capture_output=True,
                        text=True,
                        timeout=5.0,
                    )
                )

                if success:
                    return ServiceResult.success(
                        {
                            "status": "healthy",
                            "docker_version": result_output,
                            "platform": self.platform_service.get_platform(),
                        }
                    )
                error = ProcessError(
                    f"Docker is not available: {result_output}",
                    error_code="DOCKER_NOT_AVAILABLE",
                )
                return ServiceResult.error(error)

            except Exception as e:
                error = ProcessError(f"Failed to check Docker availability: {str(e)}")
                return ServiceResult.error(error)

    async def _validate_shell_script_shebang(self, script_path: Path) -> bool:
        """
        Validate and fix shebang line in shell script
        Returns True if successful, False otherwise
        """
        try:
            content = script_path.read_text(encoding="utf-8")
            lines = content.split("\n")

            # Check if first line is a valid shebang
            if lines and lines[0].startswith("#!"):
                # Already has shebang, validate it's appropriate
                shebang = lines[0].strip()
                if shebang not in [
                    "#!/bin/sh",
                    "#!/bin/bash",
                    "#!/usr/bin/env bash",
                ]:
                    # Fix shebang to use /bin/sh for maximum compatibility
                    lines[0] = "#!/bin/sh"
                    fixed_content = "\n".join(lines)
                    script_path.write_text(
                        fixed_content, encoding="utf-8", newline="\n"
                    )
            else:
                # No shebang, add one
                fixed_content = "#!/bin/sh\n" + content
                script_path.write_text(fixed_content, encoding="utf-8", newline="\n")
            return True
        except Exception as e:
            self.logger.warning(
                f"Failed to validate shebang in {script_path}: {str(e)}"
            )
            return False

    async def _normalize_shell_script(self, script_path: Path) -> bool:
        """
        Normalize line endings in shell script to Unix format (LF)
        Returns True if successful, False otherwise
        """
        try:
            # Read the file content
            content = script_path.read_text(encoding="utf-8")

            # Convert Windows line endings (CRLF) to Unix line endings (LF)
            normalized_content = content.replace("\r\n", "\n").replace("\r", "\n")

            # Write back with Unix line endings
            script_path.write_text(normalized_content, encoding="utf-8", newline="\n")

            return True
        except Exception as e:
            self.logger.warning(
                f"Failed to normalize line endings in {script_path}: {str(e)}"
            )
            return False

    async def build_docker_image(
        self,
        project_path: Path,
        docker_tag: str,
        progress_callback: Callable[[str], None] = None,
        status_callback: Callable[[str, str], None] = None,
    ) -> ServiceResult[str]:
        """
        Build Docker image with standardized result format
        """
        # Validate inputs
        if not project_path.exists():
            error = ValidationError(f"Project path does not exist: {project_path}")
            return ServiceResult.error(error)

        if not docker_tag:
            error = ValidationError("Docker tag cannot be empty")
            return ServiceResult.error(error)

        async with self.operation_context("build_docker_image", timeout=300.0) as ctx:
            try:
                if progress_callback:
                    progress_callback(f"=== DOCKER BUILD ===\n")

                # Check if build_docker.sh exists and fix permissions if needed
                build_script_path = project_path / "build_docker.sh"
                if not build_script_path.exists():
                    error = ValidationError(
                        f"build_docker.sh not found in {project_path}"
                    )
                    return ServiceResult.error(error)

                # Also check if run_tests.sh exists and fix it
                run_tests_path = project_path / "run_tests.sh"
                if not run_tests_path.exists():
                    error = ValidationError(f"run_tests.sh not found in {project_path}")
                    return ServiceResult.error(error)

                # Validate and fix shebang line for build_docker.sh
                if progress_callback:
                    progress_callback(f"Validating shebang in {build_script_path}...\n")

                shebang_success = await self._validate_shell_script_shebang(
                    build_script_path
                )
                if not shebang_success and progress_callback:
                    progress_callback(f"Warning: Failed to validate shebang line\n")

                # Validate and fix shebang line for run_tests.sh
                if progress_callback:
                    progress_callback(f"Validating shebang in {run_tests_path}...\n")

                shebang_success = await self._validate_shell_script_shebang(
                    run_tests_path
                )
                if not shebang_success and progress_callback:
                    progress_callback(
                        f"Warning: Failed to validate run_tests.sh shebang line\n"
                    )

                # Normalize line endings to Unix format for build_docker.sh
                if progress_callback:
                    progress_callback(
                        f"Normalizing line endings in {build_script_path}...\n"
                    )

                normalize_success = await self._normalize_shell_script(
                    build_script_path
                )
                if not normalize_success and progress_callback:
                    progress_callback(f"Warning: Failed to normalize line endings\n")

                # Normalize line endings to Unix format for run_tests.sh
                if progress_callback:
                    progress_callback(
                        f"Normalizing line endings in {run_tests_path}...\n"
                    )

                normalize_success = await self._normalize_shell_script(run_tests_path)
                if not normalize_success and progress_callback:
                    progress_callback(
                        f"Warning: Failed to normalize run_tests.sh line endings\n"
                    )

                # Ensure the build script has execute permissions
                if progress_callback:
                    progress_callback(
                        f"Setting execute permissions for {build_script_path}...\n"
                    )

                success, error_msg = (
                    await PlatformService.run_command_with_result_async(
                        "FILE_PERMISSION_COMMANDS",
                        subkey="make_executable",
                        file_path=str(build_script_path),
                        capture_output=True,
                        text=True,
                    )
                )

                if not success and progress_callback:
                    progress_callback(
                        f"Warning: Failed to set execute permissions: {error_msg}\n"
                    )

                # Ensure the run_tests.sh script has execute permissions
                if progress_callback:
                    progress_callback(
                        f"Setting execute permissions for {run_tests_path}...\n"
                    )

                success, error_msg = (
                    await PlatformService.run_command_with_result_async(
                        "FILE_PERMISSION_COMMANDS",
                        subkey="make_executable",
                        file_path=str(run_tests_path),
                        capture_output=True,
                        text=True,
                    )
                )

                if not success and progress_callback:
                    progress_callback(
                        f"Warning: Failed to set run_tests.sh execute permissions: {error_msg}\n"
                    )

                # Use bash command execution for the build script
                build_cmd = f"./build_docker.sh {docker_tag}"

                if progress_callback:
                    progress_callback(f"Command: {build_cmd}\n\n")

                # Stream build output using new async method
                return_code, build_output = (
                    await PlatformService.run_command_streaming_async(
                        "SHELL_COMMANDS",
                        subkey="bash_execute",
                        command=build_cmd,
                        cwd=str(project_path),
                        output_callback=progress_callback,
                    )
                )

                if return_code == 0:
                    if status_callback:
                        status_callback("Build Successful", COLORS["success"])

                    return ServiceResult.success(
                        docker_tag,
                        message="Docker image built successfully",
                        metadata={
                            "build_output": build_output,
                            "project_path": str(project_path),
                            "command": build_cmd,
                        },
                    )
                else:
                    if status_callback:
                        status_callback("Build Failed", COLORS["error"])

                    error_msg = await run_in_executor(
                        self.platform_service.get_error_message, "bash_not_found"
                    )

                    error = ProcessError(
                        f"Docker build failed: {error_msg}",
                        return_code=return_code,
                        stdout=build_output,
                        error_code="BUILD_FAILED",
                    )
                    return ServiceResult.error(error)

            except Exception as e:
                self.logger.exception("Unexpected error during Docker build")
                error = ProcessError(f"Docker build error: {str(e)}")
                return ServiceResult.error(error)

    async def run_docker_tests(
        self,
        project_path: Path,
        docker_tag: str,
        progress_callback: Callable[[str], None] = None,
        status_callback: Callable[[str, str], None] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Run tests in Docker container with standardized result format
        """
        # Validate inputs
        if not project_path.exists():
            error = ValidationError(f"Project path does not exist: {project_path}")
            return ServiceResult.error(error)

        async with self.operation_context("run_docker_tests", timeout=300.0) as ctx:
            try:
                if status_callback:
                    status_callback("Running Tests...", COLORS["info"])

                if progress_callback:
                    progress_callback(f"\n=== DOCKER TEST ===\n")

                # Use bash command execution for the test command
                test_cmd = f"docker run --rm {docker_tag} ./run_tests.sh"

                if progress_callback:
                    progress_callback(f"Command: {test_cmd}\n\n")

                # Use streaming subprocess for real-time output
                return_code, test_output = (
                    await PlatformService.run_command_streaming_async(
                        "SHELL_COMMANDS",
                        subkey="bash_execute",
                        command=test_cmd,
                        cwd=str(project_path),
                        output_callback=progress_callback,
                    )
                )

                # Analyze test results
                test_status = self._analyze_test_results(test_output, "", return_code)

                # Determine status color
                final_color = (
                    COLORS["success"]
                    if "COMPLETED" in test_status and "Failed" not in test_status
                    else COLORS["error"]
                )

                if status_callback:
                    status_callback(test_status, final_color)

                if progress_callback:
                    progress_callback(f"\nTest Status: {test_status}\n")
                    progress_callback(f"Exit Code: {return_code}\n")

                test_data = {
                    "status": test_status,
                    "return_code": return_code,
                    "raw_output": test_output,
                    "stdout": test_output,
                    "stderr": "",
                }

                if return_code == 0:
                    return ServiceResult.success(
                        test_data,
                        message=f"Tests completed: {test_status}",
                        metadata={
                            "docker_tag": docker_tag,
                            "project_path": str(project_path),
                        },
                    )
                # Partial success - tests ran but some failed
                error = ProcessError(
                    f"Tests failed: {test_status}",
                    return_code=return_code,
                    stdout=test_output,
                    stderr="",
                )
                return ServiceResult.partial(test_data, error)

            except Exception as e:
                self.logger.exception("Unexpected error during test execution")
                error = ProcessError(f"Test execution error: {str(e)}")
                return ServiceResult.error(error)

    async def build_and_test(
        self,
        project_path: Path,
        docker_tag: str,
        progress_callback: Callable[[str], None] = None,
        status_callback: Callable[[str, str], None] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Build Docker image and run tests with standardized result format
        """
        async with self.operation_context("build_and_test", timeout=600.0) as ctx:
            try:
                # Step 1: Build Docker image
                build_result = await self.build_docker_image(
                    project_path, docker_tag, progress_callback, status_callback
                )

                if build_result.is_error:
                    return ServiceResult.error(build_result.error)

                # Step 2: Run tests
                test_result = await self.run_docker_tests(
                    project_path, docker_tag, progress_callback, status_callback
                )

                # Combine results
                combined_data = {
                    "build_data": build_result.data,
                    "test_data": test_result.data or {},
                    "docker_tag": docker_tag,
                    "project_path": str(project_path),
                }

                if test_result.is_success:
                    return ServiceResult.success(
                        combined_data, message="Build and test completed successfully"
                    )
                elif test_result.is_partial:
                    return ServiceResult.partial(
                        combined_data,
                        test_result.error,
                        message="Build successful, but some tests failed",
                    )
                else:
                    return ServiceResult.error(
                        test_result.error, metadata={"build_data": build_result.data}
                    )

            except Exception as e:
                self.logger.exception("Unexpected error during build and test")
                error = ProcessError(f"Build and test error: {str(e)}")
                return ServiceResult.error(error)

    def _analyze_test_results(self, stdout: str, stderr: str, return_code: int) -> str:
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

        # Check for specific patterns first
        if "passed" in output_text and "failed" in output_text:
            # Look for patterns like "X failed" or "0 failed"
            import re

            failed_match = re.search(r"(\d+)\s+failed", output_text)
            if failed_match and int(failed_match.group(1)) == 0:
                return "COMPLETED (All Tests Passed)"
            else:
                return "COMPLETED (Some Tests Failed)"
        elif "failed" in output_text:
            return "COMPLETED (All Tests Failed)"
        elif "passed" in output_text:
            return "COMPLETED (All Tests Passed)"
        elif return_code == 0:
            return "COMPLETED (Success)"
        else:
            return "COMPLETED (With Issues)"
