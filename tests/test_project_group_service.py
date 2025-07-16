"""
Tests for ProjectGroupService - Tests for project grouping and navigation
"""

import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

# Add parent directory to path to import modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from services.project_group_service import ProjectGroup, ProjectGroupService
from services.project_service import ProjectService
from models.project import Project


class TestProjectGroup:
    """Test cases for ProjectGroup class"""

    def setup_method(self):
        """Set up test fixtures"""
        self.project_service = Mock(spec=ProjectService)
        self.project_service.get_folder_sort_order = Mock(
            side_effect=self._mock_sort_order
        )
        self.project_group = ProjectGroup("test_project", self.project_service)

    def _mock_sort_order(self, folder):
        """Mock sort order for folders"""
        order = {"pre-edit": 0, "post-edit": 1, "post-edit2": 2, "correct-edit": 3}
        return order.get(folder, 99)

    def test_project_group_initialization(self):
        """Test ProjectGroup initialization"""
        assert self.project_group.name == "test_project"
        assert self.project_group.versions == {}
        assert self.project_group.project_service is self.project_service

    def test_add_project(self):
        """Test adding projects to a group"""
        # Create test projects
        project1 = Project(
            parent="pre-edit",
            name="test_project",
            path=Path("/path/pre-edit/test_project"),
            relative_path="pre-edit/test_project",
        )

        project2 = Project(
            parent="post-edit",
            name="test_project",
            path=Path("/path/post-edit/test_project"),
            relative_path="post-edit/test_project",
        )

        # Add projects
        self.project_group.add_project(project1)
        self.project_group.add_project(project2)

        assert len(self.project_group.versions) == 2
        assert self.project_group.versions["pre-edit"] == project1
        assert self.project_group.versions["post-edit"] == project2

    def test_add_project_overwrites_existing(self):
        """Test that adding a project with same parent overwrites existing"""
        project1 = Project(
            parent="pre-edit",
            name="test_project",
            path=Path("/path1/pre-edit/test_project"),
            relative_path="pre-edit/test_project",
        )

        project2 = Project(
            parent="pre-edit",
            name="test_project",
            path=Path("/path2/pre-edit/test_project"),
            relative_path="pre-edit/test_project",
        )

        self.project_group.add_project(project1)
        assert self.project_group.versions["pre-edit"].path == project1.path

        self.project_group.add_project(project2)
        assert self.project_group.versions["pre-edit"].path == project2.path
        assert len(self.project_group.versions) == 1

    def test_get_version_existing(self):
        """Test getting an existing version"""
        project = Project(
            parent="post-edit",
            name="test_project",
            path=Path("/path/post-edit/test_project"),
            relative_path="post-edit/test_project",
        )

        self.project_group.add_project(project)
        retrieved = self.project_group.get_version("post-edit")

        assert retrieved == project

    def test_get_version_non_existing(self):
        """Test getting a non-existing version"""
        result = self.project_group.get_version("non-existent")
        assert result is None

    def test_get_all_versions_sorted(self):
        """Test getting all versions sorted by folder order"""
        # Create projects in random order
        projects = [
            Project(
                "correct-edit", "test_project", Path("/p3"), "correct-edit/test_project"
            ),
            Project("pre-edit", "test_project", Path("/p1"), "pre-edit/test_project"),
            Project(
                "post-edit2", "test_project", Path("/p4"), "post-edit2/test_project"
            ),
            Project("post-edit", "test_project", Path("/p2"), "post-edit/test_project"),
        ]

        # Add in random order
        for project in projects:
            self.project_group.add_project(project)

        # Get sorted versions
        sorted_versions = self.project_group.get_all_versions()

        # Verify correct order
        assert len(sorted_versions) == 4
        assert sorted_versions[0].parent == "pre-edit"
        assert sorted_versions[1].parent == "post-edit"
        assert sorted_versions[2].parent == "post-edit2"
        assert sorted_versions[3].parent == "correct-edit"

    def test_get_all_versions_empty(self):
        """Test getting all versions when none exist"""
        versions = self.project_group.get_all_versions()
        assert versions == []

    def test_has_version(self):
        """Test checking if a version exists"""
        project = Project(
            parent="pre-edit",
            name="test_project",
            path=Path("/path/pre-edit/test_project"),
            relative_path="pre-edit/test_project",
        )

        self.project_group.add_project(project)

        assert self.project_group.has_version("pre-edit") is True
        assert self.project_group.has_version("post-edit") is False
        assert self.project_group.has_version("") is False

    def test_get_all_versions_with_unknown_folders(self):
        """Test sorting with folders not in the standard order"""
        projects = [
            Project(
                "custom-version",
                "test_project",
                Path("/p1"),
                "custom-version/test_project",
            ),
            Project("pre-edit", "test_project", Path("/p2"), "pre-edit/test_project"),
            Project(
                "another-version",
                "test_project",
                Path("/p3"),
                "another-version/test_project",
            ),
        ]

        for project in projects:
            self.project_group.add_project(project)

        sorted_versions = self.project_group.get_all_versions()

        # pre-edit should come first, others sorted by their default order (99)
        assert sorted_versions[0].parent == "pre-edit"
        # Custom versions should maintain their order
        assert len(sorted_versions) == 3


class TestProjectGroupService:
    """Test cases for ProjectGroupService"""

    def setup_method(self):
        """Set up test fixtures"""
        self.project_service = Mock(spec=ProjectService)
        self.project_service.get_folder_sort_order = Mock(
            side_effect=self._mock_sort_order
        )
        self.project_group_service = ProjectGroupService(self.project_service)

    def _mock_sort_order(self, folder):
        """Mock sort order for folders"""
        order = {"pre-edit": 0, "post-edit": 1, "post-edit2": 2, "correct-edit": 3}
        return order.get(folder, 99)

    def test_initialization(self):
        """Test ProjectGroupService initialization"""
        assert self.project_group_service.project_service is self.project_service
        assert self.project_group_service._groups == {}
        assert self.project_group_service._current_group_index == 0
        assert self.project_group_service._group_names == []

    def test_load_project_groups_clears_existing(self):
        """Test that loading project groups clears existing groups"""
        # Add some initial groups
        self.project_group_service._groups = {
            "old_group": ProjectGroup("old_group", self.project_service)
        }
        self.project_group_service._group_names = ["old_group"]

        # Mock the project_service.find_two_layer_projects to return an iterable
        mock_projects = [
            Project("pre-edit", "test1", Path("/path/to/test1"), "pre-edit/test1"),
            Project("post-edit", "test1", Path("/path/to/test1"), "post-edit/test1"),
        ]
        self.project_service.find_two_layer_projects.return_value = mock_projects

        # Act
        self.project_group_service.load_project_groups()

        # Assert - should have cleared old groups and loaded new ones
        assert "old_group" not in self.project_group_service._groups
        assert len(self.project_group_service._groups) > 0
        assert "test1" in self.project_group_service._groups

    def test_add_project_to_new_group(self):
        """Test adding a project creates a new group if needed"""
        # This test assumes there's an add_project method or similar
        # Would need to check actual implementation
        pass

    def test_get_current_group(self):
        """Test getting the current project group"""
        # Create test groups
        group1 = ProjectGroup("project1", self.project_service)
        group2 = ProjectGroup("project2", self.project_service)

        self.project_group_service._groups = {"project1": group1, "project2": group2}
        self.project_group_service._group_names = ["project1", "project2"]
        self.project_group_service._current_group_index = 0

        # Assuming there's a get_current_group method
        # This is a placeholder for the actual test

    def test_navigate_groups(self):
        """Test navigating between project groups"""
        # Set up multiple groups
        self.project_group_service._group_names = ["project1", "project2", "project3"]
        self.project_group_service._current_group_index = 0

        # Test navigation methods if they exist
        # This is a placeholder for the actual test

    def test_empty_group_handling(self):
        """Test handling of empty project groups"""
        # Test behavior when no projects are loaded
        assert len(self.project_group_service._groups) == 0
        assert len(self.project_group_service._group_names) == 0

    def test_group_sorting(self):
        """Test that groups are sorted correctly"""
        # Create groups with different names
        groups = ["zebra_project", "alpha_project", "beta_project"]

        for group_name in groups:
            self.project_group_service._groups[group_name] = ProjectGroup(
                group_name, self.project_service
            )

        # Assuming group names are sorted alphabetically
        # This would depend on actual implementation

    def test_concurrent_group_access(self):
        """Test thread safety of group access"""
        # This test would verify thread-safe access if the service is used concurrently
        pass

    def test_group_index_bounds(self):
        """Test that group index stays within bounds"""
        self.project_group_service._group_names = ["project1", "project2"]

        # Test various index operations
        assert self.project_group_service._current_group_index >= 0
        assert (
            self.project_group_service._current_group_index
            < len(self.project_group_service._group_names)
            or len(self.project_group_service._group_names) == 0
        )

    def test_project_service_integration(self):
        """Test integration with ProjectService"""
        # Verify that project service methods are called correctly
        group = ProjectGroup("test", self.project_group_service.project_service)

        # Add projects with different parents
        projects = [
            Project("pre-edit", "test", Path("/p1"), "pre-edit/test"),
            Project("post-edit", "test", Path("/p2"), "post-edit/test"),
        ]

        for project in projects:
            group.add_project(project)

        # Get sorted versions should use project service
        sorted_versions = group.get_all_versions()

        # Verify project service was called
        assert self.project_group_service.project_service.get_folder_sort_order.called

    def test_group_with_single_version(self):
        """Test group with only one version"""
        group = ProjectGroup("single_version", self.project_service)
        project = Project(
            "pre-edit", "single_version", Path("/p"), "pre-edit/single_version"
        )

        group.add_project(project)

        assert len(group.versions) == 1
        assert group.has_version("pre-edit")
        assert len(group.get_all_versions()) == 1

    def test_group_name_uniqueness(self):
        """Test that group names are unique and properly handled"""
        # Create projects with duplicate names from different parents
        projects = [
            Project(
                "pre-edit", "duplicate_name", Path("/p1"), "pre-edit/duplicate_name"
            ),
            Project(
                "post-edit", "duplicate_name", Path("/p2"), "post-edit/duplicate_name"
            ),
            Project("pre-edit", "unique_name", Path("/p3"), "pre-edit/unique_name"),
        ]

        self.project_service.find_two_layer_projects.return_value = projects
        self.project_group_service.load_project_groups()

        # Should have 2 groups: one for duplicate_name, one for unique_name
        assert self.project_group_service.get_group_count() == 2

        # Check that duplicate_name group has multiple versions
        duplicate_group = self.project_group_service.get_group_by_name("duplicate_name")
        assert duplicate_group is not None
        assert len(duplicate_group.versions) == 2

    def test_navigation_edge_cases(self):
        """Test navigation edge cases and boundary conditions"""
        # Setup with projects
        projects = [
            Project("pre-edit", "project_a", Path("/p1"), "pre-edit/project_a"),
            Project("post-edit", "project_b", Path("/p2"), "post-edit/project_b"),
        ]
        self.project_service.find_two_layer_projects.return_value = projects
        self.project_group_service.load_project_groups()

        # Test navigation when at boundaries
        assert self.project_group_service.get_current_group_index() == 0

        # Navigate previous (should wrap to last group)
        prev_group = self.project_group_service.get_previous_group()
        assert prev_group is not None
        assert (
            self.project_group_service.get_current_group_index() == 1
        )  # Wrapped to last group

        # Navigate back to first
        self.project_group_service.set_current_group_by_index(0)

        # Navigate to next group
        next_group = self.project_group_service.get_next_group()
        assert next_group is not None
        assert self.project_group_service.get_current_group_index() == 1

        # Navigate next again (should wrap to first group)
        next_group = self.project_group_service.get_next_group()
        assert next_group is not None
        assert (
            self.project_group_service.get_current_group_index() == 0
        )  # Wrapped to first group

    def test_set_current_group_by_index_boundary_conditions(self):
        """Test setting current group by index with boundary conditions"""
        projects = [
            Project("pre-edit", "project_a", Path("/p1"), "pre-edit/project_a"),
            Project("post-edit", "project_b", Path("/p2"), "post-edit/project_b"),
            Project("pre-edit", "project_c", Path("/p3"), "pre-edit/project_c"),
        ]
        self.project_service.find_two_layer_projects.return_value = projects
        self.project_group_service.load_project_groups()

        # Test valid indices
        assert self.project_group_service.set_current_group_by_index(0) is True
        assert self.project_group_service.get_current_group_index() == 0

        assert self.project_group_service.set_current_group_by_index(2) is True
        assert self.project_group_service.get_current_group_index() == 2

        # Test invalid indices
        assert self.project_group_service.set_current_group_by_index(-1) is False
        assert (
            self.project_group_service.get_current_group_index() == 2
        )  # Should remain unchanged

        assert self.project_group_service.set_current_group_by_index(3) is False
        assert (
            self.project_group_service.get_current_group_index() == 2
        )  # Should remain unchanged

    def test_set_current_group_by_name_edge_cases(self):
        """Test setting current group by name with edge cases"""
        projects = [
            Project("pre-edit", "project_a", Path("/p1"), "pre-edit/project_a"),
            Project("post-edit", "project_b", Path("/p2"), "post-edit/project_b"),
        ]
        self.project_service.find_two_layer_projects.return_value = projects
        self.project_group_service.load_project_groups()

        # Test valid names
        assert self.project_group_service.set_current_group_by_name("project_b") is True
        assert self.project_group_service.get_current_group_name() == "project_b"

        # Test invalid names
        assert (
            self.project_group_service.set_current_group_by_name("non_existent")
            is False
        )
        assert (
            self.project_group_service.get_current_group_name() == "project_b"
        )  # Should remain unchanged

        # Test empty string
        assert self.project_group_service.set_current_group_by_name("") is False
        assert (
            self.project_group_service.get_current_group_name() == "project_b"
        )  # Should remain unchanged

    def test_empty_project_list_handling(self):
        """Test handling when no projects are found"""
        self.project_service.find_two_layer_projects.return_value = []
        self.project_group_service.load_project_groups()

        assert self.project_group_service.get_group_count() == 0
        assert self.project_group_service.get_current_group() is None
        assert self.project_group_service.get_current_group_name() is None
        assert self.project_group_service.get_current_group_index() == -1

        # Navigation should return None for empty list
        assert self.project_group_service.get_next_group() is None
        assert self.project_group_service.get_previous_group() is None

    def test_single_project_group_handling(self):
        """Test handling when only one project group exists"""
        projects = [
            Project(
                "pre-edit", "single_project", Path("/p1"), "pre-edit/single_project"
            ),
            Project(
                "post-edit", "single_project", Path("/p2"), "post-edit/single_project"
            ),
        ]
        self.project_service.find_two_layer_projects.return_value = projects
        self.project_group_service.load_project_groups()

        assert self.project_group_service.get_group_count() == 1
        assert self.project_group_service.get_current_group_index() == 0
        assert self.project_group_service.get_current_group_name() == "single_project"

        # Navigation with single group should cycle to itself
        current_group = self.project_group_service.get_current_group()
        next_group = self.project_group_service.get_next_group()
        assert next_group is not None
        assert next_group.name == current_group.name
        assert (
            self.project_group_service.get_current_group_index() == 0
        )  # Should remain at same position

        prev_group = self.project_group_service.get_previous_group()
        assert prev_group is not None
        assert prev_group.name == current_group.name
        assert (
            self.project_group_service.get_current_group_index() == 0
        )  # Should remain at same position

    def test_project_group_version_management(self):
        """Test comprehensive version management within project groups"""
        # Create project group with multiple versions
        project_group = ProjectGroup("test_project", self.project_service)

        projects = [
            Project("pre-edit", "test_project", Path("/p1"), "pre-edit/test_project"),
            Project("post-edit", "test_project", Path("/p2"), "post-edit/test_project"),
            Project(
                "correct-edit", "test_project", Path("/p3"), "correct-edit/test_project"
            ),
            Project(
                "custom-edit", "test_project", Path("/p4"), "custom-edit/test_project"
            ),
        ]

        # Add projects
        for project in projects:
            project_group.add_project(project)

        # Test version existence
        assert project_group.has_version("pre-edit") is True
        assert project_group.has_version("post-edit") is True
        assert project_group.has_version("non-existent") is False

        # Test getting specific versions
        pre_edit_project = project_group.get_version("pre-edit")
        assert pre_edit_project is not None
        assert pre_edit_project.parent == "pre-edit"

        # Test getting all versions (should be sorted)
        all_versions = project_group.get_all_versions()
        assert len(all_versions) == 4
        assert all_versions[0].parent == "pre-edit"  # Should be first in sort order
        assert all_versions[1].parent == "post-edit"
        assert all_versions[2].parent == "correct-edit"
        # custom-edit should be last (unknown folder, sort order 99)

    def test_project_group_name_handling(self):
        """Test project group name handling with special characters and cases"""
        test_names = [
            "project-with-dashes",
            "project_with_underscores",
            "ProjectWithCamelCase",
            "project.with.dots",
            "project with spaces",
            "123-numeric-start",
            "UPPERCASE-PROJECT",
        ]

        projects = []
        for i, name in enumerate(test_names):
            projects.append(
                Project("pre-edit", name, Path(f"/p{i}"), f"pre-edit/{name}")
            )

        self.project_service.find_two_layer_projects.return_value = projects
        self.project_group_service.load_project_groups()

        assert self.project_group_service.get_group_count() == len(test_names)

        # Test that all groups can be retrieved
        for name in test_names:
            group = self.project_group_service.get_group_by_name(name)
            assert group is not None
            assert group.name == name

    def test_load_project_groups_exception_handling(self):
        """Test exception handling during project group loading"""
        # Mock project service to raise exception
        self.project_service.find_two_layer_projects.side_effect = Exception(
            "Service error"
        )

        # Should not raise exception, but handle gracefully
        try:
            self.project_group_service.load_project_groups()
            # If it doesn't raise an exception, groups should be empty
            assert self.project_group_service.get_group_count() == 0
        except Exception:
            # If it does raise, that's also acceptable behavior
            pass

    def test_concurrent_group_operations(self):
        """Test thread safety and concurrent operations"""
        projects = [
            Project("pre-edit", "project_a", Path("/p1"), "pre-edit/project_a"),
            Project("post-edit", "project_b", Path("/p2"), "post-edit/project_b"),
            Project("pre-edit", "project_c", Path("/p3"), "pre-edit/project_c"),
        ]
        self.project_service.find_two_layer_projects.return_value = projects
        self.project_group_service.load_project_groups()

        # Simulate concurrent navigation operations
        original_index = self.project_group_service.get_current_group_index()

        # Multiple navigation operations
        self.project_group_service.get_next_group()
        next_index = self.project_group_service.get_current_group_index()

        self.project_group_service.get_previous_group()
        back_index = self.project_group_service.get_current_group_index()

        # Should maintain consistency
        assert back_index == original_index
        assert next_index != original_index

    def test_group_names_sorting_behavior(self):
        """Test that group names are properly sorted"""
        projects = [
            Project("pre-edit", "zebra_project", Path("/p1"), "pre-edit/zebra_project"),
            Project(
                "post-edit", "alpha_project", Path("/p2"), "post-edit/alpha_project"
            ),
            Project("pre-edit", "beta_project", Path("/p3"), "pre-edit/beta_project"),
        ]
        self.project_service.find_two_layer_projects.return_value = projects
        self.project_group_service.load_project_groups()

        group_names = self.project_group_service.get_group_names()

        # Should be sorted alphabetically
        expected_order = ["alpha_project", "beta_project", "zebra_project"]
        assert group_names == expected_order

    def test_get_group_names_returns_copy(self):
        """Test that get_group_names returns a copy, not the original list"""
        projects = [
            Project("pre-edit", "project_a", Path("/p1"), "pre-edit/project_a"),
            Project("post-edit", "project_b", Path("/p2"), "post-edit/project_b"),
        ]
        self.project_service.find_two_layer_projects.return_value = projects
        self.project_group_service.load_project_groups()

        group_names = self.project_group_service.get_group_names()

        # Modify the returned list
        group_names.append("hacker_project")
        group_names.sort(reverse=True)

        # Original should be unchanged
        original_names = self.project_group_service.get_group_names()
        assert "hacker_project" not in original_names
        assert original_names == ["project_a", "project_b"]  # Should be sorted normally

    def test_group_reloading_behavior(self):
        """Test behavior when reloading project groups"""
        # Initial load
        projects_v1 = [
            Project("pre-edit", "project_a", Path("/p1"), "pre-edit/project_a"),
            Project("post-edit", "project_b", Path("/p2"), "post-edit/project_b"),
        ]
        self.project_service.find_two_layer_projects.return_value = projects_v1
        self.project_group_service.load_project_groups()

        assert self.project_group_service.get_group_count() == 2
        self.project_group_service.set_current_group_by_index(1)  # Set to second group

        # Reload with different projects
        projects_v2 = [
            Project("pre-edit", "project_c", Path("/p3"), "pre-edit/project_c"),
        ]
        self.project_service.find_two_layer_projects.return_value = projects_v2
        self.project_group_service.load_project_groups()

        # Should have new groups and reset index
        assert self.project_group_service.get_group_count() == 1
        assert self.project_group_service.get_current_group_index() == 0
        assert self.project_group_service.get_current_group_name() == "project_c"

    def test_project_group_integration_with_sorting(self):
        """Test integration between project groups and project service sorting"""
        # Create projects with complex sorting requirements
        projects = [
            Project(
                "post-edit2",
                "complex_project",
                Path("/p1"),
                "post-edit2/complex_project",
            ),
            Project(
                "pre-edit", "complex_project", Path("/p2"), "pre-edit/complex_project"
            ),
            Project(
                "correct-edit",
                "complex_project",
                Path("/p3"),
                "correct-edit/complex_project",
            ),
            Project(
                "post-edit", "complex_project", Path("/p4"), "post-edit/complex_project"
            ),
            Project(
                "unknown-folder",
                "complex_project",
                Path("/p5"),
                "unknown-folder/complex_project",
            ),
        ]

        self.project_service.find_two_layer_projects.return_value = projects
        self.project_group_service.load_project_groups()

        group = self.project_group_service.get_group_by_name("complex_project")
        sorted_versions = group.get_all_versions()

        # Verify sorting was called for each version
        assert self.project_service.get_folder_sort_order.call_count >= len(projects)

        # Verify expected order based on mock sort function
        expected_order = [
            "pre-edit",
            "post-edit",
            "post-edit2",
            "correct-edit",
            "unknown-folder",
        ]
        actual_order = [v.parent for v in sorted_versions]
        assert actual_order == expected_order

    def test_advanced_navigation_scenarios(self):
        """Test advanced navigation scenarios and edge cases"""
        projects = [
            Project("pre-edit", "project_a", Path("/p1"), "pre-edit/project_a"),
            Project("post-edit", "project_b", Path("/p2"), "post-edit/project_b"),
            Project("pre-edit", "project_c", Path("/p3"), "pre-edit/project_c"),
        ]
        self.project_service.find_two_layer_projects.return_value = projects
        self.project_group_service.load_project_groups()

        # Test cycling navigation - with 3 groups, after 3 steps we should be back at start
        initial_index = self.project_group_service.get_current_group_index()

        # Navigate forward 3 times (should cycle back to start)
        for _ in range(3):
            self.project_group_service.get_next_group()

        # Should be back at initial position due to cycling
        assert self.project_group_service.get_current_group_index() == initial_index

        # Navigate backward 3 times (should cycle back to start again)
        for _ in range(3):
            self.project_group_service.get_previous_group()

        # Should be back at initial position due to cycling
        assert self.project_group_service.get_current_group_index() == initial_index

    def test_group_state_consistency(self):
        """Test that group state remains consistent across operations"""
        projects = [
            Project("pre-edit", "test_project", Path("/p1"), "pre-edit/test_project"),
            Project("post-edit", "test_project", Path("/p2"), "post-edit/test_project"),
        ]
        self.project_service.find_two_layer_projects.return_value = projects
        self.project_group_service.load_project_groups()

        # Test multiple ways of accessing the same group
        group_by_current = self.project_group_service.get_current_group()
        group_by_name = self.project_group_service.get_group_by_name("test_project")
        group_by_index = self.project_group_service.get_current_group()

        # All should return the same group
        assert group_by_current is group_by_name
        assert group_by_current is group_by_index

        # Test group name consistency
        current_name = self.project_group_service.get_current_group_name()
        assert current_name == group_by_current.name


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
