"""
Tests for Archive Button Color Change Functionality
Tests the integration of archive button color management with file monitoring service
"""

import os
import sys
import time
import tempfile
import shutil
import asyncio
from pathlib import Path
import pytest
from unittest.mock import Mock, patch, MagicMock, call
from unittest.mock import ANY

# Add parent directory to path to import modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from models.project import Project
from services.file_monitor_service import FileMonitorService, file_monitor
from gui.main_window import MainWindow
from config.config import get_config

COLORS = get_config().gui.colors
BUTTON_STYLES = get_config().gui.button_styles


class TestArchiveButtonColorFunctionality:
    """Test archive button color change functionality"""

    def _assert_button_config_call(self, mock_button, **kwargs):
        """Helper method to check for either config or configure method call"""
        try:
            mock_button.config.assert_called_with(**kwargs)
        except (AttributeError, AssertionError):
            try:
                mock_button.configure.assert_called_with(**kwargs)
            except (AttributeError, AssertionError):
                # If both fail, provide a clear error message
                raise AssertionError(
                    f"Neither config nor configure was called with {kwargs}. "
                    f"config calls: {getattr(mock_button.config, 'call_args_list', 'not available')}, "
                    f"configure calls: {getattr(mock_button.configure, 'call_args_list', 'not available')}"
                )

    def _assert_button_has_calls(self, mock_button, expected_calls, any_order=False):
        """Helper method to check for either config or configure method calls in sequence"""
        try:
            mock_button.config.assert_has_calls(expected_calls, any_order=any_order)
        except (AttributeError, AssertionError):
            try:
                mock_button.configure.assert_has_calls(
                    expected_calls, any_order=any_order
                )
            except (AttributeError, AssertionError):
                # If both fail, provide a clear error message
                raise AssertionError(
                    f"Neither config nor configure was called with expected sequence {expected_calls}. "
                    f"config calls: {getattr(mock_button.config, 'call_args_list', 'not available')}, "
                    f"configure calls: {getattr(mock_button.configure, 'call_args_list', 'not available')}"
                )

    def _get_button_call_count(self, mock_button):
        """Helper method to get call count from either config or configure"""
        config_count = getattr(mock_button.config, "call_count", 0)
        configure_count = getattr(mock_button.configure, "call_count", 0)
        return max(config_count, configure_count)

    def setup_method(self):
        """Set up test environment before each test"""
        self.temp_dir = tempfile.mkdtemp(prefix="archive_button_test_")
        self.temp_path = Path(self.temp_dir)

        # Create test project structures
        self.pre_edit_project = self._create_test_project("pre-edit", "test-project")
        self.post_edit_project = self._create_test_project("post-edit", "test-project")
        self.other_project = self._create_test_project("pre-edit", "other-project")

    def teardown_method(self):
        """Clean up after each test"""
        # Stop all monitoring to prevent interference between tests
        file_monitor.stop_all_monitoring()
        time.sleep(0.1)  # Give threads time to stop

        # Clean up temp directory
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def _create_test_project(self, parent: str, name: str) -> Project:
        """Create a test project with directory structure"""
        project_path = self.temp_path / parent / name
        project_path.mkdir(parents=True, exist_ok=True)

        # Create some initial files
        (project_path / "main.py").write_text("print('hello')")
        (project_path / "README.md").write_text("# Test Project")

        # Create subdirectories
        (project_path / "src").mkdir(exist_ok=True)
        (project_path / "src" / "module.py").write_text("def func(): pass")

        return Project(
            parent=parent,
            name=name,
            path=project_path,
            relative_path=f"{parent}/{name}",
        )

    @patch("tkinter.Tk")
    @patch("tkinter.Button")
    def test_button_turns_green_when_archived(self, mock_button_class, mock_tk):
        """Test that the archive button turns green when project is archived"""
        # Arrange
        mock_button = Mock()
        mock_button.config = Mock()
        mock_button.configure = Mock()
        mock_button_class.return_value = mock_button

        with patch(
            "gui.main_window.GuiUtils.create_styled_button", return_value=mock_button
        ):
            main_window = MainWindow(str(self.temp_path))

            # Store button reference in the archive_buttons dict (simulating button creation)
            project_key = main_window._get_project_key(self.pre_edit_project)
            main_window.archive_buttons[project_key] = mock_button

            # Simulate marking project as archived
            main_window.mark_project_archived(self.pre_edit_project)

            # Assert - check for either config or configure method call
            self._assert_button_config_call(mock_button, bg=COLORS["success"])

            # Verify project is tracked as archived
            assert main_window.archived_projects[project_key] is True

    @patch("tkinter.Tk")
    @patch("tkinter.Button")
    def test_triggering_archive_twice_works(self, mock_button_class, mock_tk):
        """Test that triggering archive operation twice works correctly"""
        # Arrange
        mock_button = Mock()
        mock_button.config = Mock()
        mock_button.configure = Mock()
        mock_button_class.return_value = mock_button

        with patch(
            "gui.main_window.GuiUtils.create_styled_button", return_value=mock_button
        ):
            main_window = MainWindow(str(self.temp_path))

            # Store button reference in the archive_buttons dict (simulating button creation)
            project_key = main_window._get_project_key(self.pre_edit_project)
            main_window.archive_buttons[project_key] = mock_button

            # First archive
            main_window.mark_project_archived(self.pre_edit_project)

            # Second archive (should work without errors)
            main_window.mark_project_archived(self.pre_edit_project)

            # Assert button was configured twice
            expected_calls = [call(bg=COLORS["success"]), call(bg=COLORS["success"])]
            self._assert_button_has_calls(mock_button, expected_calls)

    @patch("tkinter.Tk")
    @patch("tkinter.Button")
    def test_button_resets_color_on_file_deletion(self, mock_button_class, mock_tk):
        """Test that button color resets when a file is deleted from project directory"""
        # Arrange
        mock_button = Mock()
        mock_button.config = Mock()
        mock_button.configure = Mock()
        mock_button_class.return_value = mock_button

        with patch(
            "gui.main_window.GuiUtils.create_styled_button", return_value=mock_button
        ):
            main_window = MainWindow(str(self.temp_path))

            # Store button reference for tracking
            project_key = main_window._get_project_key(self.pre_edit_project)
            main_window.archive_buttons[project_key] = mock_button

            # Mark as archived (button should turn green)
            main_window.mark_project_archived(self.pre_edit_project)

            # Verify button turned green
            self._assert_button_config_call(mock_button, bg=COLORS["success"])

            # Reset mocks to track subsequent calls
            if hasattr(mock_button.config, "reset_mock"):
                mock_button.config.reset_mock()
            if hasattr(mock_button.configure, "reset_mock"):
                mock_button.configure.reset_mock()

            # Mock the window.after method to immediately execute the scheduled callback
            def mock_after(delay, callback):
                callback()

            with patch.object(main_window.window, "after", side_effect=mock_after):
                # Simulate file change callback (which would be called by file monitor)
                main_window._on_file_change(project_key)

            # Verify button color was reset to original
            original_color = BUTTON_STYLES["archive"]["bg"]
            self._assert_button_config_call(mock_button, bg=original_color)

            # Check that the reset color was scheduled (by checking the archived_projects state)
            assert main_window.archived_projects[project_key] is False
            assert project_key not in file_monitor.monitored_projects

    @patch("tkinter.Tk")
    @patch("tkinter.Button")
    def test_button_resets_color_on_file_modification(self, mock_button_class, mock_tk):
        """Test that button color resets when a file is modified in project directory"""
        # Arrange
        mock_button = Mock()
        mock_button.config = Mock()
        mock_button.configure = Mock()
        mock_button_class.return_value = mock_button

        with patch(
            "gui.main_window.GuiUtils.create_styled_button", return_value=mock_button
        ):
            main_window = MainWindow(str(self.temp_path))

            # Store button reference for tracking
            project_key = main_window._get_project_key(self.pre_edit_project)
            main_window.archive_buttons[project_key] = mock_button

            # Mark as archived
            main_window.mark_project_archived(self.pre_edit_project)

            # Verify button turned green
            self._assert_button_config_call(mock_button, bg=COLORS["success"])

            # Reset mocks to track subsequent calls
            if hasattr(mock_button.config, "reset_mock"):
                mock_button.config.reset_mock()
            if hasattr(mock_button.configure, "reset_mock"):
                mock_button.configure.reset_mock()

            # Mock the window.after method to immediately execute the scheduled callback
            def mock_after(delay, callback):
                callback()

            with patch.object(main_window.window, "after", side_effect=mock_after):
                # Simulate file change callback (which would be called by file monitor)
                main_window._on_file_change(project_key)

            # Verify button color was reset to original
            original_color = BUTTON_STYLES["archive"]["bg"]
            self._assert_button_config_call(mock_button, bg=original_color)

            # Check that the reset color was scheduled (by checking the archived_projects state)
            assert main_window.archived_projects[project_key] is False
            assert project_key not in file_monitor.monitored_projects

    @patch("tkinter.Tk")
    @patch("tkinter.Button")
    def test_only_correct_button_changes_color(self, mock_button_class, mock_tk):
        """Test that only the specific project's button changes color, not others"""
        # Arrange
        mock_button_pre_edit = Mock()
        mock_button_pre_edit.config = Mock()
        mock_button_pre_edit.configure = Mock()

        mock_button_post_edit = Mock()
        mock_button_post_edit.config = Mock()
        mock_button_post_edit.configure = Mock()

        mock_button_other = Mock()
        mock_button_other.config = Mock()
        mock_button_other.configure = Mock()

        # Mock button creation to return different buttons for different projects
        buttons = [mock_button_pre_edit, mock_button_post_edit, mock_button_other]
        button_iter = iter(buttons)

        def create_button_side_effect(*args, **kwargs):
            return next(button_iter)

        with patch(
            "gui.main_window.GuiUtils.create_styled_button",
            side_effect=create_button_side_effect,
        ):
            main_window = MainWindow(str(self.temp_path))

            # Mock the window.after method to immediately execute the scheduled callback
            def mock_after(delay, callback):
                callback()

            # Apply the mock for the entire test
            main_window.window.after = Mock(side_effect=mock_after)

            # Store button references
            pre_edit_key = main_window._get_project_key(self.pre_edit_project)
            post_edit_key = main_window._get_project_key(self.post_edit_project)
            other_key = main_window._get_project_key(self.other_project)

            main_window.archive_buttons[pre_edit_key] = mock_button_pre_edit
            main_window.archive_buttons[post_edit_key] = mock_button_post_edit
            main_window.archive_buttons[other_key] = mock_button_other

            # Mark only pre-edit project as archived
            main_window.mark_project_archived(self.pre_edit_project)

            # Wait for monitoring to start
            time.sleep(0.2)

            # Modify file in pre-edit project
            file_to_modify = self.pre_edit_project.path / "main.py"
            file_to_modify.write_text("print('changed')")

            # Wait for detection
            time.sleep(1.5)

            # Assert only pre-edit button was affected
            # Pre-edit button should have been configured (green, then reset)
            assert self._get_button_call_count(mock_button_pre_edit) >= 1

            # Verify the specific config calls for pre-edit button
            expected_calls = [
                call(bg=COLORS["success"]),  # Initial archive call
                call(bg=BUTTON_STYLES["archive"]["bg"]),  # Reset after file change
            ]
            self._assert_button_has_calls(
                mock_button_pre_edit, expected_calls, any_order=False
            )

            # Other buttons should not have been configured
            assert self._get_button_call_count(mock_button_post_edit) == 0
            assert self._get_button_call_count(mock_button_other) == 0

    @patch("tkinter.Tk")
    @patch("tkinter.Button")
    def test_file_monitoring_starts_and_stops_correctly(
        self, mock_button_class, mock_tk
    ):
        """Test that file monitoring starts when project is archived and stops when changes detected"""
        # Arrange
        mock_button = Mock()
        mock_button.config = Mock()
        mock_button.configure = Mock()
        mock_button_class.return_value = mock_button

        with patch(
            "gui.main_window.GuiUtils.create_styled_button", return_value=mock_button
        ):
            main_window = MainWindow(str(self.temp_path))

            project_key = main_window._get_project_key(self.pre_edit_project)
            main_window.archive_buttons[project_key] = mock_button

            # Verify no monitoring initially
            assert project_key not in file_monitor.monitored_projects

            # Mark as archived - should start monitoring
            main_window.mark_project_archived(self.pre_edit_project)

            # Wait a bit
            time.sleep(0.2)

            # Verify monitoring started
            assert project_key in file_monitor.monitored_projects

            # Make a change to trigger stop
            file_to_modify = self.pre_edit_project.path / "main.py"
            file_to_modify.write_text("modified")

            # Wait for detection and auto-stop
            time.sleep(1.5)

            # Verify monitoring stopped after change detection
            # (The file change callback should stop monitoring)
            # Note: This might take a moment due to thread cleanup
            max_wait = 5
            waited = 0
            while project_key in file_monitor.monitored_projects and waited < max_wait:
                time.sleep(0.5)
                waited += 0.5

            assert project_key not in file_monitor.monitored_projects

    @patch("tkinter.Tk")
    @patch("tkinter.Button")
    def test_multiple_projects_monitoring_isolation(self, mock_button_class, mock_tk):
        """Test that monitoring multiple projects works and changes are isolated"""
        # Arrange
        mock_button1 = Mock()
        mock_button1.config = Mock()
        mock_button1.configure = Mock()

        mock_button2 = Mock()
        mock_button2.config = Mock()
        mock_button2.configure = Mock()

        buttons = [mock_button1, mock_button2]
        button_iter = iter(buttons)

        def create_button_side_effect(*args, **kwargs):
            return next(button_iter)

        with patch(
            "gui.main_window.GuiUtils.create_styled_button",
            side_effect=create_button_side_effect,
        ):
            main_window = MainWindow(str(self.temp_path))

            # Mock the window.after method to immediately execute the scheduled callback
            def mock_after(delay, callback):
                callback()

            # Apply the mock for the entire test
            main_window.window.after = Mock(side_effect=mock_after)

            # Store button references
            pre_edit_key = main_window._get_project_key(self.pre_edit_project)
            other_key = main_window._get_project_key(self.other_project)

            main_window.archive_buttons[pre_edit_key] = mock_button1
            main_window.archive_buttons[other_key] = mock_button2

            # Archive both projects
            main_window.mark_project_archived(self.pre_edit_project)
            main_window.mark_project_archived(self.other_project)

            # Wait for monitoring to start
            time.sleep(0.2)

            # Verify both are being monitored
            assert pre_edit_key in file_monitor.monitored_projects
            assert other_key in file_monitor.monitored_projects

            # Modify file in only one project
            file_to_modify = self.pre_edit_project.path / "main.py"
            file_to_modify.write_text("changed content")

            # Wait for detection
            time.sleep(1.5)

            # Only the modified project should have stopped monitoring
            # The other should still be monitored
            assert other_key in file_monitor.monitored_projects

            # Verify specific config calls for both buttons
            # Button 1 (pre-edit project) should have been set green then reset
            expected_calls_button1 = [
                call(bg=COLORS["success"]),  # Initial archive
                call(bg=BUTTON_STYLES["archive"]["bg"]),  # Reset after change
            ]
            self._assert_button_has_calls(
                mock_button1, expected_calls_button1, any_order=False
            )

            # Button 2 (other project) should only have been set green (no reset)
            self._assert_button_config_call(mock_button2, bg=COLORS["success"])

    @patch("tkinter.Tk")
    def test_cleanup_on_window_close(self, mock_tk):
        """Test that file monitoring is properly cleaned up when window closes"""
        # Arrange
        with patch("gui.main_window.GuiUtils.create_styled_button"), patch(
            "gui.main_window.GuiUtils.create_scrollable_frame"
        ) as mock_scrollable:

            # Mock the scrollable frame creation to return a mock frame
            mock_frame = Mock()
            mock_frame.winfo_children.return_value = (
                []
            )  # Return empty list for iteration
            mock_scrollable.return_value = (Mock(), mock_frame, Mock())

            main_window = MainWindow(str(self.temp_path))

            # Initialize the GUI so scrollable_frame is set
            main_window.create_gui()

            # Store button reference for tracking (simulate button creation)
            project_key = main_window._get_project_key(self.pre_edit_project)
            mock_archive_button = Mock()
            mock_archive_button.config = Mock()
            main_window.archive_buttons[project_key] = mock_archive_button

            # Start monitoring
            main_window.mark_project_archived(self.pre_edit_project)
            time.sleep(0.2)

            # Verify config method was called for button color change
            self._assert_button_config_call(mock_archive_button, bg=COLORS["success"])

            # Verify monitoring is active and button is tracked
            assert project_key in file_monitor.monitored_projects
            assert project_key in main_window.archive_buttons
            assert main_window.archived_projects[project_key] is True

            # Simulate window close
            main_window.clear_content()

            # Verify button tracking is cleared
            assert len(main_window.archive_buttons) == 0
            assert len(main_window.archived_projects) == 0

            # Verify stop event is set (monitoring cleanup was initiated)
            assert file_monitor.stop_event.is_set()

    @patch("tkinter.Tk")
    @patch("tkinter.Button")
    def test_button_color_values_are_correct(self, mock_button_class, mock_tk):
        """Test that the correct color values are used for button states"""
        # Arrange
        mock_button = Mock()
        mock_button.config = Mock()
        mock_button.configure = Mock()
        mock_button_class.return_value = mock_button

        with patch(
            "gui.main_window.GuiUtils.create_styled_button", return_value=mock_button
        ):
            main_window = MainWindow(str(self.temp_path))

            project_key = main_window._get_project_key(self.pre_edit_project)
            main_window.archive_buttons[project_key] = mock_button

            # Test archived state (green)
            main_window.mark_project_archived(self.pre_edit_project)
            self._assert_button_config_call(mock_button, bg=COLORS["success"])

            # Test reset to original color
            main_window.reset_archive_button_color(self.pre_edit_project)
            original_color = BUTTON_STYLES["archive"]["bg"]
            self._assert_button_config_call(mock_button, bg=original_color)

    @patch("tkinter.Tk")
    @patch("tkinter.Button")
    def test_error_handling_destroyed_button(self, mock_button_class, mock_tk):
        """Test that the system handles gracefully when button is destroyed"""
        # Arrange
        mock_button = Mock()
        # Configure button to raise TclError when accessed (simulating destroyed widget)
        import tkinter as tk

        mock_button.config.side_effect = tk.TclError("invalid command name")
        # Also mock configure method in case it's used instead of config
        mock_button.configure = Mock(side_effect=tk.TclError("invalid command name"))

        with patch(
            "gui.main_window.GuiUtils.create_styled_button", return_value=mock_button
        ):
            main_window = MainWindow(str(self.temp_path))

            project_key = main_window._get_project_key(self.pre_edit_project)
            main_window.archive_buttons[project_key] = mock_button

            # This should not raise an exception
            main_window.mark_project_archived(self.pre_edit_project)

            # Verify that either config or configure method was attempted to be called
            try:
                mock_button.config.assert_called_once_with(bg=COLORS["success"])
            except AssertionError:
                mock_button.configure.assert_called_once_with(bg=COLORS["success"])

            # Button should be removed from tracking after TclError
            assert project_key not in main_window.archive_buttons

    def test_project_key_generation(self):
        """Test that project keys are generated correctly and uniquely"""
        with patch("tkinter.Tk"):
            main_window = MainWindow(str(self.temp_path))

            # Test unique keys for different projects
            key1 = main_window._get_project_key(self.pre_edit_project)
            key2 = main_window._get_project_key(self.post_edit_project)
            key3 = main_window._get_project_key(self.other_project)

            assert key1 != key2
            assert key1 != key3
            assert key2 != key3

            # Test consistent keys for same project
            key1_again = main_window._get_project_key(self.pre_edit_project)
            assert key1 == key1_again

            # Test key format
            assert key1 == "pre-edit_test-project"
            assert key3 == "pre-edit_other-project"


class TestFileMonitorServiceIntegration:
    """Test file monitor service integration aspects"""

    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp(prefix="file_monitor_test_")
        self.temp_path = Path(self.temp_dir)
        self.test_project_path = self.temp_path / "test_project"
        self.test_project_path.mkdir(parents=True)

        # Create initial files
        (self.test_project_path / "file1.py").write_text("content1")
        (self.test_project_path / "file2.py").write_text("content2")

    def teardown_method(self):
        """Clean up after each test"""
        file_monitor.stop_all_monitoring()
        time.sleep(0.1)
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_file_monitor_detects_new_files(self):
        """Test that file monitor detects new files"""
        callback_called = []

        def test_callback(project_key):
            callback_called.append(project_key)

        # Start monitoring
        file_monitor.start_monitoring("test_key", self.test_project_path, test_callback)
        time.sleep(0.2)

        # Add new file
        (self.test_project_path / "new_file.py").write_text("new content")

        # Wait for detection
        time.sleep(1.5)

        # Verify callback was called
        assert "test_key" in callback_called

    def test_file_monitor_detects_modified_files(self):
        """Test that file monitor detects file modifications"""
        callback_called = []

        def test_callback(project_key):
            callback_called.append(project_key)

        # Start monitoring
        file_monitor.start_monitoring("test_key", self.test_project_path, test_callback)
        time.sleep(0.2)

        # Modify existing file
        (self.test_project_path / "file1.py").write_text("modified content")

        # Wait for detection
        time.sleep(1.5)

        # Verify callback was called
        assert "test_key" in callback_called

    def test_file_monitor_detects_deleted_files(self):
        """Test that file monitor detects file deletions"""
        callback_called = []

        def test_callback(project_key):
            callback_called.append(project_key)

        # Start monitoring
        file_monitor.start_monitoring("test_key", self.test_project_path, test_callback)
        time.sleep(0.2)

        # Delete existing file
        (self.test_project_path / "file1.py").unlink()

        # Wait for detection
        time.sleep(1.5)

        # Verify callback was called
        assert "test_key" in callback_called

    def test_file_monitor_ignores_hidden_files(self):
        """Test that file monitor ignores hidden files and cache directories"""
        callback_called = []

        def test_callback(project_key):
            callback_called.append(project_key)

        # Start monitoring
        file_monitor.start_monitoring("test_key", self.test_project_path, test_callback)
        time.sleep(0.2)

        # Create hidden files and cache directories that should be ignored
        (self.test_project_path / "__pycache__").mkdir()
        (self.test_project_path / "__pycache__" / "cache.pyc").write_text("cache")

        # Wait for potential detection
        time.sleep(1.5)

        # Verify callback was NOT called for hidden files
        assert "test_key" not in callback_called
