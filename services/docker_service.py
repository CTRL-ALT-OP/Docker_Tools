"""
Docker Service - Standardized Async Version
"""

from pathlib import Path
from typing import Callable, Dict, Any

from services.platform_service import PlatformService
from config.commands import DOCKER_COMMANDS
from utils.async_base import (
    AsyncServiceInterface,
    ServiceResult,
    ProcessError,
    ValidationError,
    AsyncServiceContext,
)
from utils.async_utils import (
    run_subprocess_async,
    run_subprocess_streaming_async,
    run_in_executor,
)


class DockerService(AsyncServiceInterface):
    """Standardized Docker service with consistent async interface"""

    def __init__(self):
        super().__init__("DockerService")
        self.platform_service = PlatformService()

    async def health_check(self) -> ServiceResult[Dict[str, Any]]:
        """Check Docker service health"""
        async with self.operation_context("health_check", timeout=10.0) as ctx:
            try:
                # Check if Docker is available
                result = await run_subprocess_async(
                    ["docker", "--version"], capture_output=True, timeout=5.0
                )

                if result.returncode == 0:
                    return ServiceResult.success(
                        {
                            "status": "healthy",
                            "docker_version": result.stdout.strip(),
                            "platform": self.platform_service.get_platform(),
                        }
                    )
                error = ProcessError(
                    "Docker is not available",
                    return_code=result.returncode,
                    stderr=result.stderr,
                )
                return ServiceResult.error(error)

            except Exception as e:
                error = ProcessError(f"Failed to check Docker availability: {str(e)}")
                return ServiceResult.error(error)

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
                # Prepare build command
                build_cmd = DOCKER_COMMANDS["build_script"].format(tag=docker_tag)
                cmd_list, cmd_display = await run_in_executor(
                    self.platform_service.create_bash_command, build_cmd
                )

                if progress_callback:
                    progress_callback(f"=== DOCKER BUILD ===\n")
                    progress_callback(f"Command: {cmd_display}\n\n")

                # Stream build output
                use_shell = isinstance(cmd_list[0], str) and "bash -c" in cmd_list[0]
                cmd_to_run = cmd_list[0] if use_shell else cmd_list

                return_code, build_output = await run_subprocess_streaming_async(
                    cmd_to_run,
                    shell=use_shell,
                    cwd=str(project_path),
                    output_callback=progress_callback,
                )

                if return_code == 0:
                    if status_callback:
                        status_callback("Build Successful", "#27ae60")

                    return ServiceResult.success(
                        docker_tag,
                        message="Docker image built successfully",
                        metadata={
                            "build_output": build_output,
                            "project_path": str(project_path),
                            "command": cmd_display,
                        },
                    )
                else:
                    if status_callback:
                        status_callback("Build Failed", "#e74c3c")

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
                    status_callback("Running Tests...", "#3498db")

                if progress_callback:
                    progress_callback(f"\n=== DOCKER TEST ===\n")

                test_cmd = DOCKER_COMMANDS["run_tests"].format(tag=docker_tag)

                if progress_callback:
                    progress_callback(f"Command: {test_cmd}\n\n")

                # Use streaming subprocess for real-time output
                return_code, test_output = await run_subprocess_streaming_async(
                    test_cmd,
                    shell=True,
                    cwd=str(project_path),
                    output_callback=progress_callback,
                )

                # Analyze test results
                test_status = self._analyze_test_results(test_output, "", return_code)

                # Determine status color
                final_color = (
                    "#27ae60"
                    if "COMPLETED" in test_status and "Failed" not in test_status
                    else "#e74c3c"
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
