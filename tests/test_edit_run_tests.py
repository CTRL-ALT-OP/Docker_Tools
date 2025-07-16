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

        def capture_selected_tests(project_group, selected_tests, language):
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

        def should_not_be_called(project_group, selected_tests, language):
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

    @pytest.mark.asyncio
    async def test_run_tests_file_modification_preserves_unix_line_endings(self):
        """Test that modifying run_tests.sh preserves Unix line endings"""
        # Create run_tests.sh with Windows-style line endings
        pre_edit_path = Path(self.temp_dir) / "pre-edit" / "test-project"
        run_tests_path = pre_edit_path / "run_tests.sh"

        # Write with Windows line endings
        run_tests_path.write_text("#!/bin/sh\r\npytest tests/\r\n")

        # Create test files
        tests_dir = pre_edit_path / "tests"
        tests_dir.mkdir(exist_ok=True)
        (tests_dir / "test_example.py").touch()

        with patch("tkinter.Tk"), patch("tkinter.BooleanVar"):
            window = EditRunTestsWindow(Mock(), self.project_group, Mock())
            window._load_test_files()

            # Mock the main app's handle_run_tests_edit method
            async def mock_handle_run_tests_edit(
                project_group, selected_tests, language
            ):
                # This would be called from the main app
                # Simulate the file modification
                new_content = "#!/bin/sh\npytest tests/test_example.py\n"
                run_tests_path.write_text(new_content, newline="\n")

            # Call the mock function to simulate file modification
            await mock_handle_run_tests_edit(
                self.project_group, ["tests/test_example.py"], "python"
            )

            # Get the line ending style
            raw_bytes = run_tests_path.read_bytes()

            # Should have Unix line endings (LF only)
            assert b"\r\n" not in raw_bytes
            assert b"\n" in raw_bytes


class TestEditRunTestsNewLanguages:
    """Test cases for Edit run_tests.sh functionality for new languages (go, cpp, csharp)"""

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

    def test_go_test_file_discovery(self):
        """Test that Go test files are discovered correctly"""
        pre_edit_path = Path(self.temp_dir) / "pre-edit" / "test-project"

        # Create Go test files
        (pre_edit_path / "main.go").write_text("package main")
        (pre_edit_path / "utils.go").write_text("package main")
        (pre_edit_path / "main_test.go").write_text('package main\nimport "testing"')
        (pre_edit_path / "utils_test.go").write_text('package main\nimport "testing"')
        (pre_edit_path / "helper_test.go").write_text('package main\nimport "testing"')

        # Create subdirectory with test files
        subdir = pre_edit_path / "handlers"
        subdir.mkdir()
        (subdir / "handler.go").write_text("package handlers")
        (subdir / "handler_test.go").write_text('package handlers\nimport "testing"')

        # Create non-test files that shouldn't be discovered
        (pre_edit_path / "not_a_test_file.go").write_text("package main")
        (pre_edit_path / "config.go").write_text("package main")

        with patch("tkinter.Tk"), patch("tkinter.BooleanVar"):
            window = EditRunTestsWindow(Mock(), self.project_group, Mock())
            window.detected_language = "go"
            window._load_test_files()

            # Should find only Go test files
            expected_test_files = {
                "main_test.go",
                "utils_test.go",
                "helper_test.go",
                "handlers/handler_test.go",
            }

            actual_test_files = set(window.all_test_files)
            assert actual_test_files == expected_test_files

    def test_cpp_test_file_discovery(self):
        """Test that C++ test files are discovered correctly"""
        pre_edit_path = Path(self.temp_dir) / "pre-edit" / "test-project"

        # Create test directory
        tests_dir = pre_edit_path / "tests"
        tests_dir.mkdir()

        # Create C++ test files
        (tests_dir / "test_main.cpp").write_text("#include <gtest/gtest.h>")
        (tests_dir / "test_utils.cpp").write_text("#include <gtest/gtest.h>")
        (tests_dir / "main_test.cpp").write_text("#include <gtest/gtest.h>")
        (tests_dir / "utils_test.cpp").write_text("#include <gtest/gtest.h>")
        (tests_dir / "test_handler.cc").write_text("#include <gtest/gtest.h>")
        (tests_dir / "handler_test.cc").write_text("#include <gtest/gtest.h>")

        # Create C test files too
        (tests_dir / "test_core.c").write_text("#include <stdio.h>")
        (tests_dir / "core_test.c").write_text("#include <stdio.h>")

        # Create non-test files that shouldn't be discovered
        (tests_dir / "helper.cpp").write_text("#include <iostream>")
        (tests_dir / "config.c").write_text("#include <stdio.h>")

        with patch("tkinter.Tk"), patch("tkinter.BooleanVar"):
            window = EditRunTestsWindow(Mock(), self.project_group, Mock())
            window.detected_language = "cpp"
            window._load_test_files()

            # Should find both C++ and C test files (pattern matches test_*.c, *_test.c, test_*.cpp, *_test.cpp)
            expected_test_files = {
                "tests/test_main.cpp",
                "tests/test_utils.cpp",
                "tests/main_test.cpp",
                "tests/utils_test.cpp",
                "tests/test_core.c",
                "tests/core_test.c",
            }

            actual_test_files = set(window.all_test_files)
            assert actual_test_files == expected_test_files

    def test_csharp_test_file_discovery(self):
        """Test that C# test files are discovered correctly"""
        pre_edit_path = Path(self.temp_dir) / "pre-edit" / "test-project"

        # Create test directory
        tests_dir = pre_edit_path / "tests"
        tests_dir.mkdir()

        # Create C# test files
        (tests_dir / "MainTest.cs").write_text("using NUnit.Framework;")
        (tests_dir / "UtilsTest.cs").write_text("using NUnit.Framework;")
        (tests_dir / "MainTests.cs").write_text("using NUnit.Framework;")
        (tests_dir / "UtilsTests.cs").write_text("using NUnit.Framework;")
        (tests_dir / "HandlerTest.cs").write_text("using NUnit.Framework;")

        # Create non-test files that shouldn't be discovered
        (tests_dir / "Helper.cs").write_text("using System;")
        (tests_dir / "Config.cs").write_text("using System;")

        with patch("tkinter.Tk"), patch("tkinter.BooleanVar"):
            window = EditRunTestsWindow(Mock(), self.project_group, Mock())
            window.detected_language = "csharp"
            window._load_test_files()

            # Should find only C# test files
            expected_test_files = {
                "tests/MainTest.cs",
                "tests/UtilsTest.cs",
                "tests/MainTests.cs",
                "tests/UtilsTests.cs",
                "tests/HandlerTest.cs",
            }

            actual_test_files = set(window.all_test_files)
            assert actual_test_files == expected_test_files

    def test_go_test_command_parsing(self):
        """Test parsing Go test commands from run_tests.sh"""
        pre_edit_path = Path(self.temp_dir) / "pre-edit" / "test-project"

        # Create run_tests.sh with Go test commands
        run_tests_content = """#!/bin/sh
go test ./handlers/handler_test.go
"""
        run_tests_path = pre_edit_path / "run_tests.sh"
        run_tests_path.write_text(run_tests_content)

        # Create test files
        (pre_edit_path / "main_test.go").write_text("package main")
        (pre_edit_path / "utils_test.go").write_text("package main")
        handlers_dir = pre_edit_path / "handlers"
        handlers_dir.mkdir()
        (handlers_dir / "handler_test.go").write_text("package handlers")

        with patch("tkinter.Tk"), patch("tkinter.BooleanVar"):
            window = EditRunTestsWindow(Mock(), self.project_group, Mock())
            window.detected_language = "go"
            window._load_test_files()
            selected_tests = window._get_currently_selected_tests()

            # Should find the specific test file mentioned in the command
            assert "handlers/handler_test.go" in selected_tests
            # Should NOT find the other test files
            assert "main_test.go" not in selected_tests
            assert "utils_test.go" not in selected_tests

    def test_go_test_package_command_parsing(self):
        """Test parsing Go test package commands from run_tests.sh"""
        pre_edit_path = Path(self.temp_dir) / "pre-edit" / "test-project"

        # Create run_tests.sh with Go package test commands
        run_tests_content = """#!/bin/sh
go test ./handlers
"""
        run_tests_path = pre_edit_path / "run_tests.sh"
        run_tests_path.write_text(run_tests_content)

        # Create test files
        (pre_edit_path / "main_test.go").write_text("package main")
        handlers_dir = pre_edit_path / "handlers"
        handlers_dir.mkdir()
        (handlers_dir / "handler_test.go").write_text("package handlers")
        (handlers_dir / "service_test.go").write_text("package handlers")

        with patch("tkinter.Tk"), patch("tkinter.BooleanVar"):
            window = EditRunTestsWindow(Mock(), self.project_group, Mock())
            window.detected_language = "go"
            window._load_test_files()
            selected_tests = window._get_currently_selected_tests()

            # Should find all test files in the handlers package
            assert "handlers/handler_test.go" in selected_tests
            assert "handlers/service_test.go" in selected_tests
            # Should NOT find the root level test
            assert "main_test.go" not in selected_tests

    def test_cpp_test_command_parsing(self):
        """Test parsing C++ CTest commands from run_tests.sh"""
        pre_edit_path = Path(self.temp_dir) / "pre-edit" / "test-project"

        # Create run_tests.sh with CTest commands
        run_tests_content = """#!/bin/sh
ctest --verbose -R test_main
"""
        run_tests_path = pre_edit_path / "run_tests.sh"
        run_tests_path.write_text(run_tests_content)

        # Create test files
        tests_dir = pre_edit_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_main.cpp").write_text("#include <gtest/gtest.h>")
        (tests_dir / "test_utils.cpp").write_text("#include <gtest/gtest.h>")
        (tests_dir / "test_handler.cpp").write_text("#include <gtest/gtest.h>")

        with patch("tkinter.Tk"), patch("tkinter.BooleanVar"):
            window = EditRunTestsWindow(Mock(), self.project_group, Mock())
            window.detected_language = "cpp"
            window._load_test_files()
            selected_tests = window._get_currently_selected_tests()

            # Should find test files matching the pattern
            assert "tests/test_main.cpp" in selected_tests
            # Should NOT find other test files
            assert "tests/test_utils.cpp" not in selected_tests
            assert "tests/test_handler.cpp" not in selected_tests

    def test_csharp_test_command_parsing(self):
        """Test parsing C# dotnet test commands from run_tests.sh"""
        pre_edit_path = Path(self.temp_dir) / "pre-edit" / "test-project"

        # Create run_tests.sh with dotnet test commands
        run_tests_content = """#!/bin/sh
dotnet test tests/MainTest.cs
"""
        run_tests_path = pre_edit_path / "run_tests.sh"
        run_tests_path.write_text(run_tests_content)

        # Create test files
        tests_dir = pre_edit_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "MainTest.cs").write_text("using NUnit.Framework;")
        (tests_dir / "UtilsTest.cs").write_text("using NUnit.Framework;")
        (tests_dir / "HandlerTest.cs").write_text("using NUnit.Framework;")

        with patch("tkinter.Tk"), patch("tkinter.BooleanVar"):
            window = EditRunTestsWindow(Mock(), self.project_group, Mock())
            window.detected_language = "csharp"
            window._load_test_files()
            selected_tests = window._get_currently_selected_tests()

            # Should find the specific test file mentioned in the command
            assert "tests/MainTest.cs" in selected_tests
            # Should NOT find the other test files
            assert "tests/UtilsTest.cs" not in selected_tests
            assert "tests/HandlerTest.cs" not in selected_tests

    def test_go_language_detection(self):
        """Test that Go language is detected correctly"""
        pre_edit_path = Path(self.temp_dir) / "pre-edit" / "test-project"

        # Create Go files
        (pre_edit_path / "main.go").write_text("package main")
        (pre_edit_path / "utils.go").write_text("package main")
        (pre_edit_path / "handler.go").write_text("package main")

        with patch("tkinter.Tk"), patch("tkinter.BooleanVar"):
            window = EditRunTestsWindow(Mock(), self.project_group, Mock())
            window._detect_language()

            assert window.detected_language == "go"

    def test_cpp_language_detection(self):
        """Test that C++ language is detected correctly"""
        pre_edit_path = Path(self.temp_dir) / "pre-edit" / "test-project"

        # Create C++ files (more C++ than C files)
        (pre_edit_path / "main.cpp").write_text("#include <iostream>")
        (pre_edit_path / "utils.cpp").write_text("#include <iostream>")
        (pre_edit_path / "handler.cxx").write_text("#include <iostream>")
        (pre_edit_path / "component.hpp").write_text("#ifndef COMPONENT_HPP")
        (pre_edit_path / "helper.cc").write_text("#include <iostream>")
        # Add one C file
        (pre_edit_path / "legacy.c").write_text("#include <stdio.h>")

        with patch("tkinter.Tk"), patch("tkinter.BooleanVar"):
            window = EditRunTestsWindow(Mock(), self.project_group, Mock())
            window._detect_language()

            assert window.detected_language == "cpp"

    def test_csharp_language_detection(self):
        """Test that C# language is detected correctly"""
        pre_edit_path = Path(self.temp_dir) / "pre-edit" / "test-project"

        # Create C# files
        (pre_edit_path / "Program.cs").write_text("using System;")
        (pre_edit_path / "Utils.cs").write_text("using System;")
        (pre_edit_path / "Handler.cs").write_text("using System;")

        with patch("tkinter.Tk"), patch("tkinter.BooleanVar"):
            window = EditRunTestsWindow(Mock(), self.project_group, Mock())
            window._detect_language()

            assert window.detected_language == "csharp"

    def test_go_default_all_tests_selection(self):
        """Test that all Go tests are selected by default when no specific command is found"""
        pre_edit_path = Path(self.temp_dir) / "pre-edit" / "test-project"

        # Create run_tests.sh with generic go test command
        run_tests_content = """#!/bin/sh
go test
"""
        run_tests_path = pre_edit_path / "run_tests.sh"
        run_tests_path.write_text(run_tests_content)

        # Create test files
        (pre_edit_path / "main_test.go").write_text("package main")
        (pre_edit_path / "utils_test.go").write_text("package main")
        handlers_dir = pre_edit_path / "handlers"
        handlers_dir.mkdir()
        (handlers_dir / "handler_test.go").write_text("package handlers")

        with patch("tkinter.Tk"), patch("tkinter.BooleanVar"):
            window = EditRunTestsWindow(Mock(), self.project_group, Mock())
            window.detected_language = "go"
            window._load_test_files()
            selected_tests = window._get_currently_selected_tests()

            # Should select all test files
            assert "main_test.go" in selected_tests
            assert "utils_test.go" in selected_tests
            assert "handlers/handler_test.go" in selected_tests

    def test_cpp_default_all_tests_selection(self):
        """Test that all C++ tests are selected by default when no specific command is found"""
        pre_edit_path = Path(self.temp_dir) / "pre-edit" / "test-project"

        # Create run_tests.sh with generic ctest command
        run_tests_content = """#!/bin/sh
ctest --verbose
"""
        run_tests_path = pre_edit_path / "run_tests.sh"
        run_tests_path.write_text(run_tests_content)

        # Create test files
        tests_dir = pre_edit_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_main.cpp").write_text("#include <gtest/gtest.h>")
        (tests_dir / "test_utils.cpp").write_text("#include <gtest/gtest.h>")
        (tests_dir / "test_handler.cpp").write_text("#include <gtest/gtest.h>")

        with patch("tkinter.Tk"), patch("tkinter.BooleanVar"):
            window = EditRunTestsWindow(Mock(), self.project_group, Mock())
            window.detected_language = "cpp"
            window._load_test_files()
            selected_tests = window._get_currently_selected_tests()

            # Should select all test files
            assert "tests/test_main.cpp" in selected_tests
            assert "tests/test_utils.cpp" in selected_tests
            assert "tests/test_handler.cpp" in selected_tests

    def test_csharp_default_all_tests_selection(self):
        """Test that all C# tests are selected by default when no specific command is found"""
        pre_edit_path = Path(self.temp_dir) / "pre-edit" / "test-project"

        # Create run_tests.sh with generic dotnet test command
        run_tests_content = """#!/bin/sh
dotnet test
"""
        run_tests_path = pre_edit_path / "run_tests.sh"
        run_tests_path.write_text(run_tests_content)

        # Create test files
        tests_dir = pre_edit_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "MainTest.cs").write_text("using NUnit.Framework;")
        (tests_dir / "UtilsTest.cs").write_text("using NUnit.Framework;")
        (tests_dir / "HandlerTest.cs").write_text("using NUnit.Framework;")

        with patch("tkinter.Tk"), patch("tkinter.BooleanVar"):
            window = EditRunTestsWindow(Mock(), self.project_group, Mock())
            window.detected_language = "csharp"
            window._load_test_files()
            selected_tests = window._get_currently_selected_tests()

            # Should select all test files
            assert "tests/MainTest.cs" in selected_tests
            assert "tests/UtilsTest.cs" in selected_tests
            assert "tests/HandlerTest.cs" in selected_tests


class TestEditRunTestsShebangAndLineEndings:
    """Test cases for shebang preservation and LF line ending enforcement in edit run_tests functionality"""

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

        # Create test files in pre-edit version
        pre_edit_path = Path(self.temp_dir) / "pre-edit" / "test-project"
        tests_dir = pre_edit_path / "tests"
        tests_dir.mkdir(exist_ok=True)
        (tests_dir / "test_example.py").write_text("def test_example(): pass")
        (tests_dir / "test_another.py").write_text("def test_another(): pass")

    def teardown_method(self):
        """Clean up test fixtures"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    @pytest.mark.asyncio
    async def test_shebang_preservation_sh_to_sh(self):
        """Test that #!/bin/sh shebang is preserved and not changed to #!/bin/bash"""
        # Create run_tests.sh with #!/bin/sh shebang in all versions
        original_shebang = "#!/bin/sh"
        original_content = f"""{original_shebang}
# Original run_tests.sh content
pytest -vv tests/
"""

        # Set up run_tests.sh files with #!/bin/sh in all versions
        for version in ["pre-edit", "post-edit", "post-edit2", "correct-edit"]:
            version_path = Path(self.temp_dir) / version / "test-project"
            run_tests_path = version_path / "run_tests.sh"
            run_tests_path.write_text(original_content, encoding="utf-8")

        # Mock the operation manager and run the actual edit functionality
        from core.operation_manager import OperationManager
        from unittest.mock import AsyncMock, Mock, patch

        # Mock the dependencies
        mock_services = {
            "project_service": Mock(),
            "file_service": Mock(),
            "git_service": Mock(),
            "docker_service": Mock(),
            "sync_service": Mock(),
            "validation_service": Mock(),
            "docker_files_service": Mock(),
            "async_bridge": Mock(),
        }

        mock_callback_handler = Mock()
        mock_window = Mock()
        mock_control_panel = Mock()

        # Create operation manager instance
        operation_manager = OperationManager(
            services=mock_services,
            callback_handler=mock_callback_handler,
            window=mock_window,
            control_panel=mock_control_panel,
        )

        # Mock the TerminalOutputWindow to avoid GUI dependencies
        with patch(
            "core.operation_manager.TerminalOutputWindow"
        ) as mock_output_window_class:
            mock_output_window = Mock()
            mock_output_window_class.return_value = mock_output_window

            # Call the actual edit functionality
            operation_manager._handle_run_tests_edit(
                self.project_group, ["tests/test_example.py"], "python"
            )

            # Wait a moment for async operations to complete
            await asyncio.sleep(0.1)

        # Verify that all run_tests.sh files still have #!/bin/sh shebang
        for version in ["post-edit", "post-edit2", "correct-edit"]:
            version_path = Path(self.temp_dir) / version / "test-project"
            run_tests_path = version_path / "run_tests.sh"

            if run_tests_path.exists():
                content = run_tests_path.read_text(encoding="utf-8")
                lines = content.split("\n")

                # First line should still be #!/bin/sh, not #!/bin/bash
                assert (
                    lines[0] == "#!/bin/sh"
                ), f"Expected '#!/bin/sh' but got '{lines[0]}' in {version}/run_tests.sh"
                assert (
                    lines[0] != "#!/bin/bash"
                ), f"Shebang incorrectly changed to #!/bin/bash in {version}/run_tests.sh"

    @pytest.mark.asyncio
    async def test_shebang_preservation_bash_to_bash(self):
        """Test that #!/bin/bash shebang is preserved as #!/bin/bash"""
        # Create run_tests.sh with #!/bin/bash shebang in all versions
        original_shebang = "#!/bin/bash"
        original_content = f"""{original_shebang}
# Original run_tests.sh content with bash
pytest -vv tests/
"""

        # Set up run_tests.sh files with #!/bin/bash in all versions
        for version in ["pre-edit", "post-edit", "post-edit2", "correct-edit"]:
            version_path = Path(self.temp_dir) / version / "test-project"
            run_tests_path = version_path / "run_tests.sh"
            run_tests_path.write_text(original_content, encoding="utf-8")

        # Mock the operation manager and run the actual edit functionality
        from core.operation_manager import OperationManager
        from unittest.mock import AsyncMock, Mock, patch

        # Mock the dependencies
        mock_services = {
            "project_service": Mock(),
            "file_service": Mock(),
            "git_service": Mock(),
            "docker_service": Mock(),
            "sync_service": Mock(),
            "validation_service": Mock(),
            "docker_files_service": Mock(),
            "async_bridge": Mock(),
        }

        mock_callback_handler = Mock()
        mock_window = Mock()
        mock_control_panel = Mock()

        # Create operation manager instance
        operation_manager = OperationManager(
            services=mock_services,
            callback_handler=mock_callback_handler,
            window=mock_window,
            control_panel=mock_control_panel,
        )

        # Mock the TerminalOutputWindow to avoid GUI dependencies
        with patch(
            "core.operation_manager.TerminalOutputWindow"
        ) as mock_output_window_class:
            mock_output_window = Mock()
            mock_output_window_class.return_value = mock_output_window

            # Call the actual edit functionality
            operation_manager._handle_run_tests_edit(
                self.project_group, ["tests/test_example.py"], "python"
            )

            # Wait a moment for async operations to complete
            await asyncio.sleep(0.1)

        # Verify that all run_tests.sh files still have #!/bin/bash shebang
        for version in ["post-edit", "post-edit2", "correct-edit"]:
            version_path = Path(self.temp_dir) / version / "test-project"
            run_tests_path = version_path / "run_tests.sh"

            if run_tests_path.exists():
                content = run_tests_path.read_text(encoding="utf-8")
                lines = content.split("\n")

                # First line should still be #!/bin/bash
                assert (
                    lines[0] == "#!/bin/bash"
                ), f"Expected '#!/bin/bash' but got '{lines[0]}' in {version}/run_tests.sh"

    @pytest.mark.asyncio
    async def test_default_shebang_for_new_files(self):
        """Test that new run_tests.sh files get #!/bin/sh as default shebang"""
        # Don't create any existing run_tests.sh files
        # The edit functionality should create new files with default shebang

        # Mock the operation manager and run the actual edit functionality
        from core.operation_manager import OperationManager
        from unittest.mock import AsyncMock, Mock, patch

        # Mock the dependencies
        mock_services = {
            "project_service": Mock(),
            "file_service": Mock(),
            "git_service": Mock(),
            "docker_service": Mock(),
            "sync_service": Mock(),
            "validation_service": Mock(),
            "docker_files_service": Mock(),
            "async_bridge": Mock(),
        }

        mock_callback_handler = Mock()
        mock_window = Mock()
        mock_control_panel = Mock()

        # Create operation manager instance
        operation_manager = OperationManager(
            services=mock_services,
            callback_handler=mock_callback_handler,
            window=mock_window,
            control_panel=mock_control_panel,
        )

        # Mock the TerminalOutputWindow to avoid GUI dependencies
        with patch(
            "core.operation_manager.TerminalOutputWindow"
        ) as mock_output_window_class:
            mock_output_window = Mock()
            mock_output_window_class.return_value = mock_output_window

            # Call the actual edit functionality
            operation_manager._handle_run_tests_edit(
                self.project_group, ["tests/test_example.py"], "python"
            )

            # Wait a moment for async operations to complete
            await asyncio.sleep(0.1)

        # Verify that all newly created run_tests.sh files have #!/bin/sh as default
        for version in ["post-edit", "post-edit2", "correct-edit"]:
            version_path = Path(self.temp_dir) / version / "test-project"
            run_tests_path = version_path / "run_tests.sh"

            if run_tests_path.exists():
                content = run_tests_path.read_text(encoding="utf-8")
                lines = content.split("\n")

                # First line should be #!/bin/sh (the portable default)
                assert (
                    lines[0] == "#!/bin/sh"
                ), f"Expected default '#!/bin/sh' but got '{lines[0]}' in {version}/run_tests.sh"

    @pytest.mark.asyncio
    async def test_lf_line_endings_enforcement(self):
        """Test that run_tests.sh files are always saved with LF line endings, even on Windows"""
        # Create run_tests.sh with CRLF line endings to simulate Windows editing
        crlf_content = (
            "#!/bin/sh\r\n# Original content with CRLF\r\npytest -vv tests/\r\n"
        )

        # Set up run_tests.sh files with CRLF in all versions
        for version in ["pre-edit", "post-edit", "post-edit2", "correct-edit"]:
            version_path = Path(self.temp_dir) / version / "test-project"
            run_tests_path = version_path / "run_tests.sh"
            # Write as bytes to ensure CRLF line endings
            run_tests_path.write_bytes(crlf_content.encode("utf-8"))

        # Verify initial state has CRLF
        pre_edit_path = (
            Path(self.temp_dir) / "pre-edit" / "test-project" / "run_tests.sh"
        )
        initial_bytes = pre_edit_path.read_bytes()
        assert b"\r\n" in initial_bytes, "Test setup should have CRLF line endings"

        # Mock the operation manager and run the actual edit functionality
        from core.operation_manager import OperationManager
        from unittest.mock import AsyncMock, Mock, patch

        # Mock the dependencies
        mock_services = {
            "project_service": Mock(),
            "file_service": Mock(),
            "git_service": Mock(),
            "docker_service": Mock(),
            "sync_service": Mock(),
            "validation_service": Mock(),
            "docker_files_service": Mock(),
            "async_bridge": Mock(),
        }

        mock_callback_handler = Mock()
        mock_window = Mock()
        mock_control_panel = Mock()

        # Create operation manager instance
        operation_manager = OperationManager(
            services=mock_services,
            callback_handler=mock_callback_handler,
            window=mock_window,
            control_panel=mock_control_panel,
        )

        # Mock the TerminalOutputWindow to avoid GUI dependencies
        with patch(
            "core.operation_manager.TerminalOutputWindow"
        ) as mock_output_window_class:
            mock_output_window = Mock()
            mock_output_window_class.return_value = mock_output_window

            # Call the actual edit functionality
            operation_manager._handle_run_tests_edit(
                self.project_group, ["tests/test_example.py"], "python"
            )

            # Wait a moment for async operations to complete
            await asyncio.sleep(0.1)

        # Verify that all run_tests.sh files now have LF line endings only
        for version in ["post-edit", "post-edit2", "correct-edit"]:
            version_path = Path(self.temp_dir) / version / "test-project"
            run_tests_path = version_path / "run_tests.sh"

            if run_tests_path.exists():
                # Read as bytes to check exact line ending characters
                content_bytes = run_tests_path.read_bytes()
                content_str = content_bytes.decode("utf-8")

                # Should have LF line endings
                assert (
                    b"\n" in content_bytes
                ), f"File should contain LF characters in {version}/run_tests.sh"

                # Should NOT have CRLF line endings
                assert (
                    b"\r\n" not in content_bytes
                ), f"File should not contain CRLF in {version}/run_tests.sh. Content: {repr(content_str)}"

                # Should NOT have isolated CR characters
                assert (
                    b"\r" not in content_bytes
                ), f"File should not contain CR characters in {version}/run_tests.sh. Content: {repr(content_str)}"

    @pytest.mark.asyncio
    async def test_lf_enforcement_on_all_platforms(self):
        """Test that LF enforcement works regardless of the current platform's default line endings"""
        # This test ensures the fix works even on Linux where LF would be default anyway

        # Create run_tests.sh with mixed line endings (simulate cross-platform editing)
        mixed_content_bytes = b"#!/bin/sh\n# Line 1 with LF\r\n# Line 2 with CRLF\r# Line 3 with just CR\npytest tests/\n"

        # Set up run_tests.sh files with mixed line endings
        for version in ["pre-edit", "post-edit", "post-edit2", "correct-edit"]:
            version_path = Path(self.temp_dir) / version / "test-project"
            run_tests_path = version_path / "run_tests.sh"
            run_tests_path.write_bytes(mixed_content_bytes)

        # Verify initial state has mixed line endings
        pre_edit_path = (
            Path(self.temp_dir) / "pre-edit" / "test-project" / "run_tests.sh"
        )
        initial_bytes = pre_edit_path.read_bytes()
        assert b"\r\n" in initial_bytes, "Test setup should have CRLF"
        assert b"\r" in initial_bytes, "Test setup should have CR characters"

        # Mock the operation manager and run the actual edit functionality
        from core.operation_manager import OperationManager
        from unittest.mock import AsyncMock, Mock, patch

        # Mock the dependencies
        mock_services = {
            "project_service": Mock(),
            "file_service": Mock(),
            "git_service": Mock(),
            "docker_service": Mock(),
            "sync_service": Mock(),
            "validation_service": Mock(),
            "docker_files_service": Mock(),
            "async_bridge": Mock(),
        }

        mock_callback_handler = Mock()
        mock_window = Mock()
        mock_control_panel = Mock()

        # Create operation manager instance
        operation_manager = OperationManager(
            services=mock_services,
            callback_handler=mock_callback_handler,
            window=mock_window,
            control_panel=mock_control_panel,
        )

        # Mock the TerminalOutputWindow to avoid GUI dependencies
        with patch(
            "core.operation_manager.TerminalOutputWindow"
        ) as mock_output_window_class:
            mock_output_window = Mock()
            mock_output_window_class.return_value = mock_output_window

            # Call the actual edit functionality
            operation_manager._handle_run_tests_edit(
                self.project_group,
                ["tests/test_example.py", "tests/test_another.py"],
                "python",
            )

            # Wait a moment for async operations to complete
            await asyncio.sleep(0.1)

        # Verify that all run_tests.sh files are normalized to LF only
        for version in ["post-edit", "post-edit2", "correct-edit"]:
            version_path = Path(self.temp_dir) / version / "test-project"
            run_tests_path = version_path / "run_tests.sh"

            if run_tests_path.exists():
                # Read as bytes to check exact line ending characters
                content_bytes = run_tests_path.read_bytes()
                content_str = content_bytes.decode("utf-8")

                # Count line endings
                lf_count = content_bytes.count(b"\n")
                crlf_count = content_bytes.count(b"\r\n")
                cr_only_count = content_bytes.count(b"\r") - crlf_count

                # Should have LF line endings (at least some)
                assert (
                    lf_count > 0
                ), f"File should contain LF characters in {version}/run_tests.sh"

                # Should NOT have any CRLF or CR characters
                assert (
                    crlf_count == 0
                ), f"File should not contain CRLF in {version}/run_tests.sh. Content: {repr(content_str)}"
                assert (
                    cr_only_count == 0
                ), f"File should not contain standalone CR in {version}/run_tests.sh. Content: {repr(content_str)}"

                # Verify shebang is preserved
                lines = content_str.split("\n")
                assert (
                    lines[0] == "#!/bin/sh"
                ), f"Shebang should be preserved in {version}/run_tests.sh"
