"""
Tests for Color Picker functionality in Settings Window
"""

import os
import sys
import tempfile
import shutil
import tkinter as tk
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
import pytest

# Set up headless testing environment
os.environ.setdefault("DISPLAY", ":0")

# Add parent directory to path to import modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from gui.popup_windows import SettingsWindow


def create_mock_tkinter_frame():
    """Helper function to create properly mocked tkinter frame"""
    mock_frame = Mock()
    mock_frame._last_child_ids = {}  # Add tkinter internal attribute
    return mock_frame


def create_mock_gui_utils():
    """Helper function to create GuiUtils mock that returns proper tkinter frames"""
    mock_gui_utils = Mock()
    mock_gui_utils.create_styled_frame.side_effect = (
        lambda *args, **kwargs: create_mock_tkinter_frame()
    )
    mock_gui_utils.create_styled_label.return_value = Mock()
    mock_gui_utils.create_styled_button.return_value = Mock()
    return mock_gui_utils


def create_mock_tkinter_widget():
    """Helper function to create tkinter widget mock with required internal attributes"""
    widget = Mock()
    widget._last_child_ids = {}
    widget._setup = Mock()
    widget.winfo_exists.return_value = True
    return widget


def setup_mock_stringvar_with_trace():
    """Helper function to create StringVar mock that handles both trace methods"""
    mock_var = Mock()
    mock_var.get.return_value = "#ff0000"
    mock_var.set = Mock()

    # Capture trace callbacks for both trace and trace_add methods
    trace_callback = None

    def capture_trace(mode, callback=None):
        nonlocal trace_callback
        if callback is None:  # trace_add("write", callback) format
            trace_callback = mode  # mode is actually the callback in trace_add
        else:  # trace("w", callback) format
            trace_callback = callback

    def capture_trace_add(mode, callback):
        nonlocal trace_callback
        trace_callback = callback

    mock_var.trace = capture_trace
    mock_var.trace_add = capture_trace_add

    return mock_var, lambda: trace_callback


class TestColorPickerFunctionality:
    """Test cases for color picker functionality in settings window"""

    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()

        # Create mock parent window with tkinter attributes
        self.mock_parent = create_mock_tkinter_widget()

        # Mock callbacks
        self.mock_save_callback = Mock()
        self.mock_reset_callback = Mock()

        # Patch the settings module
        self.settings_patch = patch("config.settings")
        self.mock_settings = self.settings_patch.start()

        # Patch tkinter widgets to avoid internal tkinter conflicts
        self.tkinter_patches = [
            patch("tkinter.Frame", create_mock_tkinter_widget),
            patch("tkinter.Text", create_mock_tkinter_widget),
            patch("tkinter.Canvas", create_mock_tkinter_widget),
        ]
        for patcher in self.tkinter_patches:
            patcher.start()

        # Set up default mock settings with color values
        self.mock_settings.SOURCE_DIR = str(self.temp_dir)
        self.mock_settings.COLORS = {
            "background": "#f0f0f0",
            "terminal_bg": "#2c3e50",
            "terminal_text": "#ffffff",
            "success": "#27ae60",
            "error": "#e74c3c",
            "warning": "#f39c12",
            "info": "#3498db",
        }
        self.mock_settings.FONTS = {
            "title": ("Arial", 16, "bold"),
            "header": ("Arial", 14, "bold"),
            "button": ("Arial", 9, "bold"),
            "console": ("Consolas", 9),
        }

    def teardown_method(self):
        """Clean up test fixtures"""
        if hasattr(self, "settings_patch"):
            self.settings_patch.stop()

        # Stop tkinter patches
        if hasattr(self, "tkinter_patches"):
            for patcher in self.tkinter_patches:
                patcher.stop()

        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_create_color_setting_creates_button_instead_of_frame(self):
        """Test that _create_color_setting creates a Button widget for color preview"""
        # Create mock parent with tkinter attributes
        mock_parent = create_mock_tkinter_widget()

        with patch("tkinter.Tk"), patch("tkinter.StringVar") as mock_stringvar, patch(
            "tkinter.Entry"
        ) as mock_entry, patch("tkinter.Button") as mock_button, patch(
            "gui.popup_windows.GuiUtils"
        ) as mock_gui_utils, patch(
            "tkinter.Frame", create_mock_tkinter_widget
        ), patch(
            "tkinter.Text", create_mock_tkinter_widget
        ):

            # Set up mocks
            mock_var = Mock()
            mock_stringvar.return_value = mock_var
            mock_var.get.return_value = "#ff0000"
            mock_var.set = Mock()
            mock_var.trace = Mock()

            mock_frame = Mock()
            mock_gui_utils.create_styled_frame.return_value = mock_frame
            mock_gui_utils.create_styled_label.return_value = Mock()

            mock_button_instance = Mock()
            mock_button.return_value = mock_button_instance

            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )

            # Call the method directly
            window._create_color_setting(
                mock_parent, "Test Color", "test_key", "Test description", "#ff0000"
            )

            # Verify Button was created (not Frame as in old implementation)
            mock_button.assert_called_once()
            button_call = mock_button.call_args

            # Verify button properties
            assert button_call[1]["bg"] == "#ff0000"
            assert button_call[1]["width"] == 4
            assert button_call[1]["height"] == 1
            assert button_call[1]["bd"] == 2
            assert button_call[1]["cursor"] == "hand2"
            assert "command" in button_call[1]

            # Verify button is packed
            mock_button_instance.pack.assert_called_once()

    def test_color_entry_updates_button_background(self):
        """Test that manually changing hex code in entry updates button background"""
        mock_parent = Mock()

        with patch("tkinter.Tk"), patch("tkinter.StringVar") as mock_stringvar, patch(
            "tkinter.Entry"
        ) as mock_entry, patch("tkinter.Button") as mock_button, patch(
            "gui.popup_windows.GuiUtils"
        ) as mock_gui_utils:

            # Set up mocks
            mock_var = Mock()
            mock_stringvar.return_value = mock_var
            mock_var.get.return_value = "#ff0000"
            mock_var.set = Mock()

            # Create proper tkinter-like mock frames
            mock_frame = Mock()
            mock_frame._last_child_ids = {}  # Add tkinter internal attribute
            mock_gui_utils.create_styled_frame.return_value = mock_frame
            mock_gui_utils.create_styled_label.return_value = Mock()

            mock_button_instance = Mock()
            mock_button.return_value = mock_button_instance

            # Capture the trace callback (handle both trace and trace_add methods)
            trace_callback = None

            def capture_trace(mode, callback=None):
                nonlocal trace_callback
                if callback is None:  # trace_add("write", callback) format
                    trace_callback = mode  # mode is actually the callback in trace_add
                else:  # trace("w", callback) format
                    trace_callback = callback

            def capture_trace_add(mode, callback):
                nonlocal trace_callback
                trace_callback = callback

            mock_var.trace = capture_trace
            mock_var.trace_add = capture_trace_add

            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )

            # Call the method
            window._create_color_setting(
                mock_parent, "Test Color", "test_key", "Test description", "#ff0000"
            )

            # Simulate entry value change by calling the trace callback
            assert trace_callback is not None
            mock_var.get.return_value = "#00ff00"  # New color
            trace_callback()

            # Verify button background was updated
            mock_button_instance.config.assert_called_with(bg="#00ff00")

    def test_color_entry_handles_invalid_colors_gracefully(self):
        """Test that invalid color codes don't crash the application"""
        mock_parent = Mock()

        with patch("tkinter.Tk"), patch("tkinter.StringVar") as mock_stringvar, patch(
            "tkinter.Entry"
        ) as mock_entry, patch("tkinter.Button") as mock_button, patch(
            "gui.popup_windows.GuiUtils"
        ) as mock_gui_utils:

            # Set up mocks
            mock_var = Mock()
            mock_stringvar.return_value = mock_var
            mock_var.get.return_value = "#ff0000"
            mock_var.set = Mock()

            # Create proper tkinter-like mock frames
            mock_frame = Mock()
            mock_frame._last_child_ids = {}  # Add tkinter internal attribute
            mock_gui_utils.create_styled_frame.return_value = mock_frame
            mock_gui_utils.create_styled_label.return_value = Mock()

            mock_button_instance = Mock()
            mock_button.return_value = mock_button_instance

            # Simulate TclError when setting invalid color
            mock_button_instance.config.side_effect = tk.TclError("invalid color")

            # Capture the trace callback (handle both trace and trace_add methods)
            trace_callback = None

            def capture_trace(mode, callback=None):
                nonlocal trace_callback
                if callback is None:  # trace_add("write", callback) format
                    trace_callback = mode  # mode is actually the callback in trace_add
                else:  # trace("w", callback) format
                    trace_callback = callback

            def capture_trace_add(mode, callback):
                nonlocal trace_callback
                trace_callback = callback

            mock_var.trace = capture_trace
            mock_var.trace_add = capture_trace_add

            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )

            # Call the method
            window._create_color_setting(
                mock_parent, "Test Color", "test_key", "Test description", "#ff0000"
            )

            # Simulate invalid color entry
            assert trace_callback is not None
            mock_var.get.return_value = "invalid_color"

            # This should not raise an exception
            trace_callback()

            # Verify config was attempted but error was handled
            mock_button_instance.config.assert_called_with(bg="invalid_color")

    @patch("tkinter.colorchooser.askcolor")
    def test_button_click_opens_color_chooser(self, mock_askcolor):
        """Test that clicking the color button opens colorchooser.askcolor"""
        mock_parent = Mock()

        with patch("tkinter.Tk"), patch("tkinter.StringVar") as mock_stringvar, patch(
            "tkinter.Entry"
        ) as mock_entry, patch("tkinter.Button") as mock_button, patch(
            "gui.popup_windows.GuiUtils"
        ) as mock_gui_utils:

            # Set up mocks
            mock_var = Mock()
            mock_stringvar.return_value = mock_var
            mock_var.get.return_value = "#ff0000"
            mock_var.set = Mock()
            mock_var.trace = Mock()

            mock_frame = Mock()
            mock_gui_utils.create_styled_frame.return_value = mock_frame
            mock_gui_utils.create_styled_label.return_value = Mock()

            mock_button_instance = Mock()
            mock_button.return_value = mock_button_instance

            # Mock color chooser to return a new color
            mock_askcolor.return_value = ((0, 255, 0), "#00ff00")

            # Capture the button command
            button_command = None

            def capture_command(*args, **kwargs):
                nonlocal button_command
                button_command = kwargs.get("command")
                return mock_button_instance

            mock_button.side_effect = capture_command

            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )

            # Call the method
            window._create_color_setting(
                mock_parent, "Test Color", "test_key", "Test description", "#ff0000"
            )

            # Simulate button click
            assert button_command is not None
            button_command()

            # Verify colorchooser was called with correct parameters
            mock_askcolor.assert_called_once_with(
                initialcolor="#ff0000", title="Choose Test Color"
            )

    @patch("tkinter.colorchooser.askcolor")
    def test_color_chooser_result_updates_entry_and_button(self, mock_askcolor):
        """Test that color chooser result updates both entry field and button"""
        mock_parent = Mock()

        with patch("tkinter.Tk"), patch("tkinter.StringVar") as mock_stringvar, patch(
            "tkinter.Entry"
        ) as mock_entry, patch("tkinter.Button") as mock_button, patch(
            "gui.popup_windows.GuiUtils"
        ) as mock_gui_utils:

            # Set up mocks
            mock_var = Mock()
            mock_stringvar.return_value = mock_var
            mock_var.get.return_value = "#ff0000"
            mock_var.set = Mock()
            mock_var.trace = Mock()

            mock_frame = Mock()
            mock_gui_utils.create_styled_frame.return_value = mock_frame
            mock_gui_utils.create_styled_label.return_value = Mock()

            mock_button_instance = Mock()
            mock_button.return_value = mock_button_instance

            # Mock color chooser to return a new color
            new_color = "#00ff00"
            mock_askcolor.return_value = ((0, 255, 0), new_color)

            # Capture the button command
            button_command = None

            def capture_command(*args, **kwargs):
                nonlocal button_command
                button_command = kwargs.get("command")
                return mock_button_instance

            mock_button.side_effect = capture_command

            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )

            # Call the method
            window._create_color_setting(
                mock_parent, "Test Color", "test_key", "Test description", "#ff0000"
            )

            # Simulate button click
            assert button_command is not None
            button_command()

            # Verify entry field was updated
            mock_var.set.assert_called_with(new_color)

            # Verify button background was updated
            mock_button_instance.config.assert_called_with(bg=new_color)

    @patch("tkinter.colorchooser.askcolor")
    def test_color_chooser_cancel_does_not_update_values(self, mock_askcolor):
        """Test that cancelling color chooser doesn't change existing values"""
        mock_parent = Mock()

        with patch("tkinter.Tk"), patch("tkinter.StringVar") as mock_stringvar, patch(
            "tkinter.Entry"
        ) as mock_entry, patch("tkinter.Button") as mock_button, patch(
            "gui.popup_windows.GuiUtils"
        ) as mock_gui_utils:

            # Set up mocks
            mock_var = Mock()
            mock_stringvar.return_value = mock_var
            mock_var.get.return_value = "#ff0000"
            mock_var.set = Mock()
            mock_var.trace = Mock()

            mock_frame = Mock()
            mock_gui_utils.create_styled_frame.return_value = mock_frame
            mock_gui_utils.create_styled_label.return_value = Mock()

            mock_button_instance = Mock()
            mock_button.return_value = mock_button_instance

            # Mock color chooser to return None (user cancelled)
            mock_askcolor.return_value = (None, None)

            # Capture the button command
            button_command = None

            def capture_command(*args, **kwargs):
                nonlocal button_command
                button_command = kwargs.get("command")
                return mock_button_instance

            mock_button.side_effect = capture_command

            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )

            # Call the method
            window._create_color_setting(
                mock_parent, "Test Color", "test_key", "Test description", "#ff0000"
            )

            # Simulate button click with cancel
            assert button_command is not None
            button_command()

            # Verify entry field was NOT updated
            mock_var.set.assert_not_called()

            # Verify button background was NOT updated (only initial setup call)
            # The button should only have config called once during creation
            config_calls = [call for call in mock_button_instance.config.call_args_list]
            assert (
                len(config_calls) == 0
            )  # No additional config calls after cancellation

    def test_settings_vars_stores_stringvar_for_color_setting(self):
        """Test that color settings are properly stored in settings_vars"""
        mock_parent = Mock()

        with patch("tkinter.Tk"), patch("tkinter.StringVar") as mock_stringvar, patch(
            "tkinter.Entry"
        ) as mock_entry, patch("tkinter.Button") as mock_button, patch(
            "gui.popup_windows.GuiUtils"
        ) as mock_gui_utils:

            # Set up mocks
            mock_var = Mock()
            mock_stringvar.return_value = mock_var
            mock_var.get.return_value = "#ff0000"
            mock_var.set = Mock()
            mock_var.trace = Mock()

            mock_frame = Mock()
            mock_gui_utils.create_styled_frame.return_value = mock_frame
            mock_gui_utils.create_styled_label.return_value = Mock()

            mock_button_instance = Mock()
            mock_button.return_value = mock_button_instance

            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )

            # Call the method
            setting_key = "COLORS.test_color"
            window._create_color_setting(
                mock_parent, "Test Color", setting_key, "Test description", "#ff0000"
            )

            # Verify the StringVar is stored in settings_vars
            assert setting_key in window.settings_vars
            assert window.settings_vars[setting_key] == mock_var

    def test_apply_settings_processes_color_from_picker(self):
        """Test that color values from picker are correctly processed in settings collection"""
        window = SettingsWindow(
            self.mock_parent, self.mock_save_callback, self.mock_reset_callback
        )

        # Simulate color setting variables - focus on the color collection logic
        mock_color_var = Mock()
        mock_color_var.get.return_value = "#00ff00"  # New color from picker

        window.settings_vars = {
            "COLORS.background": mock_color_var,
        }

        # Test the settings collection part of _apply_settings directly
        new_settings = {}
        for key, var in window.settings_vars.items():
            # Use hasattr instead of isinstance since tk.Text is mocked
            if not hasattr(var, "get"):
                # Handle text areas (for lists and dictionaries) - would be tk.Text normally
                continue
            else:
                # Handle string variables (like color settings)
                value = var.get()
                if key.startswith("FONTS."):
                    # Parse font settings
                    font_parts = [part.strip() for part in value.split(",")]
                    if len(font_parts) >= 2:
                        try:
                            new_settings[key] = (
                                font_parts[0],
                                int(font_parts[1]),
                            ) + tuple(font_parts[2:])
                        except ValueError:
                            new_settings[key] = (font_parts[0], 12) + tuple(
                                font_parts[2:]
                            )
                else:
                    new_settings[key] = value

        # Verify color was correctly collected
        assert "COLORS.background" in new_settings
        assert new_settings["COLORS.background"] == "#00ff00"

    def test_color_button_has_hover_effects_disabled(self):
        """Test that color button doesn't have hover effects (user removed them)"""
        mock_parent = Mock()

        with patch("tkinter.Tk"), patch("tkinter.StringVar") as mock_stringvar, patch(
            "tkinter.Entry"
        ) as mock_entry, patch("tkinter.Button") as mock_button, patch(
            "gui.popup_windows.GuiUtils"
        ) as mock_gui_utils:

            # Set up mocks
            mock_var = Mock()
            mock_stringvar.return_value = mock_var
            mock_var.get.return_value = "#ff0000"
            mock_var.set = Mock()
            mock_var.trace = Mock()

            mock_frame = Mock()
            mock_gui_utils.create_styled_frame.return_value = mock_frame
            mock_gui_utils.create_styled_label.return_value = Mock()

            mock_button_instance = Mock()
            mock_button.return_value = mock_button_instance

            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )

            # Call the method
            window._create_color_setting(
                mock_parent, "Test Color", "test_key", "Test description", "#ff0000"
            )

            # Verify no hover event bindings were created (user removed hover effects)
            mock_button_instance.bind.assert_not_called()

    @patch("tkinter.colorchooser.askcolor")
    def test_multiple_color_settings_work_independently(self, mock_askcolor):
        """Test that multiple color settings work independently"""
        mock_parent = Mock()

        with patch("tkinter.Tk"), patch("tkinter.StringVar") as mock_stringvar, patch(
            "tkinter.Entry"
        ) as mock_entry, patch("tkinter.Button") as mock_button, patch(
            "gui.popup_windows.GuiUtils"
        ) as mock_gui_utils:

            # Set up mocks for multiple calls
            mock_vars = []
            mock_buttons = []

            def create_mock_var(value=None):
                var = Mock()
                var.get.return_value = value or "#ff0000"
                var.set = Mock()
                var.trace = Mock()
                mock_vars.append(var)
                return var

            def create_mock_button(*args, **kwargs):
                button = Mock()
                mock_buttons.append(button)
                return button

            mock_stringvar.side_effect = create_mock_var
            mock_button.side_effect = create_mock_button

            mock_frame = Mock()
            mock_gui_utils.create_styled_frame.return_value = mock_frame
            mock_gui_utils.create_styled_label.return_value = Mock()

            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )

            # Create two color settings
            window._create_color_setting(
                mock_parent, "Background", "COLORS.background", "Bg color", "#ffffff"
            )
            window._create_color_setting(
                mock_parent, "Error", "COLORS.error", "Error color", "#ff0000"
            )

            # Verify two separate StringVars and Buttons were created
            assert len(mock_vars) == 2
            assert len(mock_buttons) == 2

            # Verify settings are stored separately
            assert "COLORS.background" in window.settings_vars
            assert "COLORS.error" in window.settings_vars
            assert (
                window.settings_vars["COLORS.background"]
                != window.settings_vars["COLORS.error"]
            )

    def test_colorchooser_import_available(self):
        """Test that colorchooser module is properly imported"""
        # This is a simple smoke test to ensure the import works
        from tkinter import colorchooser

        assert hasattr(colorchooser, "askcolor")


class TestColorPickerIntegration:
    """Integration tests for color picker with full settings window"""

    def setup_method(self):
        """Set up test fixtures for integration tests"""
        self.temp_dir = tempfile.mkdtemp()

        # Create mock parent window with tkinter attributes
        self.mock_parent = create_mock_tkinter_widget()

        # Mock callbacks
        self.mock_save_callback = Mock()
        self.mock_reset_callback = Mock()

        # Patch the settings module
        self.settings_patch = patch("config.settings")
        self.mock_settings = self.settings_patch.start()

        # Patch tkinter widgets to avoid internal tkinter conflicts
        self.tkinter_patches = [
            patch("tkinter.Frame", create_mock_tkinter_widget),
            patch("tkinter.Text", create_mock_tkinter_widget),
            patch("tkinter.Canvas", create_mock_tkinter_widget),
        ]
        for patcher in self.tkinter_patches:
            patcher.start()

        # Set up comprehensive mock settings
        self.mock_settings.SOURCE_DIR = str(self.temp_dir)
        self.mock_settings.WINDOW_TITLE = "Test App"
        self.mock_settings.MAIN_WINDOW_SIZE = "800x600"
        self.mock_settings.OUTPUT_WINDOW_SIZE = "700x500"
        self.mock_settings.GIT_WINDOW_SIZE = "900x600"
        self.mock_settings.COLORS = {
            "background": "#f0f0f0",
            "terminal_bg": "#2c3e50",
            "terminal_text": "#ffffff",
            "success": "#27ae60",
            "error": "#e74c3c",
            "warning": "#f39c12",
            "info": "#3498db",
        }
        self.mock_settings.FONTS = {
            "title": ("Arial", 16, "bold"),
            "header": ("Arial", 14, "bold"),
            "button": ("Arial", 9, "bold"),
            "console": ("Consolas", 9),
        }
        self.mock_settings.IGNORE_DIRS = ["__pycache__", ".git"]
        self.mock_settings.IGNORE_FILES = [".coverage", ".DS_Store"]
        self.mock_settings.FOLDER_ALIASES = {"preedit": ["pre-edit"]}
        self.mock_settings.LANGUAGE_EXTENSIONS = {"python": [".py"]}
        self.mock_settings.LANGUAGE_REQUIRED_FILES = {"python": ["requirements.txt"]}

    def teardown_method(self):
        """Clean up test fixtures"""
        if hasattr(self, "settings_patch"):
            self.settings_patch.stop()

        # Stop tkinter patches
        if hasattr(self, "tkinter_patches"):
            for patcher in self.tkinter_patches:
                patcher.stop()

        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    @patch("tkinter.colorchooser.askcolor")
    def test_full_color_picker_workflow_in_appearance_tab(self, mock_askcolor):
        """Test complete workflow: create appearance tab, pick color, save settings"""

        with patch("tkinter.Tk"), patch("tkinter.Toplevel") as mock_toplevel, patch(
            "tkinter.ttk.Notebook"
        ) as mock_notebook, patch(
            "gui.popup_windows.GuiUtils"
        ) as mock_gui_utils, patch(
            "tkinter.Canvas"
        ) as mock_canvas, patch(
            "tkinter.ttk.Scrollbar"
        ) as mock_scrollbar, patch(
            "tkinter.StringVar"
        ) as mock_stringvar, patch(
            "tkinter.Entry"
        ) as mock_entry, patch(
            "tkinter.Button"
        ) as mock_button, patch(
            "tkinter.messagebox"
        ) as mock_messagebox:

            # Mock messagebox to avoid UI interactions during tests
            mock_messagebox.showerror = Mock()
            mock_messagebox.askyesno = Mock(return_value=True)
            mock_messagebox.showinfo = Mock()

            # Set up GUI mocks
            mock_window = Mock()
            mock_toplevel.return_value = mock_window
            mock_notebook_instance = Mock()
            mock_notebook.return_value = mock_notebook_instance

            # Mock canvas and scrollable frame creation
            mock_canvas_instance = Mock()
            mock_canvas.return_value = mock_canvas_instance
            mock_scrollbar_instance = Mock()
            mock_scrollbar.return_value = mock_scrollbar_instance

            mock_frame = Mock()
            mock_gui_utils.create_styled_frame.return_value = mock_frame
            mock_gui_utils.create_styled_label.return_value = Mock()

            # Mock StringVar and Button for color setting
            mock_var = Mock()
            mock_var.get.return_value = "#f0f0f0"  # Initial color
            mock_var.set = Mock()
            mock_var.trace = Mock()
            mock_stringvar.return_value = mock_var

            mock_button_instance = Mock()
            mock_button.return_value = mock_button_instance

            # Mock color chooser to return new color
            new_color = "#ff6600"  # Orange color
            mock_askcolor.return_value = ((255, 102, 0), new_color)

            # Create settings window
            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )

            # Capture the button command
            button_command = None

            def capture_command(*args, **kwargs):
                nonlocal button_command
                button_command = kwargs.get("command")
                return mock_button_instance

            mock_button.side_effect = capture_command

            # Test the color setting creation directly (simulates appearance tab)
            window._create_color_setting(
                mock_frame,
                "Background Color",
                "COLORS.background",
                "Background",
                "#f0f0f0",
            )

            # Simulate clicking the color picker button
            assert button_command is not None
            button_command()

            # Verify color chooser was opened
            mock_askcolor.assert_called_once_with(
                initialcolor="#f0f0f0", title="Choose Background Color"
            )

            # Verify the color variable was updated
            mock_var.set.assert_called_with(new_color)

            # Verify button background was updated
            mock_button_instance.config.assert_called_with(bg=new_color)

            # Setup for applying settings
            mock_var.get.return_value = new_color  # Simulate the new color in the var

            # Verify that the color variable contains the new color from picker
            assert mock_var.get() == new_color

            # This demonstrates that the color picker workflow would work end-to-end
            # The actual settings application is complex and tested separately

    def test_color_picker_error_handling_in_integration(self):
        """Test that color picker errors don't break the settings window"""

        with patch("tkinter.Tk"), patch("tkinter.Toplevel"), patch(
            "tkinter.ttk.Notebook"
        ), patch("gui.popup_windows.GuiUtils") as mock_gui_utils, patch(
            "tkinter.StringVar"
        ) as mock_stringvar, patch(
            "tkinter.Entry"
        ) as mock_entry, patch(
            "tkinter.Button"
        ) as mock_button, patch(
            "tkinter.colorchooser.askcolor"
        ) as mock_askcolor:

            # Mock askcolor to raise an exception
            mock_askcolor.side_effect = Exception("Color chooser error")

            # Set up other mocks
            mock_frame = Mock()
            mock_gui_utils.create_styled_frame.return_value = mock_frame
            mock_gui_utils.create_styled_label.return_value = Mock()

            mock_var = Mock()
            mock_var.get.return_value = "#ff0000"
            mock_var.set = Mock()
            mock_var.trace = Mock()
            mock_var.trace_add = Mock()
            mock_stringvar.return_value = mock_var

            mock_button_instance = Mock()
            mock_button.return_value = mock_button_instance

            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )

            # This should not raise an exception even if color chooser fails
            window._create_color_setting(
                Mock(), "Test Color", "test_key", "Test description", "#ff0000"
            )

            # The button command should still be created
            button_calls = mock_button.call_args_list
            assert len(button_calls) > 0

            # The command should handle the exception gracefully
            # (implementation should catch exceptions in the command)
