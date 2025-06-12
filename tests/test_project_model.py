"""
Tests for Project model - Tests for project data model
"""

import os
import sys
from pathlib import Path
import pytest
from dataclasses import FrozenInstanceError

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.project import Project


class TestProject:
    """Test cases for Project model"""

    def test_project_creation(self):
        """Test creating a Project instance"""
        parent = "pre-edit"
        name = "test-project"
        path = Path("/home/user/projects/pre-edit/test-project")
        relative_path = "pre-edit/test-project"

        project = Project(
            parent=parent, name=name, path=path, relative_path=relative_path
        )

        assert project.parent == parent
        assert project.name == name
        assert project.path == path
        assert project.relative_path == relative_path

    def test_display_name_property(self):
        """Test the display_name property"""
        project = Project(
            parent="pre-edit",
            name="test-project",
            path=Path("/workspace/pre-edit/test-project"),
            relative_path="pre-edit/test-project",
        )

        assert project.display_name == "test-project"

        # Test with different name - create new instance since Project is frozen
        project2 = Project(
            parent="pre-edit",
            name="another-project",
            path=Path("/workspace/pre-edit/another-project"),
            relative_path="pre-edit/another-project",
        )
        assert project2.display_name == "another-project"

    def test_full_path_property(self):
        """Test the full_path property"""
        path = Path("/home/user/workspace/pre-edit/project1")
        project = Project(
            parent="pre-edit",
            name="project1",
            path=path,
            relative_path="pre-edit/project1",
        )

        assert project.full_path == str(path)
        # Use os.path.normpath to handle cross-platform paths
        expected_path = os.path.normpath("/home/user/workspace/pre-edit/project1")
        assert os.path.normpath(project.full_path) == expected_path

    def test_str_representation(self):
        """Test string representation of Project"""
        project = Project(
            parent="correct-edit",
            name="demo-app",
            path=Path("/workspace/correct-edit/demo-app"),
            relative_path="correct-edit/demo-app",
        )

        assert str(project) == "correct-edit/demo-app"

    def test_project_with_windows_paths(self):
        """Test Project with Windows-style paths"""
        path = Path("C:\\Users\\Developer\\projects\\pre-edit\\app")
        project = Project(
            parent="pre-edit", name="app", path=path, relative_path="pre-edit\\app"
        )

        assert project.path == path
        assert project.full_path == str(path)

    def test_project_equality(self):
        """Test equality comparison between projects"""
        path1 = Path("/projects/pre-edit/app1")
        project1 = Project(
            parent="pre-edit", name="app1", path=path1, relative_path="pre-edit/app1"
        )

        project2 = Project(
            parent="pre-edit", name="app1", path=path1, relative_path="pre-edit/app1"
        )

        # Dataclasses provide equality comparison
        assert project1 == project2

        # Different projects should not be equal
        project3 = Project(
            parent="post-edit",
            name="app1",
            path=Path("/projects/post-edit/app1"),
            relative_path="post-edit/app1",
        )

        assert project1 != project3

    def test_project_with_special_characters(self):
        """Test Project with special characters in names"""
        project = Project(
            parent="pre-edit",
            name="project_with_underscores",
            path=Path("/path/to/project_with_underscores"),
            relative_path="pre-edit/project_with_underscores",
        )

        assert project.name == "project_with_underscores"
        assert project.display_name == "project_with_underscores"

    def test_project_with_dots_in_name(self):
        """Test Project with dots in name (like version numbers)"""
        project = Project(
            parent="v1.0.0",
            name="app.v2.1",
            path=Path("/versions/v1.0.0/app.v2.1"),
            relative_path="v1.0.0/app.v2.1",
        )

        assert project.name == "app.v2.1"
        assert str(project) == "v1.0.0/app.v2.1"

    def test_project_immutability(self):
        """Test that Project fields cannot be modified (dataclass is frozen)"""
        project = Project(
            parent="pre-edit",
            name="test",
            path=Path("/test"),
            relative_path="pre-edit/test",
        )

        # Should NOT be able to modify fields (frozen dataclass)
        with pytest.raises(FrozenInstanceError):
            project.name = "modified"

    def test_project_path_types(self):
        """Test Project accepts different path types"""
        # String path (will be converted to Path by caller)
        path_str = "/home/user/project"
        project = Project(
            parent="pre-edit",
            name="project",
            path=Path(path_str),
            relative_path="pre-edit/project",
        )

        assert isinstance(project.path, Path)
        # Use os.path.normpath for cross-platform comparison
        assert os.path.normpath(str(project.path)) == os.path.normpath(path_str)

    def test_empty_values(self):
        """Test Project with empty values"""
        project = Project(parent="", name="", path=Path("."), relative_path="")

        assert project.parent == ""
        assert project.name == ""
        assert project.display_name == ""
        assert str(project) == "/"
        assert project.relative_path == ""

    def test_project_hash(self):
        """Test that Project instances are hashable"""
        project = Project(
            parent="pre-edit",
            name="app",
            path=Path("/path/to/app"),
            relative_path="pre-edit/app",
        )

        # Should be hashable (can be used in sets/dicts)
        project_set = {project}
        assert project in project_set

        # Create project dict
        project_dict = {project: "value"}
        assert project_dict[project] == "value"

    def test_project_with_relative_paths(self):
        """Test Project with relative paths"""
        project = Project(
            parent="pre-edit",
            name="myapp",
            path=Path("./pre-edit/myapp"),
            relative_path="pre-edit/myapp",
        )

        # Path should be stored as given (relative)
        assert not project.path.is_absolute()
        assert project.relative_path == "pre-edit/myapp"

    def test_project_repr(self):
        """Test Project repr for debugging"""
        project = Project(
            parent="post-edit",
            name="test-app",
            path=Path("/workspace/post-edit/test-app"),
            relative_path="post-edit/test-app",
        )

        repr_str = repr(project)
        # Dataclass provides a useful repr by default
        assert "Project(" in repr_str
        assert "parent='post-edit'" in repr_str
        assert "name='test-app'" in repr_str

    def test_project_with_unicode(self):
        """Test Project with unicode characters"""
        project = Project(
            parent="préedit",
            name="application_café",
            path=Path("/projects/préedit/application_café"),
            relative_path="préedit/application_café",
        )

        assert project.parent == "préedit"
        assert project.name == "application_café"
        assert project.display_name == "application_café"
        assert str(project) == "préedit/application_café"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
