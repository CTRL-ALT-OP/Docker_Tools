"""
Test suite for ValidationService with new web API behavior
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from pathlib import Path
import json
from dataclasses import dataclass
from typing import List, Dict, Any

from services.validation_service import (
    ValidationService,
    ValidationSettings,
    ValidationResult,
    ArchiveInfo,
)
from services.project_group_service import ProjectGroup
from models.project import Project
from utils.async_base import ServiceResult, ProcessError, ResourceError


@pytest.fixture
def validation_service():
    """Create a ValidationService instance for testing."""
    return ValidationService()


@pytest.fixture
def mock_project_group():
    """Create a mock project group for testing."""
    mock_project_service = Mock()
    # Fix the Mock comparison issue by providing proper return values
    mock_project_service.get_folder_sort_order.side_effect = lambda x: str(x)
    mock_project_service.get_folder_alias.return_value = "test-alias"

    project_group = ProjectGroup("test_project", mock_project_service)

    # Add some test projects
    project1 = Project(
        "pre-edit", "test_project", Path("/test/pre-edit"), "pre-edit/test_project"
    )
    project2 = Project(
        "post-edit", "test_project", Path("/test/post-edit"), "post-edit/test_project"
    )

    project_group.add_project(project1)
    project_group.add_project(project2)

    return project_group


@pytest.fixture
def mock_validation_settings():
    """Create mock validation settings."""
    return ValidationSettings(
        validation_tool_path=Path("/test/validation-tool"),
        codebases_path=Path("/test/validation-tool/codebases"),
        auto_cleanup=True,
        max_parallel_archives=2,
        timeout_minutes=30,
    )


@pytest.fixture
def mock_zip_files(tmp_path):
    """Create mock ZIP files for testing."""
    codebases_path = tmp_path / "codebases"
    codebases_path.mkdir(parents=True)

    # Create some test ZIP files
    zip1 = codebases_path / "test_project_pre-edit.zip"
    zip2 = codebases_path / "test_project_post-edit.zip"

    zip1.write_bytes(b"fake zip content 1")
    zip2.write_bytes(b"fake zip content 2")

    return [zip1, zip2]


class TestValidationServiceHealth:
    """Test ValidationService health checks."""

    @pytest.mark.asyncio
    async def test_health_check_success(self, validation_service):
        """Test successful health check when validation tool exists."""
        with patch.object(
            validation_service.file_service, "health_check"
        ) as mock_file_health:
            mock_file_health.return_value = ServiceResult.success({})

            with patch("pathlib.Path.exists", return_value=True):
                result = await validation_service.health_check()

                assert result.is_success
                assert result.data["status"] == "healthy"
                assert result.data["validation_tool_available"] is True

    @pytest.mark.asyncio
    async def test_health_check_degraded(self, validation_service):
        """Test health check when validation tool is missing."""
        with patch.object(
            validation_service.file_service, "health_check"
        ) as mock_file_health:
            mock_file_health.return_value = ServiceResult.success({})

            with patch("pathlib.Path.exists", return_value=False):
                result = await validation_service.health_check()

                assert result.is_error
                assert "degraded state" in result.error.message


class TestValidationServiceDocker:
    """Test Docker-related functionality."""

    @pytest.mark.asyncio
    async def test_check_docker_running_success(self, validation_service):
        """Test successful Docker check."""
        mock_result = Mock()
        mock_result.returncode = 0

        with patch("services.validation_service.run_in_executor") as mock_executor:
            mock_executor.return_value = mock_result

            result = await validation_service._check_docker_running()
            assert result is True

    @pytest.mark.asyncio
    async def test_check_docker_running_failure(self, validation_service):
        """Test Docker check when Docker is not running."""
        mock_result = Mock()
        mock_result.returncode = 1

        with patch("services.validation_service.run_in_executor") as mock_executor:
            mock_executor.return_value = mock_result

            result = await validation_service._check_docker_running()
            assert result is False

    @pytest.mark.asyncio
    async def test_check_validation_service_running(self, validation_service):
        """Test checking if validation service is running."""
        mock_response = Mock()
        mock_response.status_code = 200

        with patch("services.validation_service.run_in_executor") as mock_executor:
            mock_executor.return_value = mock_response

            result = await validation_service._check_validation_service(
                "http://localhost:8080"
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_check_validation_service_not_running(self, validation_service):
        """Test checking validation service when it's not running."""
        with patch("services.validation_service.run_in_executor") as mock_executor:
            mock_executor.side_effect = Exception("Connection refused")

            result = await validation_service._check_validation_service(
                "http://localhost:8080"
            )
            assert result is False


class TestValidationServiceStartup:
    """Test validation service startup."""

    @pytest.mark.asyncio
    async def test_start_validation_service_success(self, validation_service, tmp_path):
        """Test successful validation service startup."""
        validation_tool_path = tmp_path / "validation-tool"
        validation_tool_path.mkdir()

        # Create mock run.bat
        run_bat = validation_tool_path / "run.bat"
        run_bat.write_text("@echo off\necho Starting validation service")

        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None
        mock_process.stdout.readline.return_value = "Starting containers...\n"

        output_callback = Mock()

        with patch("services.validation_service.subprocess.Popen") as mock_popen:
            mock_popen.return_value = mock_process

            with patch.object(
                validation_service, "_check_docker_running"
            ) as mock_docker_check:
                mock_docker_check.return_value = True

                with patch(
                    "services.validation_service.asyncio.create_task"
                ) as mock_create_task:
                    with patch(
                        "services.validation_service.asyncio.sleep"
                    ) as mock_sleep:
                        with patch.object(
                            validation_service.platform_service, "is_windows"
                        ) as mock_is_windows:
                            # Mock platform check to avoid platform-specific issues in Docker
                            mock_is_windows.return_value = True

                            result = await validation_service._start_validation_service(
                                validation_tool_path, output_callback
                            )

                            assert result is True
                            assert hasattr(validation_service, "_validation_process")
                            mock_create_task.assert_called_once()
                            mock_docker_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_validation_service_docker_not_running(
        self, validation_service, tmp_path
    ):
        """Test validation service startup when Docker is not running."""
        validation_tool_path = tmp_path / "validation-tool"
        validation_tool_path.mkdir()

        output_callback = Mock()

        with patch.object(
            validation_service, "_check_docker_running"
        ) as mock_docker_check:
            mock_docker_check.return_value = False

            result = await validation_service._start_validation_service(
                validation_tool_path, output_callback
            )

            assert result is False
            output_callback.assert_any_call(
                "❌ Docker is not running. Please start Docker Desktop first.\n"
            )


class TestValidationServiceWebAPI:
    """Test web API functionality."""

    @pytest.mark.asyncio
    async def test_run_web_validation_success(self, validation_service, tmp_path):
        """Test successful web validation."""
        zip_file = tmp_path / "test.zip"
        zip_file.write_bytes(b"fake zip content")

        # Mock upload response
        mock_upload_response = Mock()
        mock_upload_response.status_code = 200
        mock_upload_response.json.return_value = {"session_id": "test-session-123"}

        output_callback = Mock()

        with patch("services.validation_service.run_in_executor") as mock_executor:
            mock_executor.return_value = mock_upload_response

            with patch.object(
                validation_service, "_poll_validation_results"
            ) as mock_poll:
                mock_poll.return_value = (
                    True,
                    "Build Success: True\nTest Success: True",
                    [],
                )

                success, output, errors = await validation_service._run_web_validation(
                    "http://localhost:8080", zip_file, output_callback
                )

                assert success is True
                assert "Build Success: True" in output
                assert errors == []

    @pytest.mark.asyncio
    async def test_run_web_validation_upload_failure(
        self, validation_service, tmp_path
    ):
        """Test web validation when upload fails."""
        zip_file = tmp_path / "test.zip"
        zip_file.write_bytes(b"fake zip content")

        # Mock upload response failure
        mock_upload_response = Mock()
        mock_upload_response.status_code = 500

        output_callback = Mock()

        with patch("services.validation_service.run_in_executor") as mock_executor:
            mock_executor.return_value = mock_upload_response

            success, output, errors = await validation_service._run_web_validation(
                "http://localhost:8080", zip_file, output_callback
            )

            assert success is False
            assert "Upload failed with status 500" in output
            assert len(errors) == 1

    @pytest.mark.asyncio
    async def test_poll_validation_results_success(self, validation_service):
        """Test successful result polling."""
        mock_status_response = Mock()
        mock_status_response.status_code = 200
        mock_status_response.json.return_value = {
            "status": "complete",
            "progress": 100,
            "message": "Validation complete",
            "result": {
                "validation_success": True,
                "build_success": True,
                "test_success": True,
                "test_execution_time": 5.2,
                "error_message": None,
            },
        }

        output_callback = Mock()

        with patch("services.validation_service.run_in_executor") as mock_executor:
            mock_executor.return_value = mock_status_response

            success, output, errors = await validation_service._poll_validation_results(
                "http://localhost:8080", "test-session-123", "test.zip", output_callback
            )

            assert success is True
            assert "Build Success: True" in output
            assert "Test Success: True" in output
            assert "Test Time: 5.2s" in output
            assert errors == []

    @pytest.mark.asyncio
    async def test_poll_validation_results_failure(self, validation_service):
        """Test result polling when validation fails."""
        mock_status_response = Mock()
        mock_status_response.status_code = 200
        mock_status_response.json.return_value = {
            "status": "complete",
            "progress": 100,
            "message": "Validation complete",
            "result": {
                "validation_success": False,
                "build_success": False,
                "test_success": False,
                "error_message": "Docker build failed",
            },
        }

        output_callback = Mock()

        with patch("services.validation_service.run_in_executor") as mock_executor:
            mock_executor.return_value = mock_status_response

            success, output, errors = await validation_service._poll_validation_results(
                "http://localhost:8080", "test-session-123", "test.zip", output_callback
            )

            assert success is False
            assert "Build Success: False" in output
            assert "Error: Docker build failed" in output
            assert len(errors) == 1
            assert "test.zip: Docker build failed" in errors[0]

    @pytest.mark.asyncio
    async def test_poll_validation_results_timeout(self, validation_service):
        """Test result polling timeout."""
        mock_status_response = Mock()
        mock_status_response.status_code = 200
        mock_status_response.json.return_value = {
            "status": "building",
            "progress": 50,
            "message": "Building Docker image...",
        }

        output_callback = Mock()

        with patch("services.validation_service.run_in_executor") as mock_executor:
            mock_executor.return_value = mock_status_response

            with patch("time.time") as mock_time:
                # Mock time to simulate timeout
                mock_time.side_effect = [0, 1900, 1900]  # Start, check, timeout

                success, output, errors = (
                    await validation_service._poll_validation_results(
                        "http://localhost:8080",
                        "test-session-123",
                        "test.zip",
                        output_callback,
                    )
                )

                assert success is False
                assert "timed out" in output
                assert len(errors) == 1


class TestValidationServiceIntegration:
    """Test full validation service integration."""

    @pytest.mark.asyncio
    async def test_archive_and_validate_project_group_success(
        self, validation_service, mock_project_group, tmp_path
    ):
        """Test successful end-to-end validation."""
        # Setup mock validation tool directory
        validation_tool_path = tmp_path / "validation-tool"
        validation_tool_path.mkdir()
        codebases_path = validation_tool_path / "codebases"
        codebases_path.mkdir()

        # Create mock ZIP files
        zip1 = codebases_path / "test_project_pre-edit.zip"
        zip2 = codebases_path / "test_project_post-edit.zip"
        zip1.write_bytes(b"fake zip content 1")
        zip2.write_bytes(b"fake zip content 2")

        # Mock validation settings
        mock_settings = ValidationSettings(
            validation_tool_path=validation_tool_path,
            codebases_path=codebases_path,
            auto_cleanup=True,
            max_parallel_archives=2,
            timeout_minutes=30,
        )

        output_callback = Mock()
        status_callback = Mock()

        with patch.object(
            validation_service, "get_validation_settings"
        ) as mock_get_settings:
            mock_get_settings.return_value = ServiceResult.success(mock_settings)

            with patch.object(
                validation_service, "_clear_existing_archives"
            ) as mock_clear:
                with patch.object(
                    validation_service, "_archive_all_versions"
                ) as mock_archive:
                    # Mock successful archiving
                    mock_archive.return_value = ServiceResult.success(
                        [
                            ArchiveInfo(
                                "test_project",
                                "pre-edit",
                                "test_project_pre-edit.zip",
                                zip1,
                                1000,
                            ),
                            ArchiveInfo(
                                "test_project",
                                "post-edit",
                                "test_project_post-edit.zip",
                                zip2,
                                1000,
                            ),
                        ]
                    )

                    with patch.object(
                        validation_service, "_run_validation_script"
                    ) as mock_run:
                        mock_run.return_value = ServiceResult.success(
                            ("All validations completed successfully", [], True)
                        )

                        result = (
                            await validation_service.archive_and_validate_project_group(
                                mock_project_group,
                                output_callback,
                                status_callback,
                                mock_settings,
                            )
                        )

                        assert result.is_success
                        assert result.data.success is True  # All validations passed
                        assert len(result.data.archived_projects) == 2
                        assert result.data.total_projects == 2

    @pytest.mark.asyncio
    async def test_archive_and_validate_project_group_with_failures(
        self, validation_service, mock_project_group, tmp_path
    ):
        """Test validation when some codebases fail validation."""
        validation_tool_path = tmp_path / "validation-tool"
        validation_tool_path.mkdir()
        codebases_path = validation_tool_path / "codebases"
        codebases_path.mkdir()

        mock_settings = ValidationSettings(
            validation_tool_path=validation_tool_path,
            codebases_path=codebases_path,
            auto_cleanup=True,
            max_parallel_archives=2,
            timeout_minutes=30,
        )

        output_callback = Mock()
        status_callback = Mock()

        with patch.object(
            validation_service, "get_validation_settings"
        ) as mock_get_settings:
            mock_get_settings.return_value = ServiceResult.success(mock_settings)

            with patch.object(
                validation_service, "_clear_existing_archives"
            ) as mock_clear:
                with patch.object(
                    validation_service, "_archive_all_versions"
                ) as mock_archive:
                    mock_archive.return_value = ServiceResult.success(
                        [
                            ArchiveInfo(
                                "project1",
                                "pre-edit",
                                "pre-edit_project1.zip",
                                tmp_path / "pre-edit_project1.zip",
                                1000,
                            ),
                            ArchiveInfo(
                                "project1",
                                "post-edit",
                                "post-edit_project1.zip",
                                tmp_path / "post-edit_project1.zip",
                                1000,
                            ),
                        ]
                    )

                    with patch.object(
                        validation_service, "_run_validation_script"
                    ) as mock_run:
                        # Validation process completes but some codebases fail
                        mock_run.return_value = ServiceResult.success(
                            ("Some validations failed", ["error1", "error2"], False)
                        )

                        result = (
                            await validation_service.archive_and_validate_project_group(
                                mock_project_group,
                                output_callback,
                                status_callback,
                                mock_settings,
                            )
                        )

                        assert result.is_success  # Process completed successfully
                        assert result.data.success is False  # But validation failed
                        assert len(result.data.archived_projects) == 2
                        assert result.data.total_projects == 2
                        assert len(result.data.validation_errors) == 2

    @pytest.mark.asyncio
    async def test_archive_and_validate_project_group_no_versions(
        self, validation_service, tmp_path
    ):
        """Test validation when project group has no versions."""
        mock_project_service = Mock()
        empty_project_group = ProjectGroup("empty_project", mock_project_service)

        validation_tool_path = tmp_path / "validation-tool"
        validation_tool_path.mkdir()
        codebases_path = validation_tool_path / "codebases"
        codebases_path.mkdir()

        mock_settings = ValidationSettings(
            validation_tool_path=validation_tool_path,
            codebases_path=codebases_path,
            auto_cleanup=True,
            max_parallel_archives=2,
            timeout_minutes=30,
        )

        output_callback = Mock()
        status_callback = Mock()

        with patch.object(
            validation_service, "get_validation_settings"
        ) as mock_get_settings:
            mock_get_settings.return_value = ServiceResult.success(mock_settings)

            with patch.object(
                validation_service, "_clear_existing_archives"
            ) as mock_clear:
                result = await validation_service.archive_and_validate_project_group(
                    empty_project_group, output_callback, status_callback, mock_settings
                )

                assert result.is_error
                assert "No versions found" in result.error.message

    @pytest.mark.asyncio
    async def test_run_validation_script_service_already_running(
        self, validation_service, tmp_path
    ):
        """Test validation when service is already running."""
        validation_tool_path = tmp_path / "validation-tool"
        validation_tool_path.mkdir()
        codebases_path = validation_tool_path / "codebases"
        codebases_path.mkdir()

        # Create mock ZIP files
        zip1 = codebases_path / "test1.zip"
        zip1.write_bytes(b"fake zip content 1")

        output_callback = Mock()

        with patch.object(
            validation_service, "_check_validation_service"
        ) as mock_check:
            mock_check.return_value = True  # Service already running

            with patch.object(
                validation_service, "_run_web_validation"
            ) as mock_web_val:
                mock_web_val.return_value = (
                    True,
                    "Build Success: True\nTest Success: True",
                    [],
                )

                result = await validation_service._run_validation_script(
                    validation_tool_path, output_callback
                )

                assert result.is_success
                output_callback.assert_any_call(
                    "✅ Validation service is already running\n"
                )


class TestValidationServiceEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_validation_with_mixed_results(self, validation_service, tmp_path):
        """Test validation with some successes and some failures."""
        validation_tool_path = tmp_path / "validation-tool"
        validation_tool_path.mkdir()
        codebases_path = validation_tool_path / "codebases"
        codebases_path.mkdir()

        # Create mock ZIP files
        zip1 = codebases_path / "success.zip"
        zip2 = codebases_path / "failure.zip"
        zip1.write_bytes(b"fake zip content 1")
        zip2.write_bytes(b"fake zip content 2")

        output_callback = Mock()

        with patch.object(
            validation_service, "_check_validation_service"
        ) as mock_check:
            mock_check.return_value = True

            with patch.object(
                validation_service, "_run_web_validation"
            ) as mock_web_val:
                # Mock mixed results
                mock_web_val.side_effect = [
                    (True, "Build Success: True\nTest Success: True", []),
                    (
                        False,
                        "Build Success: False\nTest Success: False",
                        ["failure.zip: Build failed"],
                    ),
                ]

                result = await validation_service._run_validation_script(
                    validation_tool_path, output_callback
                )

                assert result.is_success  # Still success but with captured errors
                assert len(result.data[1]) == 1  # One error captured
                assert result.data[2] is False  # all_successful should be False
                # Now with the corrected logic, it should properly count 1 failure
                output_callback.assert_any_call(
                    "⚠️ 1 codebase(s) failed validation. Check individual results above.\n"
                )

    @pytest.mark.asyncio
    async def test_validation_tool_not_found(self, validation_service, tmp_path):
        """Test validation when validation tool directory doesn't exist."""
        nonexistent_path = tmp_path / "nonexistent"

        output_callback = Mock()

        # In Docker environments, the service startup may fail before reaching
        # the codebases directory check, so we need to handle both error cases
        result = await validation_service._run_validation_script(
            nonexistent_path, output_callback
        )

        assert result.is_error
        # Accept either error message depending on where the failure occurs
        error_message = result.error.message
        assert (
            "Codebases directory not found" in error_message
            or "Failed to start validation service" in error_message
        ), f"Unexpected error message: {error_message}"

    @pytest.mark.asyncio
    async def test_no_zip_files_found(self, validation_service, tmp_path):
        """Test validation when no ZIP files are found."""
        validation_tool_path = tmp_path / "validation-tool"
        validation_tool_path.mkdir()
        codebases_path = validation_tool_path / "codebases"
        codebases_path.mkdir()
        # No ZIP files created

        output_callback = Mock()

        with patch.object(
            validation_service, "_check_validation_service"
        ) as mock_check:
            mock_check.return_value = True

            result = await validation_service._run_validation_script(
                validation_tool_path, output_callback
            )

            assert result.is_error
            assert "No ZIP files found" in result.error.message


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
