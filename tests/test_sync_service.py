"""
Tests for SyncService - Tests for syncing files from pre-edit to other versions
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

# Add parent directory to path to import modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from services.sync_service import SyncService
from services.project_service import ProjectService
from services.project_group_service import ProjectGroup
from models.project import Project


class TestSyncService:
    """Test cases for SyncService"""

    def setup_method(self):
        """Set up test fixtures"""
        self.sync_service = SyncService()
        self.temp_dir = None

    def teardown_method(self):
        """Clean up test fixtures"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def create_test_project_structure(self):
        """Create a temporary directory structure for testing"""
        self.temp_dir = tempfile.mkdtemp()
        base_path = Path(self.temp_dir)

        # Create project structure: base_dir/version/project_name
        versions = ["pre-edit", "post-edit", "post-edit2", "correct-edit"]
        project_name = "test_project"

        projects = []
        for version in versions:
            version_path = base_path / version / project_name
            version_path.mkdir(parents=True, exist_ok=True)

            project = Project(
                parent=version,
                name=project_name,
                path=version_path,
                relative_path=f"{version}/{project_name}",
            )
            projects.append(project)

        return projects

    def create_mock_project_service(self):
        """Create a properly mocked project service"""
        project_service = Mock()
        # Mock the get_folder_sort_order method to return consistent ordering
        sort_order = {"pre-edit": 0, "post-edit": 1, "post-edit2": 2, "correct-edit": 3}
        project_service.get_folder_sort_order.side_effect = lambda x: sort_order.get(
            x, 99
        )
        return project_service

    def create_test_file(
        self, project: Project, file_name: str, content: str = "test content\n"
    ):
        """Helper to create a test file in a project"""
        file_path = project.path / file_name
        file_path.write_text(content)
        return file_path

    async def test_sync_file_from_pre_edit_success(self):
        """Test successfully syncing a file from pre-edit to other versions"""

        # Arrange
        projects = self.create_test_project_structure()
        project_service = self.create_mock_project_service()
        project_group = ProjectGroup("test_project", project_service)

        for project in projects:
            project_group.add_project(project)

        file_name = "run_tests.sh"
        pre_edit_content = "#!/bin/bash\necho 'Pre-edit tests'\npytest .\n"
        pre_edit_project = next(p for p in projects if p.parent == "pre-edit")
        self.create_test_file(pre_edit_project, file_name, pre_edit_content)

        # Act
        success, message, synced_paths = (
            await self.sync_service.sync_file_from_pre_edit(project_group, file_name)
        )

        # Assert
        assert success is True
        assert "successfully synced" in message.lower()
        assert len(synced_paths) == 3  # Should sync to 3 other versions

        # Verify files were copied
        for project in projects:
            if project.parent != "pre-edit":
                file_path = project.path / file_name
                assert file_path.exists()
                assert file_path.read_text() == pre_edit_content

    @pytest.mark.asyncio
    async def test_sync_file_from_pre_edit_different_file_types(self):
        """Test sync works with different file types"""

        # Arrange
        projects = self.create_test_project_structure()
        project_service = self.create_mock_project_service()
        project_group = ProjectGroup("test_project", project_service)

        for project in projects:
            project_group.add_project(project)

        pre_edit_project = next(p for p in projects if p.parent == "pre-edit")

        # Test different file types
        test_files = [
            ("config.json", '{"test": "value"}'),
            ("README.md", "# Test Project\nThis is a test."),
            ("requirements.txt", "pytest==7.0.0\nrequests==2.28.0"),
            ("Dockerfile", "FROM python:3.9\nCOPY . /app"),
        ]

        for file_name, content in test_files:
            # Create file in pre-edit
            self.create_test_file(pre_edit_project, file_name, content)

            # Act
            success, message, synced_paths = (
                await self.sync_service.sync_file_from_pre_edit(
                    project_group, file_name
                )
            )

            # Assert
            assert success is True, f"Failed to sync {file_name}"
            assert len(synced_paths) == 3

            # Verify file was copied to all other versions
            for project in projects:
                if project.parent != "pre-edit":
                    file_path = project.path / file_name
                    assert (
                        file_path.exists()
                    ), f"{file_name} not found in {project.parent}"
                    assert file_path.read_text() == content

    @pytest.mark.asyncio
    async def test_sync_file_no_pre_edit_version(self):
        """Test sync fails when no pre-edit version exists"""
        # Arrange
        projects = self.create_test_project_structure()
        # Remove pre-edit project
        projects = [p for p in projects if p.parent != "pre-edit"]

        project_service = self.create_mock_project_service()
        project_group = ProjectGroup("test_project", project_service)

        for project in projects:
            project_group.add_project(project)

        # Act
        success, message, synced_paths = (
            await self.sync_service.sync_file_from_pre_edit(
                project_group, "any_file.txt"
            )
        )

        # Assert
        assert success is False
        assert "pre-edit" in message.lower()
        assert len(synced_paths) == 0

    @pytest.mark.asyncio
    async def test_sync_file_no_source_file_in_pre_edit(self):
        """Test sync fails when specified file doesn't exist in pre-edit"""

        # Arrange
        projects = self.create_test_project_structure()
        project_service = self.create_mock_project_service()
        project_group = ProjectGroup("test_project", project_service)

        for project in projects:
            project_group.add_project(project)

        file_name = "nonexistent_file.txt"

        # Act
        success, message, synced_paths = (
            await self.sync_service.sync_file_from_pre_edit(project_group, file_name)
        )

        # Assert
        assert success is False
        assert file_name in message.lower()
        assert "not found" in message.lower() or "does not exist" in message.lower()
        assert len(synced_paths) == 0

    @pytest.mark.asyncio
    async def test_sync_file_partial_failure(self):
        """Test sync when some target directories have issues"""

        # Arrange
        projects = self.create_test_project_structure()
        project_service = self.create_mock_project_service()
        project_group = ProjectGroup("test_project", project_service)

        for project in projects:
            project_group.add_project(project)

        # Create test file in pre-edit
        file_name = "test_file.txt"
        pre_edit_project = next(p for p in projects if p.parent == "pre-edit")
        self.create_test_file(pre_edit_project, file_name)

        # Mock file copy failure for some targets
        with patch.object(self.sync_service, "copy_file") as mock_copy:
            # First call succeeds, second fails, third succeeds
            async def copy_side_effect(*args):
                if not hasattr(copy_side_effect, "call_count"):
                    copy_side_effect.call_count = 0
                copy_side_effect.call_count += 1
                return copy_side_effect.call_count in [1, 3]  # 1st and 3rd succeed

            mock_copy.side_effect = copy_side_effect

            # Act
            success, message, synced_paths = (
                await self.sync_service.sync_file_from_pre_edit(
                    project_group, file_name
                )
            )

            # Assert
            assert success is False  # Partial failure should return False
            assert "partially" in message.lower() or "some" in message.lower()
            assert len(synced_paths) == 2  # Only successful copies

    @pytest.mark.asyncio
    async def test_sync_file_empty_project_group(self):
        """Test sync with empty project group"""
        # Arrange
        project_service = self.create_mock_project_service()
        project_group = ProjectGroup("empty_project", project_service)

        # Act
        success, message, synced_paths = (
            await self.sync_service.sync_file_from_pre_edit(
                project_group, "any_file.txt"
            )
        )

        # Assert
        assert success is False
        assert "pre-edit" in message.lower()
        assert len(synced_paths) == 0

    def test_get_pre_edit_version_found(self):
        """Test getting pre-edit version when it exists"""
        # Arrange
        projects = self.create_test_project_structure()
        project_service = self.create_mock_project_service()
        project_group = ProjectGroup("test_project", project_service)

        for project in projects:
            project_group.add_project(project)

        # Act
        pre_edit_project = self.sync_service.get_pre_edit_version(project_group)

        # Assert
        assert pre_edit_project is not None
        assert pre_edit_project.parent == "pre-edit"

    def test_get_pre_edit_version_not_found(self):
        """Test getting pre-edit version when it doesn't exist"""
        # Arrange
        projects = self.create_test_project_structure()
        # Remove pre-edit project
        projects = [p for p in projects if p.parent != "pre-edit"]

        project_service = self.create_mock_project_service()
        project_group = ProjectGroup("test_project", project_service)

        for project in projects:
            project_group.add_project(project)

        # Act
        pre_edit_project = self.sync_service.get_pre_edit_version(project_group)

        # Assert
        assert pre_edit_project is None

    def test_get_pre_edit_version_multiple_pre_edit_versions(self):
        """Test getting pre-edit version when multiple exist (should return first found)"""
        # Arrange
        projects = self.create_test_project_structure()
        # Add another pre-edit project (edge case)
        additional_pre_edit = Project(
            parent="pre-edit",
            name="another_project",
            path=Path(self.temp_dir) / "pre-edit" / "another_project",
            relative_path="pre-edit/another_project",
        )
        projects.append(additional_pre_edit)

        project_service = self.create_mock_project_service()
        project_group = ProjectGroup("test_project", project_service)

        for project in projects:
            project_group.add_project(project)

        # Act
        pre_edit_project = self.sync_service.get_pre_edit_version(project_group)

        # Assert
        assert pre_edit_project is not None
        assert pre_edit_project.parent == "pre-edit"

    @pytest.mark.asyncio
    async def test_has_file_exists(self):
        """Test checking for file when it exists"""

        # Arrange
        projects = self.create_test_project_structure()
        project = projects[0]
        file_name = "test_file.txt"
        self.create_test_file(project, file_name)

        # Act
        has_file = await self.sync_service.has_file(project, file_name)

        # Assert
        assert has_file is True

    @pytest.mark.asyncio
    async def test_has_file_not_exists(self):
        """Test checking for file when it doesn't exist"""

        # Arrange
        projects = self.create_test_project_structure()
        project = projects[0]
        file_name = "nonexistent_file.txt"

        # Act
        has_file = await self.sync_service.has_file(project, file_name)

        # Assert
        assert has_file is False

    @pytest.mark.asyncio
    async def test_has_file_different_file_types(self):
        """Test has_file works with different file types and extensions"""

        # Arrange
        projects = self.create_test_project_structure()
        project = projects[0]

        test_files = [
            "script.sh",
            "config.json",
            "README.md",
            "requirements.txt",
            "Dockerfile",
            ".gitignore",
            "file_without_extension",
        ]

        for file_name in test_files:
            self.create_test_file(project, file_name)

        # Act & Assert
        for file_name in test_files:
            assert await self.sync_service.has_file(project, file_name) is True

        # Test non-existent files
        non_existent_files = ["missing.txt", "another.py", ".hidden_missing"]
        for file_name in non_existent_files:
            assert await self.sync_service.has_file(project, file_name) is False

    @pytest.mark.asyncio
    async def test_copy_file_success(self):
        """Test successful copying of any file"""

        # Arrange
        projects = self.create_test_project_structure()
        source_project = projects[0]
        target_project = projects[1]

        file_name = "test_file.txt"
        content = "This is test content\nwith multiple lines\n"
        self.create_test_file(source_project, file_name, content)

        # Act
        success = await self.sync_service.copy_file(
            source_project, target_project, file_name
        )

        # Assert
        assert success is True
        target_file = target_project.path / file_name
        assert target_file.exists()
        assert target_file.read_text() == content

    @pytest.mark.asyncio
    async def test_copy_file_different_types(self):
        """Test copying different file types"""

        # Arrange
        projects = self.create_test_project_structure()
        source_project = projects[0]
        target_project = projects[1]

        test_files = [
            ("binary_like.txt", b"binary content".decode()),
            ("script.sh", "#!/bin/bash\necho 'hello'\n"),
            ("config.json", '{"key": "value", "number": 42}'),
            ("empty_file.txt", ""),
        ]

        for file_name, content in test_files:
            # Create source file
            self.create_test_file(source_project, file_name, content)

            # Act
            success = await self.sync_service.copy_file(
                source_project, target_project, file_name
            )

            # Assert
            assert success is True, f"Failed to copy {file_name}"
            target_file = target_project.path / file_name
            assert target_file.exists()
            assert target_file.read_text() == content

    @pytest.mark.asyncio
    async def test_copy_file_source_not_exists(self):
        """Test copying when source file doesn't exist"""

        # Arrange
        projects = self.create_test_project_structure()
        source_project = projects[0]
        target_project = projects[1]
        file_name = "nonexistent_file.txt"

        # Act
        success = await self.sync_service.copy_file(
            source_project, target_project, file_name
        )

        # Assert
        assert success is False

    @pytest.mark.asyncio
    async def test_copy_file_overwrites_existing(self):
        """Test that copy_file overwrites existing files in target"""

        # Arrange
        projects = self.create_test_project_structure()
        source_project = projects[0]
        target_project = projects[1]

        file_name = "test_file.txt"
        source_content = "New content from source"
        target_content = "Old content in target"

        # Create files in both projects
        self.create_test_file(source_project, file_name, source_content)
        self.create_test_file(target_project, file_name, target_content)

        # Act
        success = await self.sync_service.copy_file(
            source_project, target_project, file_name
        )

        # Assert
        assert success is True
        target_file = target_project.path / file_name
        assert target_file.exists()
        assert target_file.read_text() == source_content  # Should be overwritten

    def test_get_non_pre_edit_versions(self):
        """Test getting all versions except pre-edit"""
        # Arrange
        projects = self.create_test_project_structure()
        project_service = self.create_mock_project_service()
        project_group = ProjectGroup("test_project", project_service)

        for project in projects:
            project_group.add_project(project)

        # Act
        non_pre_edit_versions = self.sync_service.get_non_pre_edit_versions(
            project_group
        )

        # Assert
        assert len(non_pre_edit_versions) == 3  # All except pre-edit
        assert all(p.parent != "pre-edit" for p in non_pre_edit_versions)
        version_names = {p.parent for p in non_pre_edit_versions}
        expected_versions = {"post-edit", "post-edit2", "correct-edit"}
        assert version_names == expected_versions

    def test_get_non_pre_edit_versions_only_pre_edit_exists(self):
        """Test getting non-pre-edit versions when only pre-edit exists"""
        # Arrange
        projects = self.create_test_project_structure()
        # Keep only pre-edit project
        projects = [p for p in projects if p.parent == "pre-edit"]

        project_service = self.create_mock_project_service()
        project_group = ProjectGroup("test_project", project_service)

        for project in projects:
            project_group.add_project(project)

        # Act
        non_pre_edit_versions = self.sync_service.get_non_pre_edit_versions(
            project_group
        )

        # Assert
        assert len(non_pre_edit_versions) == 0

    @pytest.mark.asyncio
    async def test_sync_file_overwrites_existing_files(self):
        """Test that sync overwrites existing files in target versions"""

        # Arrange
        projects = self.create_test_project_structure()
        project_service = self.create_mock_project_service()
        project_group = ProjectGroup("test_project", project_service)

        for project in projects:
            project_group.add_project(project)

        # Create file in pre-edit
        file_name = "config.txt"
        pre_edit_content = "Updated configuration from pre-edit"
        pre_edit_project = next(p for p in projects if p.parent == "pre-edit")
        self.create_test_file(pre_edit_project, file_name, pre_edit_content)

        # Create different files in other versions
        for project in projects:
            if project.parent != "pre-edit":
                self.create_test_file(
                    project, file_name, f"Old {project.parent} configuration"
                )

        # Act
        success, message, synced_paths = (
            await self.sync_service.sync_file_from_pre_edit(project_group, file_name)
        )

        # Assert
        assert success is True
        assert len(synced_paths) == 3

        # Verify all files now have the pre-edit content
        for project in projects:
            if project.parent != "pre-edit":
                file_path = project.path / file_name
                assert file_path.exists()
                assert file_path.read_text() == pre_edit_content


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
