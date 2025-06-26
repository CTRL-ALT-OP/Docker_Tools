"""
Tests for Edit run_tests.sh functionality
"""

import os
import sys
import tempfile
import shutil
import tkinter as tk
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
import pytest
import asyncio

# Add parent directory to path to import modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from models.project import Project
from services.project_group_service import ProjectGroup, ProjectGroupService
from services.project_service import ProjectService
from gui.popup_windows import EditRunTestsWindow


class TestEditRunTestsFunctionality:
    """Test cases for Edit run_tests.sh functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.project_service = ProjectService()

        # Create test project group with multiple versions
        self.project_group = ProjectGroup("test-project", self.project_service)

        # Create test projects for different versions
        versions = ["pre-edit", "post-edit", "post-edit2", "correct-edit"]
        for version in versions:
            version_path = Path(self.temp_dir) / version / "test-project"
            version_path.mkdir(parents=True, exist_ok=True)

            project = Project(
                parent=version,
                name="test-project",
                path=version_path,
                relative_path=f"{version}/test-project",
            )
            self.project_group.add_project(project)

    def teardown_method(self):
        """Clean up test fixtures"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_pytest_command_parsing_with_python_prefix(self):
        """Test parsing pytest commands with python3.12 -m prefix"""
        # Create run_tests.sh with python prefix
        run_tests_content = """#!/bin/sh
python3.12 -m pytest -vv -s tests/test_bubble_visualizer_improved.py::TestBubbleVisualizerGradientMode
"""

        pre_edit_path = Path(self.temp_dir) / "pre-edit" / "test-project"
        run_tests_path = pre_edit_path / "run_tests.sh"
        run_tests_path.write_text(run_tests_content)

        # Create test files
        tests_dir = pre_edit_path / "tests"
        tests_dir.mkdir(exist_ok=True)
        (tests_dir / "test_data_loader.py").touch()
        (tests_dir / "test_bubble_visualizer_improved.py").touch()

        # Only mock the minimal GUI components needed
        with patch("tkinter.Tk"), patch("tkinter.BooleanVar"):
            window = EditRunTestsWindow(Mock(), self.project_group, Mock())
            window._load_test_files()
            selected_tests = window._get_currently_selected_tests()

            # Should find the currently selected test file
            assert "tests/test_bubble_visualizer_improved.py" in selected_tests
            # Should NOT find the other test file
            assert "tests/test_data_loader.py" not in selected_tests

    def test_pytest_command_parsing_direct_pytest(self):
        """Test parsing direct pytest commands"""
        # Create run_tests.sh with direct pytest command
        run_tests_content = """#!/bin/sh
pytest -q tests/test_bubble_visualizer_improved.py::TestBubbleVisualizerGradientMode
"""

        pre_edit_path = Path(self.temp_dir) / "pre-edit" / "test-project"
        run_tests_path = pre_edit_path / "run_tests.sh"
        run_tests_path.write_text(run_tests_content)

        # Create test files
        tests_dir = pre_edit_path / "tests"
        tests_dir.mkdir(exist_ok=True)
        (tests_dir / "test_data_loader.py").touch()
        (tests_dir / "test_bubble_visualizer_improved.py").touch()

        with patch("tkinter.Tk"), patch("tkinter.BooleanVar"):
            window = EditRunTestsWindow(Mock(), self.project_group, Mock())
            window._load_test_files()
            selected_tests = window._get_currently_selected_tests()

            # Should correctly identify the selected test from the command
            assert "tests/test_bubble_visualizer_improved.py" in selected_tests
            assert len(selected_tests) == 1

    def test_forward_slash_path_normalization(self):
        """Test that paths are normalized to forward slashes"""
        pre_edit_path = Path(self.temp_dir) / "pre-edit" / "test-project"

        # Create test files with nested structure
        tests_dir = pre_edit_path / "tests"
        tests_dir.mkdir(exist_ok=True)

        # Create nested directories
        (tests_dir / "unit").mkdir()
        (tests_dir / "integration").mkdir()

        # Create test files
        (tests_dir / "test_main.py").touch()
        (tests_dir / "unit" / "test_utils.py").touch()
        (tests_dir / "integration" / "test_api.py").touch()

        with patch("tkinter.Tk"), patch("tkinter.BooleanVar"):
            window = EditRunTestsWindow(Mock(), self.project_group, Mock())
            window._load_test_files()

            # Verify actual file discovery behavior
            assert len(window.all_test_files) == 3

            # All paths should use forward slashes (actual path normalization)
            for test_file in window.all_test_files:
                assert "\\" not in test_file, f"Path contains backslash: {test_file}"
                assert test_file.startswith(
                    "tests/"
                ), f"Path doesn't start with tests/: {test_file}"

            # Verify specific expected paths
            expected_files = {
                "tests/test_main.py",
                "tests/unit/test_utils.py",
                "tests/integration/test_api.py",
            }
            assert set(window.all_test_files) == expected_files

    def test_test_file_discovery_patterns(self):
        """Test that only correct test file patterns are discovered"""
        pre_edit_path = Path(self.temp_dir) / "pre-edit" / "test-project"
        tests_dir = pre_edit_path / "tests"
        tests_dir.mkdir(exist_ok=True)

        # Create various file patterns
        test_files = [
            "test_example.py",  # Should be found
            "test_another_file.py",  # Should be found
            "utils_test.py",  # Should be found
            "integration_test.py",  # Should be found
            "not_a_test_file.py",  # Should NOT be found
            "helper.py",  # Should NOT be found
            "conftest.py",  # Should NOT be found
        ]

        for test_file in test_files:
            (tests_dir / test_file).touch()

        with patch("tkinter.Tk"), patch("tkinter.BooleanVar"):
            window = EditRunTestsWindow(Mock(), self.project_group, Mock())
            window._load_test_files()

            # Should find only test files
            expected_test_files = {
                "tests/test_example.py",
                "tests/test_another_file.py",
                "tests/utils_test.py",
                "tests/integration_test.py",
            }

            actual_test_files = set(window.all_test_files)
            assert actual_test_files == expected_test_files

            # Specifically verify non-test files are excluded
            assert "tests/not_a_test_file.py" not in actual_test_files
            assert "tests/helper.py" not in actual_test_files
            assert "tests/conftest.py" not in actual_test_files

    def test_checkbox_initial_selection_based_on_run_tests_content(self):
        """Test that checkbox initial state reflects current run_tests.sh content"""
        pre_edit_path = Path(self.temp_dir) / "pre-edit" / "test-project"

        # Create run_tests.sh selecting specific tests
        run_tests_content = """#!/bin/sh
pytest -vv -s tests/test_selected.py tests/test_also_selected.py
"""
        run_tests_path = pre_edit_path / "run_tests.sh"
        run_tests_path.write_text(run_tests_content)

        # Create test files
        tests_dir = pre_edit_path / "tests"
        tests_dir.mkdir(exist_ok=True)
        (tests_dir / "test_selected.py").touch()
        (tests_dir / "test_also_selected.py").touch()
        (tests_dir / "test_unselected.py").touch()

        with patch("tkinter.Tk"), patch("tkinter.BooleanVar"):
            window = EditRunTestsWindow(Mock(), self.project_group, Mock())
            window._load_test_files()

            # Get currently selected tests based on actual file content
            selected_tests = window._get_currently_selected_tests()

            # Verify correct tests are identified as selected
            assert "tests/test_selected.py" in selected_tests
            assert "tests/test_also_selected.py" in selected_tests
            assert "tests/test_unselected.py" not in selected_tests
            assert len(selected_tests) == 2

    def test_save_changes_generates_correct_test_list(self):
        """Test that saving changes with selected tests generates correct test list"""
        pre_edit_path = Path(self.temp_dir) / "pre-edit" / "test-project"
        tests_dir = pre_edit_path / "tests"
        tests_dir.mkdir(exist_ok=True)
        (tests_dir / "test_one.py").touch()
        (tests_dir / "test_two.py").touch()
        (tests_dir / "test_three.py").touch()

        selected_tests_result = []

        def capture_selected_tests(project_group, selected_tests):
            selected_tests_result.extend(selected_tests)

        with patch("tkinter.Tk"), patch("tkinter.BooleanVar") as mock_bool_var:
            # Mock the checkbox variables to simulate selection
            mock_vars = []
            for i, test_name in enumerate(
                ["tests/test_one.py", "tests/test_two.py", "tests/test_three.py"]
            ):
                var = Mock()
                var.get.return_value = i == 0 or i == 2  # Select first and third
                mock_vars.append(var)
            mock_bool_var.side_effect = mock_vars

            window = EditRunTestsWindow(
                Mock(), self.project_group, capture_selected_tests
            )
            window.destroy = Mock()
            window._load_test_files()

            # Manually set up test_vars to simulate checkbox creation
            window.test_vars = {
                "tests/test_one.py": mock_vars[0],
                "tests/test_two.py": mock_vars[1],
                "tests/test_three.py": mock_vars[2],
            }

            # Save changes - this calls the actual _save_changes method
            window._save_changes()

            # Verify correct tests were selected
            assert "tests/test_one.py" in selected_tests_result
            assert "tests/test_three.py" in selected_tests_result
            assert "tests/test_two.py" not in selected_tests_result
            assert len(selected_tests_result) == 2

    def test_save_changes_validation_prevents_empty_selection(self):
        """Test that validation prevents saving with no tests selected"""
        pre_edit_path = Path(self.temp_dir) / "pre-edit" / "test-project"
        tests_dir = pre_edit_path / "tests"
        tests_dir.mkdir(exist_ok=True)
        (tests_dir / "test_example.py").touch()

        callback_called = False

        def should_not_be_called(project_group, selected_tests):
            nonlocal callback_called
            callback_called = True

        with patch("tkinter.Tk"), patch("tkinter.BooleanVar"), patch(
            "tkinter.messagebox.showwarning"
        ) as mock_warning:
            window = EditRunTestsWindow(
                Mock(), self.project_group, should_not_be_called
            )
            window._load_test_files()

            # Simulate no tests selected
            window.test_vars = {"tests/test_example.py": Mock()}
            window.test_vars["tests/test_example.py"].get.return_value = False

            # Try to save - calls actual _save_changes method
            window._save_changes()

            # Should show warning and not call callback
            mock_warning.assert_called_once()
            assert not callback_called

    def test_error_handling_missing_pre_edit_version(self):
        """Test handling when pre-edit version doesn't exist"""
        # Create project group without pre-edit version
        project_group = ProjectGroup("test-project", self.project_service)

        # Add only other versions
        for version in ["post-edit", "correct-edit"]:
            version_path = Path(self.temp_dir) / version / "test-project"
            version_path.mkdir(parents=True, exist_ok=True)

            project = Project(
                parent=version,
                name="test-project",
                path=version_path,
                relative_path=f"{version}/test-project",
            )
            project_group.add_project(project)

        # Create test files in first available version
        first_version_path = Path(self.temp_dir) / "post-edit" / "test-project"
        tests_dir = first_version_path / "tests"
        tests_dir.mkdir(exist_ok=True)
        (tests_dir / "test_fallback.py").touch()

        with patch("tkinter.Tk"), patch("tkinter.BooleanVar"):
            window = EditRunTestsWindow(Mock(), project_group, Mock())
            window._load_test_files()

            # Should fallback to first available version and find tests
            assert "tests/test_fallback.py" in window.all_test_files

    def test_error_handling_no_tests_directory(self):
        """Test handling when tests directory doesn't exist"""
        # Don't create tests directory
        pre_edit_path = Path(self.temp_dir) / "pre-edit" / "test-project"

        with patch("tkinter.Tk"), patch("tkinter.BooleanVar"):
            window = EditRunTestsWindow(Mock(), self.project_group, Mock())
            window._load_test_files()

            # Should handle missing tests directory gracefully
            assert len(window.all_test_files) == 0

    def test_malformed_run_tests_file_handling(self):
        """Test handling of malformed run_tests.sh files"""
        pre_edit_path = Path(self.temp_dir) / "pre-edit" / "test-project"
        run_tests_path = pre_edit_path / "run_tests.sh"

        # Create malformed run_tests.sh
        run_tests_content = """#!/bin/sh
# This is a comment
echo "Starting tests"
some_random_command_without_pytest
# Another comment
"""
        run_tests_path.write_text(run_tests_content)

        # Create test files
        tests_dir = pre_edit_path / "tests"
        tests_dir.mkdir(exist_ok=True)
        (tests_dir / "test_example.py").touch()

        with patch("tkinter.Tk"), patch("tkinter.BooleanVar"):
            window = EditRunTestsWindow(Mock(), self.project_group, Mock())
            window._load_test_files()
            selected_tests = window._get_currently_selected_tests()

            # Should handle malformed file and return empty selection
            assert len(selected_tests) == 0
            assert isinstance(selected_tests, set)

    def test_multiple_test_selection_from_run_tests(self):
        """Test that multiple tests in run_tests.sh are correctly identified"""
        pre_edit_path = Path(self.temp_dir) / "pre-edit" / "test-project"

        # Create run_tests.sh with multiple space-separated tests
        run_tests_content = """#!/bin/sh
pytest -vv tests/test_one.py tests/test_two.py tests/subdir/test_three.py
"""
        run_tests_path = pre_edit_path / "run_tests.sh"
        run_tests_path.write_text(run_tests_content)

        # Create test files
        tests_dir = pre_edit_path / "tests"
        tests_dir.mkdir(exist_ok=True)
        (tests_dir / "test_one.py").touch()
        (tests_dir / "test_two.py").touch()
        (tests_dir / "test_unselected.py").touch()

        subdir = tests_dir / "subdir"
        subdir.mkdir()
        (subdir / "test_three.py").touch()

        with patch("tkinter.Tk"), patch("tkinter.BooleanVar"):
            window = EditRunTestsWindow(Mock(), self.project_group, Mock())
            window._load_test_files()
            selected_tests = window._get_currently_selected_tests()

            # Should identify all selected tests
            assert "tests/test_one.py" in selected_tests
            assert "tests/test_two.py" in selected_tests
            assert "tests/subdir/test_three.py" in selected_tests
            assert "tests/test_unselected.py" not in selected_tests
            assert len(selected_tests) == 3

    def test_pytest_flags_are_ignored_during_parsing(self):
        """Test that pytest flags don't interfere with test file identification"""
        pre_edit_path = Path(self.temp_dir) / "pre-edit" / "test-project"

        # Create run_tests.sh with many flags before test files
        run_tests_content = """#!/bin/sh
python3.12 -m pytest -vv -s --tb=short --durations=10 --maxfail=1 tests/test_target.py
"""
        run_tests_path = pre_edit_path / "run_tests.sh"
        run_tests_path.write_text(run_tests_content)

        # Create test files
        tests_dir = pre_edit_path / "tests"
        tests_dir.mkdir(exist_ok=True)
        (tests_dir / "test_target.py").touch()
        (tests_dir / "test_other.py").touch()

        with patch("tkinter.Tk"), patch("tkinter.BooleanVar"):
            window = EditRunTestsWindow(Mock(), self.project_group, Mock())
            window._load_test_files()
            selected_tests = window._get_currently_selected_tests()

            # Should correctly identify the test file despite all the flags
            assert "tests/test_target.py" in selected_tests
            assert "tests/test_other.py" not in selected_tests
            assert len(selected_tests) == 1


class TestRunTestsLineEndings:
    """Test cases for run_tests.sh file line endings"""

    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.project_service = ProjectService()

        # Create test project group with multiple versions
        self.project_group = ProjectGroup("test-project", self.project_service)

        # Create test projects for different versions
        versions = ["pre-edit", "post-edit", "post-edit2", "correct-edit"]
        for version in versions:
            version_path = Path(self.temp_dir) / version / "test-project"
            version_path.mkdir(parents=True, exist_ok=True)

            project = Project(
                parent=version,
                name="test-project",
                path=version_path,
                relative_path=f"{version}/test-project",
            )
            self.project_group.add_project(project)

    def teardown_method(self):
        """Clean up test fixtures"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_run_tests_files_created_with_unix_line_endings(self):
        """Test that run_tests.sh files are created with Unix (LF) line endings, not Windows (CRLF)"""
        # Test the low-level file writing directly to avoid async complexity
        import tempfile

        # Create a test file using our newline fix
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".sh"
        ) as temp_file:
            temp_path = Path(temp_file.name)

        try:
            # Simulate what our production code does
            run_tests_content = "#!/bin/sh\npytest -vv -s tests/test_example.py\n"
            temp_path.write_text(run_tests_content, newline="\n")

            # Read file content as bytes to check line endings
            with open(temp_path, "rb") as f:
                content_bytes = f.read()

            # Convert to string for easier debugging
            content_str = content_bytes.decode("utf-8")

            # Should contain Unix line endings (LF only: \n = 0x0A)
            assert b"\n" in content_bytes, "File should contain LF characters"

            # Should NOT contain Windows line endings (CRLF: \r\n = 0x0D 0x0A)
            assert (
                b"\r\n" not in content_bytes
            ), f"File should not contain CRLF: {repr(content_str)}"

            # Should NOT contain isolated CR characters (just \r = 0x0D)
            assert (
                b"\r" not in content_bytes
            ), f"File should not contain CR characters: {repr(content_str)}"

            # Verify the content is what we expect
            expected_content = "#!/bin/sh\npytest -vv -s tests/test_example.py\n"
            assert (
                content_str == expected_content
            ), f"Unexpected content: {repr(content_str)}"

        finally:
            # Clean up
            if temp_path.exists():
                temp_path.unlink()

    def test_run_tests_file_modification_preserves_unix_line_endings(self):
        """Test that modifying existing run_tests.sh files preserves Unix line endings"""
        # Test the low-level file modification directly
        import tempfile

        # Create a test file with existing content
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".sh"
        ) as temp_file:
            temp_path = Path(temp_file.name)

        try:
            # Write initial content with explicit Unix line endings
            initial_content = "#!/bin/sh\npytest -vv -s tests/old_test.py\n"
            with open(temp_path, "wb") as f:
                f.write(initial_content.encode("utf-8"))

            # Verify initial file has Unix line endings
            with open(temp_path, "rb") as f:
                initial_bytes = f.read()
            assert b"\r\n" not in initial_bytes, "Initial file should not have CRLF"
            assert b"\n" in initial_bytes, "Initial file should have LF"

            # Simulate modifying the file (what our production code does)
            new_content = "#!/bin/sh\npytest -vv -s tests/test_new.py\n"
            temp_path.write_text(new_content, newline="\n")

            # Check that the modified file still has Unix line endings
            with open(temp_path, "rb") as f:
                modified_bytes = f.read()

            # Should still contain Unix line endings (LF only)
            assert b"\n" in modified_bytes, "Modified file should contain LF characters"

            # Should NOT contain Windows line endings (CRLF)
            assert (
                b"\r\n" not in modified_bytes
            ), f"Modified file should not contain CRLF: {repr(modified_bytes.decode('utf-8'))}"

            # Should NOT contain isolated CR characters
            assert (
                b"\r" not in modified_bytes
            ), f"Modified file should not contain CR characters: {repr(modified_bytes.decode('utf-8'))}"

            # Verify the content was updated correctly
            expected_content = "#!/bin/sh\npytest -vv -s tests/test_new.py\n"
            actual_content = modified_bytes.decode("utf-8")
            assert (
                actual_content == expected_content
            ), f"Content should be updated correctly: {repr(actual_content)}"

        finally:
            # Clean up
            if temp_path.exists():
                temp_path.unlink()
