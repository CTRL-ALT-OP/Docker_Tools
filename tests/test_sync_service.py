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
import asyncio

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
        # Mock the get_folder_alias method to map folders to aliases
        folder_aliases = {
            "pre-edit": "preedit",
            "post-edit": "postedit-beetle",
            "post-edit2": "postedit-sonnet",
            "correct-edit": "rewrite",
        }
        project_service.get_folder_alias.side_effect = lambda x: folder_aliases.get(
            x, None
        )
        return project_service

    def _create_test_project_group(self):
        """Create a test project group with mocked project service"""
        project_service = self.create_mock_project_service()
        project_group = ProjectGroup("test-project", project_service)

        projects = self.create_test_project_structure()
        for project in projects:
            project_group.add_project(project)

        return project_group

    def _create_test_project(self, parent: str, name: str):
        """Create a single test project"""
        if not self.temp_dir:
            self.temp_dir = tempfile.mkdtemp()

        base_path = Path(self.temp_dir)
        project_path = base_path / parent / name
        project_path.mkdir(parents=True, exist_ok=True)

        return Project(
            parent=parent,
            name=name,
            path=project_path,
            relative_path=f"{parent}/{name}",
        )

    def create_test_file(
        self, project: Project, file_name: str, content: str = "test content\n"
    ):
        """Helper to create a test file in a project"""
        file_path = project.path / file_name
        file_path.write_text(content)
        return file_path

    @pytest.mark.asyncio
    async def test_sync_file_from_pre_edit_success(self):
        """Test successful file sync from pre-edit version"""
        # Create project group with pre-edit and post-edit versions
        project_group = self._create_test_project_group()

        # Create test file in pre-edit version
        test_file = "test_script.py"
        pre_edit_project = project_group.get_version("pre-edit")
        test_file_path = pre_edit_project.path / test_file
        test_file_path.write_text("print('Hello from pre-edit')")

        result = await self.sync_service.sync_file_from_pre_edit(
            project_group, test_file
        )

        assert result.is_success is True
        sync_data = result.data
        assert sync_data.file_name == test_file
        assert sync_data.success_count > 0

        # Verify file was copied to other versions
        for version in ["post-edit", "post-edit2", "correct-edit"]:
            target_project = project_group.get_version(version)
            if target_project:
                target_file = target_project.path / test_file
                assert target_file.exists()
                assert target_file.read_text() == "print('Hello from pre-edit')"

    @pytest.mark.asyncio
    async def test_sync_file_from_pre_edit_different_file_types(self):
        """Test syncing different types of files"""
        project_group = self._create_test_project_group()
        pre_edit_project = project_group.get_version("pre-edit")

        # Test different file types
        test_files = {
            "script.sh": "#!/bin/bash\necho 'test'",
            "config.json": '{"test": true}',
            "readme.md": "# Test Project",
            "data.txt": "Some test data",
        }

        for file_name, content in test_files.items():
            file_path = pre_edit_project.path / file_name
            file_path.write_text(content)

            result = await self.sync_service.sync_file_from_pre_edit(
                project_group, file_name
            )

            assert result.is_success is True
            sync_data = result.data
            assert sync_data.file_name == file_name

    @pytest.mark.asyncio
    async def test_sync_file_no_pre_edit_version(self):
        """Test sync when no pre-edit version exists"""
        # Create project group without pre-edit version
        project_service = self.create_mock_project_service()
        project_group = ProjectGroup("test-project", project_service)
        post_edit_project = self._create_test_project("post-edit", "test-project")
        project_group.add_project(post_edit_project)

        result = await self.sync_service.sync_file_from_pre_edit(
            project_group, "test_file.py"
        )

        assert result.is_error is True
        assert "pre-edit" in str(result.error).lower()

    @pytest.mark.asyncio
    async def test_sync_file_no_source_file_in_pre_edit(self):
        """Test sync when source file doesn't exist in pre-edit version"""
        project_group = self._create_test_project_group()

        result = await self.sync_service.sync_file_from_pre_edit(
            project_group, "nonexistent_file.py"
        )

        assert result.is_error is True
        assert "not found" in str(result.error).lower()

    @pytest.mark.asyncio
    async def test_sync_file_partial_failure(self):
        """Test sync with partial failures"""
        project_group = self._create_test_project_group()

        # Create test file in pre-edit
        test_file = "test_file.py"
        pre_edit_project = project_group.get_version("pre-edit")
        test_file_path = pre_edit_project.path / test_file
        test_file_path.write_text("test content")

        # Get target projects for proper mocking
        target_projects = project_group.get_all_versions()
        target_projects = [p for p in target_projects if p.parent != "pre-edit"]

        # Ensure we have at least 2 target projects for partial failure
        assert (
            len(target_projects) >= 2
        ), "Need at least 2 target projects for partial failure test"

        # Mock _sync_file_to_targets to simulate partial failure
        def mock_sync_with_failure(source_project, target_projects_list, file_name):
            # Simulate some successes and some failures
            synced_paths = [target_projects_list[0].path / file_name]  # First succeeds
            failed_syncs = [
                target_projects_list[1].parent
            ]  # Second fails (use parent name)
            return {"synced_paths": synced_paths, "failed_syncs": failed_syncs}

        with patch.object(
            self.sync_service,
            "_sync_file_to_targets",
            side_effect=mock_sync_with_failure,
        ):
            result = await self.sync_service.sync_file_from_pre_edit(
                project_group, test_file
            )

            # Should return partial success with failed syncs recorded
            assert result.is_partial is True
            assert len(result.data.failed_syncs) > 0
            assert result.data.success_count > 0
            assert result.data.success_count < result.data.total_targets

    @pytest.mark.asyncio
    async def test_sync_file_empty_project_group(self):
        """Test sync with empty project group"""
        project_service = self.create_mock_project_service()
        empty_group = ProjectGroup("empty-project", project_service)

        result = await self.sync_service.sync_file_from_pre_edit(
            empty_group, "test_file.py"
        )

        assert result.is_error is True

    def test_get_pre_edit_version_found(self):
        """Test finding pre-edit version when it exists"""
        project_group = self._create_test_project_group()

        pre_edit_version = self.sync_service.get_pre_edit_version(project_group)
        assert pre_edit_version is not None
        assert pre_edit_version.parent == "pre-edit"

    def test_get_pre_edit_version_not_found(self):
        """Test finding pre-edit version when it doesn't exist"""
        project_service = self.create_mock_project_service()
        project_group = ProjectGroup("test-project", project_service)

        # Add only post-edit version
        post_edit_project = self._create_test_project("post-edit", "test-project")
        project_group.add_project(post_edit_project)

        pre_edit_version = self.sync_service.get_pre_edit_version(project_group)
        assert pre_edit_version is None

    def test_get_pre_edit_version_multiple_pre_edit_versions(self):
        """Test behavior with multiple pre-edit versions"""
        project_service = self.create_mock_project_service()
        project_group = ProjectGroup("test-project", project_service)

        # Add multiple pre-edit versions (should not happen in real usage)
        pre_edit1 = self._create_test_project("pre-edit", "test-project")
        pre_edit2 = self._create_test_project("pre-edit-v2", "test-project")

        project_group.add_project(pre_edit1)
        project_group.add_project(pre_edit2)

        # Should return the one that matches "pre-edit" exactly
        pre_edit_version = self.sync_service.get_pre_edit_version(project_group)
        assert pre_edit_version is not None
        assert pre_edit_version.parent == "pre-edit"

    @pytest.mark.asyncio
    async def test_has_file_exists(self):
        """Test checking if file exists in project"""
        project = self._create_test_project("test", "test-project")

        # Create test file
        test_file = "test.py"
        (project.path / test_file).write_text("test content")

        result = await self.sync_service.has_file(project, test_file)
        assert result.is_success is True
        assert result.data is True

    @pytest.mark.asyncio
    async def test_has_file_not_exists(self):
        """Test checking non-existent file"""
        project = self._create_test_project("test", "test-project")

        result = await self.sync_service.has_file(project, "nonexistent.py")
        assert result.is_success is True
        assert result.data is False

    @pytest.mark.asyncio
    async def test_has_file_different_file_types(self):
        """Test checking different file types"""
        project = self._create_test_project("test", "test-project")

        test_files = ["script.py", "config.json", "readme.md", "data.txt", "script.sh"]

        for file_name in test_files:
            (project.path / file_name).write_text("content")

            result = await self.sync_service.has_file(project, file_name)
            assert result.is_success is True
            assert result.data is True

    @pytest.mark.asyncio
    async def test_copy_file_success(self):
        """Test successful file copy"""
        source_project = self._create_test_project("source", "test-project")
        target_project = self._create_test_project("target", "test-project")

        # Create source file
        test_file = "test.py"
        test_content = "print('hello world')"
        (source_project.path / test_file).write_text(test_content)

        result = await self.sync_service.copy_file(
            source_project, target_project, test_file
        )
        assert result.is_success is True
        assert result.data is True

        # Verify file was copied
        target_file = target_project.path / test_file
        assert target_file.exists()
        assert target_file.read_text() == test_content

    @pytest.mark.asyncio
    async def test_copy_file_different_types(self):
        """Test copying different file types"""
        source_project = self._create_test_project("source", "test-project")
        target_project = self._create_test_project("target", "test-project")

        test_files = {
            "script.py": "print('python')",
            "config.json": '{"key": "value"}',
            "readme.md": "# Title",
            "data.txt": "plain text",
        }

        for file_name, content in test_files.items():
            (source_project.path / file_name).write_text(content)

            result = await self.sync_service.copy_file(
                source_project, target_project, file_name
            )
            assert result.is_success is True
            assert result.data is True

    @pytest.mark.asyncio
    async def test_copy_file_source_not_exists(self):
        """Test copying non-existent source file"""
        source_project = self._create_test_project("source", "test-project")
        target_project = self._create_test_project("target", "test-project")

        result = await self.sync_service.copy_file(
            source_project, target_project, "nonexistent.py"
        )
        assert result.is_error is True

    @pytest.mark.asyncio
    async def test_copy_file_overwrites_existing(self):
        """Test that copy overwrites existing files"""
        source_project = self._create_test_project("source", "test-project")
        target_project = self._create_test_project("target", "test-project")

        test_file = "test.py"

        # Create source file
        source_content = "print('source')"
        (source_project.path / test_file).write_text(source_content)

        # Create existing target file with different content
        target_content = "print('old target')"
        (target_project.path / test_file).write_text(target_content)

        result = await self.sync_service.copy_file(
            source_project, target_project, test_file
        )
        assert result.is_success is True
        assert result.data is True

        # Verify file was overwritten
        final_content = (target_project.path / test_file).read_text()
        assert final_content == source_content

    @pytest.mark.asyncio
    async def test_sync_file_overwrites_existing_files(self):
        """Test that sync overwrites existing files in target projects"""
        project_group = self._create_test_project_group()

        test_file = "test.py"
        source_content = "print('from pre-edit')"

        # Create file in pre-edit
        pre_edit_project = project_group.get_version("pre-edit")
        (pre_edit_project.path / test_file).write_text(source_content)

        # Create different content in target projects
        for version in ["post-edit", "post-edit2"]:
            target_project = project_group.get_version(version)
            if target_project:
                (target_project.path / test_file).write_text(f"print('old {version}')")

        result = await self.sync_service.sync_file_from_pre_edit(
            project_group, test_file
        )
        assert result.is_success is True

        # Verify all target files were overwritten with pre-edit content
        for version in ["post-edit", "post-edit2", "correct-edit"]:
            target_project = project_group.get_version(version)
            if target_project:
                target_file = target_project.path / test_file
                assert target_file.exists()
                assert target_file.read_text() == source_content


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
