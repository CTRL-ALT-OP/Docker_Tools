"""
Tests for DockerService - Tests for Docker operations
"""

import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import pytest
import asyncio

# Add parent directory to path to import modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from services.docker_service import DockerService
from services.platform_service import PlatformService


class TestDockerService:
    """Test cases for DockerService"""

    def setup_method(self):
        """Set up test fixtures"""
        self.docker_service = DockerService()

    def test_analyze_test_results_no_test_output(self):
        """Test when output doesn't contain test indicators"""
        stdout = "Building docker image...\nDone."
        stderr = ""
        return_code = 0

        result = self.docker_service.analyze_test_results(stdout, stderr, return_code)
        assert result == "COMPLETED (No Output)"

        # With non-zero return code
        result = self.docker_service.analyze_test_results(stdout, stderr, 1)
        assert result == "FAILED TO RUN"

    def test_analyze_test_results_all_tests_passed(self):
        """Test when all tests pass"""
        stdout = """
        collected 5 items
        
        test_example.py::test_one PASSED
        test_example.py::test_two PASSED
        test_example.py::test_three PASSED
        
        ===== 3 passed in 0.5s =====
        """
        stderr = ""
        return_code = 0

        result = self.docker_service.analyze_test_results(stdout, stderr, return_code)
        assert result == "COMPLETED (All Tests Passed)"

    def test_analyze_test_results_some_tests_failed(self):
        """Test when some tests fail"""
        stdout = """
        collected 5 items
        
        test_example.py::test_one PASSED
        test_example.py::test_two FAILED
        test_example.py::test_three PASSED
        
        ===== 2 passed, 1 failed in 0.5s =====
        """
        stderr = ""
        return_code = 1

        result = self.docker_service.analyze_test_results(stdout, stderr, return_code)
        assert result == "COMPLETED (Some Tests Failed)"

    def test_analyze_test_results_all_tests_failed(self):
        """Test when all tests fail"""
        stdout = """
        collected 3 items
        
        test_example.py::test_one FAILED
        test_example.py::test_two FAILED
        test_example.py::test_three FAILED
        
        ===== 3 failed in 0.5s =====
        """
        stderr = ""
        return_code = 1

        result = self.docker_service.analyze_test_results(stdout, stderr, return_code)
        assert result == "COMPLETED (All Tests Failed)"

    def test_analyze_test_results_with_errors(self):
        """Test when tests have errors"""
        stdout = "collected 2 items"
        stderr = "ERROR collecting test_example.py"
        return_code = 1

        result = self.docker_service.analyze_test_results(stdout, stderr, return_code)
        assert result == "COMPLETED (With Issues)"

    def test_analyze_test_results_pytest_in_stderr(self):
        """Test when pytest output is in stderr"""
        stdout = ""
        stderr = """
        ============================= test session starts ==============================
        platform linux -- Python 3.8.0, pytest-6.2.0
        collected 5 items
        
        test_example.py .....                                                    [100%]
        
        ============================== 5 passed in 0.10s ===============================
        """
        return_code = 0

        result = self.docker_service.analyze_test_results(stdout, stderr, return_code)
        assert result == "COMPLETED (All Tests Passed)"

    def test_analyze_test_results_edge_cases(self):
        """Test edge cases in test result analysis"""
        # Empty output
        result = self.docker_service.analyze_test_results("", "", 0)
        assert result == "COMPLETED (No Output)"

        # Only "collected" keyword
        result = self.docker_service.analyze_test_results("collected 0 items", "", 0)
        assert result == "COMPLETED (Success)"

        # Mixed case
        result = self.docker_service.analyze_test_results("PASSED", "FAILED", 1)
        assert result == "COMPLETED (Some Tests Failed)"

    @pytest.mark.asyncio
    async def test_run_tests_async(self):
        """Test async test execution"""
        # Mock the async utilities
        with patch(
            "services.docker_service.run_subprocess_streaming_async"
        ) as mock_run:
            mock_run.return_value = (0, "stdout", "stderr")

            # Create a mock project
            project = Mock()
            project.path = Path("/test/path")
            project.name = "test_project"
            project.parent = "test_parent"

            # Mock callback
            callback = AsyncMock()

            # Test would call the actual run_tests_async method
            # This is a placeholder for the test structure

    @pytest.mark.asyncio
    async def test_build_and_test_async(self):
        """Test async build and test execution"""
        # Mock the async utilities
        with patch("services.docker_service.run_subprocess_async") as mock_run:
            mock_run.return_value = (0, "Build successful", "")

            # Create a mock project
            project = Mock()
            project.path = Path("/test/path")
            project.name = "test_project"
            project.parent = "test_parent"

            # Test would call the actual build_and_test_async method
            # This is a placeholder for the test structure

    def test_docker_service_initialization(self):
        """Test DockerService initialization"""
        service = DockerService()
        assert service.platform_service is not None
        assert isinstance(service.platform_service, PlatformService)

    def test_analyze_test_results_case_insensitive(self):
        """Test that analysis is case insensitive"""
        stdout = "COLLECTED 5 items\ntest.py::test_one PASSED"
        stderr = ""
        return_code = 0

        result = self.docker_service.analyze_test_results(stdout, stderr, return_code)
        assert result == "COMPLETED (All Tests Passed)"

    def test_analyze_test_results_with_warnings(self):
        """Test output with warnings"""
        stdout = """
        collected 3 items
        
        test_example.py::test_one PASSED
        test_example.py::test_two PASSED
        test_example.py::test_three PASSED
        
        ===== 3 passed, 2 warnings in 0.5s =====
        """
        stderr = ""
        return_code = 0

        result = self.docker_service.analyze_test_results(stdout, stderr, return_code)
        assert result == "COMPLETED (All Tests Passed)"

    @pytest.mark.asyncio
    async def test_build_docker_image_success(self):
        """Test successful Docker image build"""
        project_path = Path("/test/project")
        docker_tag = "test:latest"

        # Mock callbacks
        output_callback = Mock()
        status_callback = Mock()

        # Mock platform service and subprocess calls
        with patch("services.docker_service.run_in_executor") as mock_executor, patch(
            "services.docker_service.run_subprocess_streaming_async"
        ) as mock_streaming:

            # Mock platform service response
            mock_executor.return_value = (
                ["docker", "build", "-t", "test:latest", "."],
                "docker build -t test:latest .",
            )

            # Mock successful build
            mock_streaming.return_value = (0, "Build successful")

            success, error_msg = await self.docker_service.build_docker_image(
                project_path, docker_tag, output_callback, status_callback
            )

            assert success is True
            assert error_msg == ""
            output_callback.assert_called()

    @pytest.mark.asyncio
    async def test_build_docker_image_failure(self):
        """Test failed Docker image build"""
        project_path = Path("/test/project")
        docker_tag = "test:latest"

        # Mock callbacks
        output_callback = Mock()
        status_callback = Mock()

        # Mock platform service and subprocess calls
        with patch("services.docker_service.run_in_executor") as mock_executor, patch(
            "services.docker_service.run_subprocess_streaming_async"
        ) as mock_streaming:

            # Mock platform service response
            mock_executor.return_value = (
                ["docker", "build", "-t", "test:latest", "."],
                "docker build -t test:latest .",
            )

            # Mock failed build
            mock_streaming.return_value = (1, "Build failed")

            success, error_msg = await self.docker_service.build_docker_image(
                project_path, docker_tag, output_callback, status_callback
            )

            assert success is False
            assert "Build failed with exit code: 1" in error_msg
            status_callback.assert_called_with("Build Failed", "#e74c3c")

    @pytest.mark.asyncio
    async def test_build_docker_image_exception(self):
        """Test Docker image build with exception"""
        project_path = Path("/test/project")
        docker_tag = "test:latest"

        # Mock callbacks
        output_callback = Mock()
        status_callback = Mock()

        # Mock platform service to raise exception
        with patch(
            "services.docker_service.run_in_executor",
            side_effect=Exception("Platform error"),
        ):
            success, error_msg = await self.docker_service.build_docker_image(
                project_path, docker_tag, output_callback, status_callback
            )

            assert success is False
            assert "Error during Docker build" in error_msg

    @pytest.mark.asyncio
    async def test_run_docker_tests_success(self):
        """Test successful Docker test execution"""
        project_path = Path("/test/project")
        docker_tag = "test:latest"

        # Mock callbacks
        output_callback = Mock()
        status_callback = Mock()

        # Mock successful test output
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = (
            "collected 5 items\ntest.py::test_one PASSED\n===== 5 passed in 0.5s ====="
        )
        mock_result.stderr = ""

        with patch(
            "services.docker_service.run_subprocess_async", return_value=mock_result
        ):
            success, raw_output, test_status = (
                await self.docker_service.run_docker_tests(
                    project_path, docker_tag, output_callback, status_callback
                )
            )

            assert success is True
            assert "5 passed" in raw_output
            assert "COMPLETED" in test_status

    @pytest.mark.asyncio
    async def test_run_docker_tests_with_failures(self):
        """Test Docker test execution with test failures"""
        project_path = Path("/test/project")
        docker_tag = "test:latest"

        # Mock callbacks
        output_callback = Mock()
        status_callback = Mock()

        # Mock test output with failures
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = "collected 3 items\ntest.py::test_one PASSED\ntest.py::test_two FAILED\n===== 1 passed, 1 failed in 0.5s ====="
        mock_result.stderr = ""

        with patch(
            "services.docker_service.run_subprocess_async", return_value=mock_result
        ):
            success, raw_output, test_status = (
                await self.docker_service.run_docker_tests(
                    project_path, docker_tag, output_callback, status_callback
                )
            )

            assert success is True
            assert "1 failed" in raw_output
            assert "Some Tests Failed" in test_status

    @pytest.mark.asyncio
    async def test_run_docker_tests_exception(self):
        """Test Docker test execution with exception"""
        project_path = Path("/test/project")
        docker_tag = "test:latest"

        # Mock callbacks
        output_callback = Mock()
        status_callback = Mock()

        with patch(
            "services.docker_service.run_subprocess_async",
            side_effect=Exception("Docker error"),
        ):
            success, raw_output, test_status = (
                await self.docker_service.run_docker_tests(
                    project_path, docker_tag, output_callback, status_callback
                )
            )

            assert success is False
            assert raw_output == ""
            assert test_status == "ERROR"
            status_callback.assert_called_with("Test Error", "#e74c3c")

    @pytest.mark.asyncio
    async def test_run_docker_tests_with_stderr(self):
        """Test Docker test execution with stderr output"""
        project_path = Path("/test/project")
        docker_tag = "test:latest"

        # Mock callbacks
        output_callback = Mock()
        status_callback = Mock()

        # Mock test output with stderr
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "collected 2 items\n===== 2 passed in 0.3s ====="
        mock_result.stderr = "WARNING: deprecated feature used"

        with patch(
            "services.docker_service.run_subprocess_async", return_value=mock_result
        ):
            success, raw_output, test_status = (
                await self.docker_service.run_docker_tests(
                    project_path, docker_tag, output_callback, status_callback
                )
            )

            assert success is True
            assert "2 passed" in raw_output
            assert "WARNING" in raw_output

    @pytest.mark.asyncio
    async def test_build_and_test_success(self):
        """Test successful build and test workflow"""
        project_path = Path("/test/project")
        docker_tag = "test:latest"

        # Mock callbacks
        output_callback = Mock()
        status_callback = Mock()

        # Mock successful build
        with patch.object(
            self.docker_service, "build_docker_image", return_value=(True, "")
        ) as mock_build, patch.object(
            self.docker_service,
            "run_docker_tests",
            return_value=(True, "test output", "COMPLETED"),
        ) as mock_test:

            success, raw_output = await self.docker_service.build_and_test(
                project_path, docker_tag, output_callback, status_callback
            )

            assert success is True
            assert raw_output == "test output"
            mock_build.assert_called_once()
            mock_test.assert_called_once()

    @pytest.mark.asyncio
    async def test_build_and_test_build_failure(self):
        """Test build and test workflow with build failure"""
        project_path = Path("/test/project")
        docker_tag = "test:latest"

        # Mock callbacks
        output_callback = Mock()
        status_callback = Mock()

        # Mock failed build
        with patch.object(
            self.docker_service,
            "build_docker_image",
            return_value=(False, "Build failed"),
        ) as mock_build:
            success, raw_output = await self.docker_service.build_and_test(
                project_path, docker_tag, output_callback, status_callback
            )

            assert success is False
            assert raw_output is None
            mock_build.assert_called_once()

    @pytest.mark.asyncio
    async def test_build_and_test_test_failure(self):
        """Test build and test workflow with test failure"""
        project_path = Path("/test/project")
        docker_tag = "test:latest"

        # Mock callbacks
        output_callback = Mock()
        status_callback = Mock()

        # Mock successful build but failed tests
        with patch.object(
            self.docker_service, "build_docker_image", return_value=(True, "")
        ) as mock_build, patch.object(
            self.docker_service,
            "run_docker_tests",
            return_value=(False, "test errors", "ERROR"),
        ) as mock_test:

            success, raw_output = await self.docker_service.build_and_test(
                project_path, docker_tag, output_callback, status_callback
            )

            assert success is False
            assert raw_output == "test errors"
            mock_build.assert_called_once()
            mock_test.assert_called_once()

    @pytest.mark.asyncio
    async def test_build_and_test_exception(self):
        """Test build and test workflow with exception"""
        project_path = Path("/test/project")
        docker_tag = "test:latest"

        # Mock callbacks
        output_callback = Mock()
        status_callback = Mock()

        # Mock build to raise exception
        with patch.object(
            self.docker_service,
            "build_docker_image",
            side_effect=Exception("Unexpected error"),
        ):
            success, raw_output = await self.docker_service.build_and_test(
                project_path, docker_tag, output_callback, status_callback
            )

            assert success is False
            assert raw_output is None
            status_callback.assert_called_with("Process Error", "#e74c3c")

    def test_analyze_test_results_complex_scenarios(self):
        """Test analyzing various complex test result scenarios"""
        # Test with collection but no tests run
        result = self.docker_service.analyze_test_results("collected 0 items", "", 0)
        assert result == "COMPLETED (Success)"

        # Test with multiple test files
        stdout = """
        collected 10 items
        
        test_module1.py::test_a PASSED
        test_module1.py::test_b FAILED
        test_module2.py::test_c PASSED
        test_module2.py::test_d PASSED
        
        ===== 3 passed, 1 failed in 1.2s =====
        """
        result = self.docker_service.analyze_test_results(stdout, "", 1)
        assert result == "COMPLETED (Some Tests Failed)"

        # Test with errors during collection
        stderr = "ERROR: failed to import test_module.py"
        result = self.docker_service.analyze_test_results("", stderr, 1)
        assert result == "COMPLETED (All Tests Failed)"

    def test_analyze_test_results_edge_cases_extended(self):
        """Test additional edge cases in test result analysis"""
        # Test with only "error" keyword
        result = self.docker_service.analyze_test_results("", "ERROR in setup", 1)
        assert result == "COMPLETED (With Issues)"

        # Test with mixed success and failure indicators
        stdout = "Some tests PASSED but others FAILED"
        result = self.docker_service.analyze_test_results(stdout, "", 1)
        assert result == "COMPLETED (Some Tests Failed)"

        # Test with pytest version info
        stderr = (
            "pytest 6.2.0 -- /usr/bin/python3\ncollected 5 items\n===== 5 passed ====="
        )
        result = self.docker_service.analyze_test_results("", stderr, 0)
        assert result == "COMPLETED (All Tests Passed)"

    @pytest.mark.asyncio
    async def test_platform_service_integration(self):
        """Test integration with platform service"""
        project_path = Path("/test/project")
        docker_tag = "test:latest"

        # Mock callbacks
        output_callback = Mock()
        status_callback = Mock()

        # Test that platform service methods are called correctly
        with patch("services.docker_service.run_in_executor") as mock_executor, patch(
            "services.docker_service.run_subprocess_streaming_async"
        ) as mock_streaming:

            # Mock platform service response with shell command
            mock_executor.return_value = (
                "bash -c 'docker build -t test:latest .'",
                "docker build command",
            )
            mock_streaming.return_value = (0, "Build successful")

            success, error_msg = await self.docker_service.build_docker_image(
                project_path, docker_tag, output_callback, status_callback
            )

            # Verify platform service was used
            mock_executor.assert_called()
            mock_streaming.assert_called()
            assert success is True

    @pytest.mark.asyncio
    async def test_docker_command_formatting(self):
        """Test Docker command formatting with different tags"""
        project_path = Path("/test/project")

        # Mock callbacks
        output_callback = Mock()
        status_callback = Mock()

        test_cases = [
            "simple-tag",
            "namespace/image:v1.0",
            "registry.example.com/namespace/image:latest",
            "test_image_with_underscores:dev",
        ]

        for docker_tag in test_cases:
            with patch(
                "services.docker_service.run_in_executor"
            ) as mock_executor, patch(
                "services.docker_service.run_subprocess_streaming_async",
                return_value=(0, "success"),
            ):

                mock_executor.return_value = (
                    ["docker", "build", "-t", docker_tag, "."],
                    f"docker build -t {docker_tag} .",
                )

                success, _ = await self.docker_service.build_docker_image(
                    project_path, docker_tag, output_callback, status_callback
                )

                assert success is True
                # Verify the tag was used in the command
                args, kwargs = mock_executor.call_args
                assert docker_tag in str(args)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
