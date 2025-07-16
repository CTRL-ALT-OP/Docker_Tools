"""
Tests for ProjectService - Tests for project management and folder aliases
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

from services.project_service import ProjectService
from models.project import Project
from config.config import get_config

FOLDER_ALIASES = get_config().project.folder_aliases


class TestProjectService:
    """Test cases for ProjectService"""

    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.project_service = ProjectService(self.temp_dir)

    def teardown_method(self):
        """Clean up test fixtures"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_initialization(self):
        """Test ProjectService initialization"""
        # Default initialization
        service = ProjectService()
        assert service.root_dir == Path(".").resolve()

        # Custom root directory
        custom_dir = "/custom/path"
        service = ProjectService(custom_dir)
        assert service.root_dir == Path(custom_dir).resolve()

    def test_get_folder_alias_existing(self):
        """Test getting alias for folders that have aliases"""
        # Assuming FOLDER_ALIASES has entries like:
        # {"preedit": ["pre-edit"], "postedit": ["post-edit", "post-edit2"]}

        # Test with actual aliases from settings
        with patch(
            "services.project_service.FOLDER_ALIASES",
            {
                "preedit": ["pre-edit"],
                "postedit": ["post-edit", "post-edit2"],
                "corrected": ["correct-edit"],
            },
        ):
            service = ProjectService()

            assert service.get_folder_alias("pre-edit") == "preedit"
            assert service.get_folder_alias("post-edit") == "postedit"
            assert service.get_folder_alias("post-edit2") == "postedit"
            assert service.get_folder_alias("correct-edit") == "corrected"

    def test_get_folder_alias_non_existing(self):
        """Test getting alias for folders without aliases"""
        assert self.project_service.get_folder_alias("random-folder") is None
        assert self.project_service.get_folder_alias("test-folder") is None
        assert self.project_service.get_folder_alias("") is None

    def test_get_archive_name_with_alias(self):
        """Test archive name generation for folders with aliases"""
        with patch(
            "services.project_service.FOLDER_ALIASES",
            {"preedit": ["pre-edit"], "postedit": ["post-edit", "post-edit2"]},
        ):
            service = ProjectService()

            # Test with aliased folders
            assert (
                service.get_archive_name("pre-edit", "test-project")
                == "testproject_preedit.zip"
            )
            assert (
                service.get_archive_name("post-edit", "test-project")
                == "testproject_postedit.zip"
            )
            assert (
                service.get_archive_name("post-edit2", "test-project")
                == "testproject_postedit.zip"
            )

    def test_get_archive_name_without_alias(self):
        """Test archive name generation for folders without aliases"""
        # Test without aliases
        archive_name = self.project_service.get_archive_name(
            "custom-folder", "test-project"
        )
        assert archive_name == "testproject_customfolder.zip"

        # Test with different project names
        assert (
            self.project_service.get_archive_name("folder", "my-app")
            == "myapp_folder.zip"
        )
        assert (
            self.project_service.get_archive_name("test", "demo-project")
            == "demoproject_test.zip"
        )

    def test_get_archive_name_special_characters(self):
        """Test archive name generation with special characters"""
        # Test that hyphens are removed
        assert (
            self.project_service.get_archive_name("test-folder-name", "my-project-name")
            == "myprojectname_testfoldername.zip"
        )

        # Test with multiple hyphens
        assert self.project_service.get_archive_name("a-b-c", "x-y-z") == "xyz_abc.zip"

    def test_get_docker_tag_with_alias(self):
        """Test Docker tag generation for folders with aliases"""
        with patch(
            "services.project_service.FOLDER_ALIASES",
            {"preedit": ["pre-edit"], "postedit": ["post-edit", "post-edit2"]},
        ):
            service = ProjectService()

            # Test with aliased folders
            assert (
                service.get_docker_tag("pre-edit", "test-project")
                == "testproject:preedit"
            )
            assert (
                service.get_docker_tag("post-edit", "test-project")
                == "testproject:postedit"
            )
            assert (
                service.get_docker_tag("post-edit2", "test-project")
                == "testproject:postedit"
            )

    def test_get_docker_tag_without_alias(self):
        """Test Docker tag generation for folders without aliases"""
        # Test without aliases
        docker_tag = self.project_service.get_docker_tag(
            "custom-folder", "test-project"
        )
        assert docker_tag == "testproject:customfolder"

        # Test with different combinations
        assert self.project_service.get_docker_tag("dev", "my-app") == "myapp:dev"
        assert (
            self.project_service.get_docker_tag("prod", "demo-project")
            == "demoproject:prod"
        )

    def test_get_docker_tag_special_characters(self):
        """Test Docker tag generation with special characters"""
        # Test that hyphens are removed
        assert (
            self.project_service.get_docker_tag("test-folder", "my-project")
            == "myproject:testfolder"
        )

        # Test with multiple hyphens
        assert self.project_service.get_docker_tag("a-b-c", "x-y-z") == "xyz:abc"

    def test_discover_projects(self):
        """Test project discovery in directory structure"""
        # Create test directory structure
        versions = ["pre-edit", "post-edit", "test-version"]
        projects = ["project1", "project2"]

        for version in versions:
            version_path = Path(self.temp_dir) / version
            version_path.mkdir(exist_ok=True)

            for project in projects:
                project_path = version_path / project
                project_path.mkdir(exist_ok=True)

                # Create some files to make it look like a real project
                (project_path / "README.md").write_text("# Test Project")
                (project_path / "test.py").write_text("print('test')")

        # Test discover_projects method if it exists
        # This is a placeholder as the actual method needs to be implemented

    def test_get_folder_sort_order(self):
        """Test getting sort order for folders"""
        # Test the get_folder_sort_order method if it exists
        # This would test the ordering of pre-edit, post-edit, etc.
        pass

    def test_edge_cases(self):
        """Test edge cases"""
        # Empty strings
        assert self.project_service.get_archive_name("", "") == "_.zip"
        assert self.project_service.get_docker_tag("", "") == ":"

        # Only hyphens
        assert self.project_service.get_archive_name("---", "---") == "_.zip"
        assert self.project_service.get_docker_tag("---", "---") == ":"

        # Unicode characters (should be handled gracefully)
        assert (
            self.project_service.get_archive_name("folder", "project-émoji")
            == "projectémoji_folder.zip"
        )

    def test_folder_alias_lookup_performance(self):
        """Test that folder alias lookup is efficient"""
        # Create a large FOLDER_ALIASES dictionary
        large_aliases = {
            f"alias{i}": [f"folder{i}-1", f"folder{i}-2"] for i in range(1000)
        }

        with patch("services.project_service.FOLDER_ALIASES", large_aliases):
            service = ProjectService()

            # Should still be fast even with many aliases
            import time

            start = time.time()

            for i in range(100):
                service.get_folder_alias(f"folder{i}-1")

            elapsed = time.time() - start
            assert elapsed < 0.1  # Should complete in less than 100ms

    def test_path_resolution(self):
        """Test that paths are properly resolved"""
        # Test with relative path
        service = ProjectService(".")
        assert service.root_dir.is_absolute()

        # Test with home directory
        service = ProjectService("~")
        assert service.root_dir.is_absolute()
        assert str(service.root_dir) != "~"

        # Test with non-existent path
        service = ProjectService("/non/existent/path")
        assert service.root_dir == Path("/non/existent/path").resolve()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
