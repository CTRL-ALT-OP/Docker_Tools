"""
Test suite for ValidateProjectGroupCommand with new web API validation service
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from pathlib import Path
import json
from dataclasses import dataclass

from utils.async_commands import ValidateProjectGroupCommand
from services.validation_service import ValidationService, ValidationResult, ArchiveInfo
from services.project_group_service import ProjectGroup
from models.project import Project
from utils.async_base import ServiceResult, ProcessError, AsyncResult


@pytest.fixture
def mock_validation_service():
    """Create a mock validation service."""
    service = Mock(spec=ValidationService)
    return service


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
def mock_window():
    """Create a mock tkinter window."""
    window = Mock()
    window.after = Mock()
    return window


@pytest.fixture
def mock_async_bridge():
    """Create a mock async bridge."""
    bridge = Mock()
    bridge.create_sync_event = Mock(return_value=("event_id", AsyncMock()))
    bridge.signal_from_gui = Mock()
    bridge.cleanup_event = Mock()
    return bridge


class TestValidateProjectGroupCommand:
    """Test ValidateProjectGroupCommand with new validation service."""

    @pytest.mark.asyncio
    async def test_execute_success_simple(
        self, mock_project_group, mock_validation_service
    ):
        """Test successful validation command execution without GUI components."""
        # Mock successful validation result
        mock_validation_result = ValidationResult(
            success=True,
            archived_projects=[
                ArchiveInfo(
                    "test_project",
                    "pre-edit",
                    "test_project_pre-edit.zip",
                    Path("/test/pre.zip"),
                    1000,
                ),
                ArchiveInfo(
                    "test_project",
                    "post-edit",
                    "test_project_post-edit.zip",
                    Path("/test/post.zip"),
                    1000,
                ),
            ],
            validation_output="All validations completed successfully\nUNIQUE VALIDATION ID: a1b2c3d4\n",
            failed_archives=[],
            validation_errors=[],
            total_projects=2,
            processing_time=120.5,
        )

        mock_validation_service.archive_and_validate_project_group.return_value = (
            ServiceResult.success(mock_validation_result)
        )

        # Create command without window components
        command = ValidateProjectGroupCommand(
            project_group=mock_project_group,
            validation_service=mock_validation_service,
            window=None,
            async_bridge=None,
        )

        # Execute command
        result = await command.execute()

        # Verify success
        assert result.is_success
        assert result.data["success"] is True
        assert result.data["project_group_name"] == "test_project"
        assert result.data["terminal_created"] is False  # No terminal without window
        assert result.data["validation_id"] == "a1b2c3d4"

        # Verify validation service was called
        mock_validation_service.archive_and_validate_project_group.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_validation_failure_simple(
        self, mock_project_group, mock_validation_service
    ):
        """Test validation command when validation service fails."""
        # Mock validation service failure
        mock_validation_service.archive_and_validate_project_group.return_value = (
            ServiceResult.error(ProcessError("Docker container failed to start"))
        )

        # Create command without window components
        command = ValidateProjectGroupCommand(
            project_group=mock_project_group,
            validation_service=mock_validation_service,
            window=None,
            async_bridge=None,
        )

        # Execute command
        result = await command.execute()

        # Verify failure - when validation service fails, command returns the error directly
        assert result.is_error
        assert "Docker container failed to start" in result.error.message

    @pytest.mark.asyncio
    async def test_execute_partial_success_simple(
        self, mock_project_group, mock_validation_service
    ):
        """Test validation command with partial success (some validations failed)."""
        # Mock partial validation result
        mock_validation_result = ValidationResult(
            success=False,
            archived_projects=[
                ArchiveInfo(
                    "test_project",
                    "pre-edit",
                    "test_project_pre-edit.zip",
                    Path("/test/pre.zip"),
                    1000,
                ),
                ArchiveInfo(
                    "test_project",
                    "post-edit",
                    "test_project_post-edit.zip",
                    Path("/test/post.zip"),
                    1000,
                ),
            ],
            validation_output="Some validations failed",
            failed_archives=["test_project_post-edit.zip"],
            validation_errors=["test_project_post-edit.zip: Docker build failed"],
            total_projects=2,
            processing_time=95.3,
        )

        mock_validation_service.archive_and_validate_project_group.return_value = (
            ServiceResult.partial(
                mock_validation_result, ProcessError("Some validations failed")
            )
        )

        # Create command without window components
        command = ValidateProjectGroupCommand(
            project_group=mock_project_group,
            validation_service=mock_validation_service,
            window=None,
            async_bridge=None,
        )

        # Execute command
        result = await command.execute()

        # Verify partial success - command succeeds but validation had issues
        assert result.is_success  # Command succeeded even though validation had issues
        assert result.data["success"] is False  # But validation result shows failure
        assert result.data["project_group_name"] == "test_project"

    @pytest.mark.asyncio
    async def test_handle_exception_during_execution_simple(
        self, mock_project_group, mock_validation_service
    ):
        """Test handling of unexpected exceptions during execution."""
        # Mock validation service to raise exception
        mock_validation_service.archive_and_validate_project_group.side_effect = (
            Exception("Unexpected error")
        )

        # Create command without window components
        command = ValidateProjectGroupCommand(
            project_group=mock_project_group,
            validation_service=mock_validation_service,
            window=None,
            async_bridge=None,
        )

        # Execute command
        result = await command.execute()

        # Verify error handling
        assert result.is_error
        assert "Unexpected error" in result.error.message

    @pytest.mark.asyncio
    async def test_execute_without_window(
        self, mock_project_group, mock_validation_service
    ):
        """Test validation command execution without GUI window."""
        # Mock successful validation result
        mock_validation_result = ValidationResult(
            success=True,
            archived_projects=[
                ArchiveInfo(
                    "test_project",
                    "pre-edit",
                    "test_project_pre-edit.zip",
                    Path("/test/pre.zip"),
                    1000,
                ),
            ],
            validation_output="Validation completed successfully",
            failed_archives=[],
            validation_errors=[],
            total_projects=1,
            processing_time=60.0,
        )

        mock_validation_service.archive_and_validate_project_group.return_value = (
            ServiceResult.success(mock_validation_result)
        )

        # Create command without window
        command = ValidateProjectGroupCommand(
            project_group=mock_project_group,
            validation_service=mock_validation_service,
            window=None,
            async_bridge=None,
        )

        # Execute command
        result = await command.execute()

        # Verify success
        assert result.is_success
        assert result.data["success"] is True
        assert result.data["terminal_created"] is False

        # Verify validation service was called
        mock_validation_service.archive_and_validate_project_group.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
