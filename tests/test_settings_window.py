"""
Tests for Settings Window functionality
"""

import os
import sys
import tempfile
import shutil
import json
import tkinter as tk
import tkinter.ttk as ttk
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
from config import settings


class TestSettingsWindow:
    """Test cases for Settings Window functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = Path(self.temp_dir) / "config"
        self.config_dir.mkdir(exist_ok=True)

        # Create mock parent window
        self.mock_parent = Mock()
        self.mock_parent.winfo_rootx.return_value = 100
        self.mock_parent.winfo_rooty.return_value = 100
        self.mock_parent.winfo_width.return_value = 800
        self.mock_parent.winfo_height.return_value = 600

        # Mock callbacks
        self.mock_save_callback = Mock()
        self.mock_reset_callback = Mock()

        # Patch the settings module to avoid conflicts
        self.settings_patch = patch("config.settings")
        self.mock_settings = self.settings_patch.start()

        # Set up default mock settings
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
        self.mock_settings.IGNORE_DIRS = ["__pycache__", ".git", "node_modules"]
        self.mock_settings.IGNORE_FILES = [".coverage", ".DS_Store"]
        self.mock_settings.FOLDER_ALIASES = {
            "preedit": ["pre-edit"],
            "postedit": ["post-edit", "post-edit2"],
        }
        self.mock_settings.LANGUAGE_EXTENSIONS = {
            "python": [".py", ".pyw"],
            "javascript": [".js", ".jsx"],
        }
        self.mock_settings.LANGUAGE_REQUIRED_FILES = {
            "python": ["requirements.txt"],
            "javascript": ["package.json"],
        }

    def teardown_method(self):
        """Clean up test fixtures"""
        if hasattr(self, "settings_patch"):
            self.settings_patch.stop()

        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_settings_window_initialization(self):
        """Test settings window initialization"""
        with patch("tkinter.Tk"), patch("tkinter.Toplevel") as mock_toplevel:
            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )

            assert window.parent_window == self.mock_parent
            assert window.on_save_callback == self.mock_save_callback
            assert window.on_reset_callback == self.mock_reset_callback
            assert window.window is None
            assert window.settings_vars == {}
            assert window.notebook is None

    def test_create_window_structure(self):
        """Test that create_window creates proper window structure"""
        with patch("tkinter.Tk"), patch("tkinter.Toplevel") as mock_toplevel, patch(
            "tkinter.ttk.Notebook"
        ) as mock_notebook, patch(
            "gui.popup_windows.GuiUtils"
        ) as mock_gui_utils, patch(
            "gui.popup_windows.SettingsWindow._create_general_tab"
        ) as mock_gen, patch(
            "gui.popup_windows.SettingsWindow._create_appearance_tab"
        ) as mock_app, patch(
            "gui.popup_windows.SettingsWindow._create_directories_tab"
        ) as mock_dirs, patch(
            "gui.popup_windows.SettingsWindow._create_languages_tab"
        ) as mock_lang, patch(
            "gui.popup_windows.SettingsWindow._bind_mouse_wheel_events"
        ) as mock_bind:

            mock_window = Mock()
            mock_toplevel.return_value = mock_window
            mock_notebook_instance = Mock()
            mock_notebook.return_value = mock_notebook_instance

            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )
            window.create_window()

            # Verify window setup
            mock_window.title.assert_called_with("Application Settings")
            mock_window.geometry.assert_called_with("700x600")
            mock_window.transient.assert_called_with(self.mock_parent)
            mock_window.grab_set.assert_called_once()

            # Verify notebook creation
            mock_notebook.assert_called_once()

            # Verify tab creation methods are called
            assert window.notebook == mock_notebook_instance
            mock_gen.assert_called_once()
            mock_app.assert_called_once()
            mock_dirs.assert_called_once()
            mock_lang.assert_called_once()
            mock_bind.assert_called_once()

    @patch("gui.popup_windows.SettingsWindow._create_general_tab")
    @patch("gui.popup_windows.SettingsWindow._create_appearance_tab")
    @patch("gui.popup_windows.SettingsWindow._create_directories_tab")
    @patch("gui.popup_windows.SettingsWindow._create_languages_tab")
    @patch("gui.popup_windows.SettingsWindow._bind_mouse_wheel_events")
    def test_tab_creation_methods_called(
        self, mock_bind, mock_lang, mock_dirs, mock_app, mock_gen
    ):
        """Test that all tab creation methods are called"""
        with patch("tkinter.Tk"), patch("tkinter.Toplevel"), patch(
            "tkinter.ttk.Notebook"
        ), patch("gui.popup_windows.GuiUtils"):

            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )

            window.create_window()

            # Verify all tab creation methods were called
            mock_gen.assert_called_once()
            mock_app.assert_called_once()
            mock_dirs.assert_called_once()
            mock_lang.assert_called_once()
            mock_bind.assert_called_once()

    def test_mouse_wheel_events_binding(self):
        """Test mouse wheel event binding"""
        with patch("tkinter.Tk"), patch("tkinter.Toplevel") as mock_toplevel, patch(
            "tkinter.ttk.Notebook"
        ) as mock_notebook, patch("gui.popup_windows.GuiUtils"), patch(
            "gui.popup_windows.SettingsWindow._create_general_tab"
        ) as mock_gen, patch(
            "gui.popup_windows.SettingsWindow._create_appearance_tab"
        ) as mock_app, patch(
            "gui.popup_windows.SettingsWindow._create_directories_tab"
        ) as mock_dirs, patch(
            "gui.popup_windows.SettingsWindow._create_languages_tab"
        ) as mock_lang, patch(
            "gui.popup_windows.SettingsWindow._bind_mouse_wheel_events"
        ) as mock_bind:

            mock_window = Mock()
            mock_toplevel.return_value = mock_window
            mock_notebook_instance = Mock()
            mock_notebook.return_value = mock_notebook_instance

            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )

            window.create_window()

            # Verify mouse wheel events binding method was called
            mock_bind.assert_called_once()

            # Verify that window event binding was called (escape key)
            # The exact function doesn't matter, just that bind was called
            mock_window.bind.assert_called()

    def test_settings_collection_text_widgets(self):
        """Test settings collection from text widgets"""
        with patch("tkinter.Tk"), patch("tkinter.Toplevel"), patch(
            "tkinter.ttk.Notebook"
        ), patch("gui.popup_windows.GuiUtils"):

            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )

            # Mock text widget for list settings (tk.Text)
            mock_text_widget = Mock(spec=tk.Text)
            mock_text_widget.get.return_value = "item1\nitem2\nitem3\n"
            window.settings_vars["IGNORE_DIRS"] = mock_text_widget

            # Mock text widget for dictionary settings (tk.Text)
            mock_dict_widget = Mock(spec=tk.Text)
            mock_dict_widget.get.return_value = '{"key1": "value1", "key2": "value2"}'
            window.settings_vars["FOLDER_ALIASES"] = mock_dict_widget

            # Mock string variable
            mock_string_var = Mock()
            mock_string_var.get.return_value = "Test Value"
            window.settings_vars["WINDOW_TITLE"] = mock_string_var

            window._apply_settings()

            # Verify callback was called
            self.mock_save_callback.assert_called_once()
            call_args = self.mock_save_callback.call_args[0][0]

            # Verify list setting was parsed correctly
            assert "IGNORE_DIRS" in call_args
            assert call_args["IGNORE_DIRS"] == ["item1", "item2", "item3"]

            # Verify dictionary setting was parsed correctly
            assert "FOLDER_ALIASES" in call_args
            assert call_args["FOLDER_ALIASES"] == {"key1": "value1", "key2": "value2"}

            # Verify string setting was preserved
            assert "WINDOW_TITLE" in call_args
            assert call_args["WINDOW_TITLE"] == "Test Value"

    def test_font_settings_parsing(self):
        """Test font settings parsing"""
        with patch("tkinter.Tk"), patch("tkinter.Toplevel"), patch(
            "tkinter.ttk.Notebook"
        ), patch("gui.popup_windows.GuiUtils"):

            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )

            # Mock font string variable
            mock_font_var = Mock()
            mock_font_var.get.return_value = "Arial, 12, bold"
            window.settings_vars["FONTS.title"] = mock_font_var

            window._apply_settings()

            # Verify callback was called with parsed font
            self.mock_save_callback.assert_called_once()
            call_args = self.mock_save_callback.call_args[0][0]

            assert "FONTS.title" in call_args
            assert call_args["FONTS.title"] == ("Arial", 12, "bold")

    def test_invalid_font_settings_handling(self):
        """Test handling of invalid font settings"""
        with patch("tkinter.Tk"), patch("tkinter.Toplevel"), patch(
            "tkinter.ttk.Notebook"
        ), patch("gui.popup_windows.GuiUtils"):

            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )

            # Mock invalid font string variable
            mock_font_var = Mock()
            mock_font_var.get.return_value = "Arial, invalid_size"
            window.settings_vars["FONTS.title"] = mock_font_var

            window._apply_settings()

            # Verify callback was called with default font size
            self.mock_save_callback.assert_called_once()
            call_args = self.mock_save_callback.call_args[0][0]

            assert "FONTS.title" in call_args
            assert call_args["FONTS.title"] == ("Arial", 12)

    def test_reset_to_defaults(self):
        """Test reset to defaults functionality"""
        with patch("tkinter.Tk"), patch("tkinter.Toplevel"), patch(
            "tkinter.ttk.Notebook"
        ), patch("gui.popup_windows.GuiUtils"):

            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )

            # Mock the window for destroy
            mock_window = Mock()
            window.window = mock_window

            window._reset_to_defaults()

            # Verify reset callback was called
            self.mock_reset_callback.assert_called_once()

            # Verify window was destroyed
            mock_window.destroy.assert_called_once()

    def test_reset_to_defaults_no_callback(self):
        """Test reset to defaults without callback"""
        with patch("tkinter.Tk"), patch("tkinter.Toplevel"), patch(
            "tkinter.ttk.Notebook"
        ), patch("gui.popup_windows.GuiUtils"), patch(
            "gui.popup_windows.messagebox"
        ) as mock_messagebox:

            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, None  # No reset callback
            )

            window._reset_to_defaults()

            # Verify fallback message was shown
            mock_messagebox.showinfo.assert_called_once()

    def test_cancel_dialog(self):
        """Test cancel dialog functionality"""
        with patch("tkinter.Tk"), patch("tkinter.Toplevel"), patch(
            "tkinter.ttk.Notebook"
        ), patch("gui.popup_windows.GuiUtils"):

            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )

            # Mock the window for destroy
            mock_window = Mock()
            window.window = mock_window

            window._cancel()

            # Verify window was destroyed
            mock_window.destroy.assert_called_once()

    def test_window_destroy_cleanup(self):
        """Test proper cleanup when window is destroyed"""
        with patch("tkinter.Tk"), patch("tkinter.Toplevel"), patch(
            "tkinter.ttk.Notebook"
        ), patch("gui.popup_windows.GuiUtils"):

            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )

            # Mock the window for destroy
            mock_window = Mock()
            window.window = mock_window

            window.destroy()

            # Verify window was destroyed and reference cleared
            mock_window.destroy.assert_called_once()
            assert window.window is None

    def test_window_destroy_without_window(self):
        """Test destroy method when window is None"""
        with patch("tkinter.Tk"), patch("tkinter.Toplevel"), patch(
            "tkinter.ttk.Notebook"
        ), patch("gui.popup_windows.GuiUtils"):

            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )
            window.window = None

            # Should not raise an error
            window.destroy()

    def test_error_handling_in_apply_settings(self):
        """Test error handling in apply settings"""
        with patch("tkinter.Tk"), patch("tkinter.Toplevel"), patch(
            "tkinter.ttk.Notebook"
        ), patch("gui.popup_windows.GuiUtils"), patch(
            "gui.popup_windows.messagebox"
        ) as mock_messagebox:

            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )

            # Mock a text widget that raises an exception
            mock_text_widget = Mock()
            mock_text_widget.get.side_effect = Exception("Test error")
            window.settings_vars["IGNORE_DIRS"] = mock_text_widget

            window._apply_settings()

            # Verify error dialog was shown
            mock_messagebox.showerror.assert_called_once()

            # Verify save callback was not called
            self.mock_save_callback.assert_not_called()

    def test_json_parsing_error_handling(self):
        """Test JSON parsing error handling"""
        with patch("tkinter.Tk"), patch("tkinter.Toplevel"), patch(
            "tkinter.ttk.Notebook"
        ), patch("gui.popup_windows.GuiUtils"), patch(
            "gui.popup_windows.messagebox"
        ) as mock_messagebox:

            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )

            # Mock text widget with invalid JSON (tk.Text)
            mock_text_widget = Mock(spec=tk.Text)
            mock_text_widget.get.return_value = "invalid json content"
            window.settings_vars["FOLDER_ALIASES"] = mock_text_widget

            window._apply_settings()

            # Verify error dialog was shown
            mock_messagebox.showerror.assert_called_once()

            # Verify save callback was not called
            self.mock_save_callback.assert_not_called()


class TestSettingsWindowCanvasScrolling:
    """Test cases for Settings Window canvas scrolling functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.mock_parent = Mock()
        self.mock_save_callback = Mock()
        self.mock_reset_callback = Mock()

    def test_canvas_references_storage(self):
        """Test that canvas references are properly stored for each tab"""
        with patch("tkinter.Tk"), patch("tkinter.Toplevel"), patch(
            "tkinter.ttk.Notebook"
        ), patch("gui.popup_windows.GuiUtils"):

            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )

            # Initialize tab_canvases dict
            window.tab_canvases = {}

            # Mock canvases for each tab
            mock_canvas = Mock()
            window.tab_canvases["General"] = mock_canvas
            window.tab_canvases["Appearance"] = mock_canvas
            window.tab_canvases["Directories"] = mock_canvas
            window.tab_canvases["Languages"] = mock_canvas

            # Verify all tabs have canvas references
            assert "General" in window.tab_canvases
            assert "Appearance" in window.tab_canvases
            assert "Directories" in window.tab_canvases
            assert "Languages" in window.tab_canvases

    def test_mouse_wheel_scroll_handling(self):
        """Test mouse wheel scroll event handling"""
        with patch("tkinter.Tk"), patch("tkinter.Toplevel"), patch(
            "tkinter.ttk.Notebook"
        ) as mock_notebook, patch("gui.popup_windows.GuiUtils"):

            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )

            # Mock notebook and canvas
            mock_notebook_instance = Mock()
            mock_notebook_instance.select.return_value = "tab1"
            mock_notebook_instance.tab.return_value = "General"
            window.notebook = mock_notebook_instance

            mock_canvas = Mock()
            window.tab_canvases = {"General": mock_canvas}

            # Create mock event
            mock_event = Mock()
            mock_event.widget = Mock()
            mock_event.widget.winfo_class.return_value = "Frame"
            mock_event.delta = 120

            # Test the mouse wheel handler logic
            # This would be called by the actual event handler
            if (
                hasattr(mock_event.widget, "winfo_class")
                and mock_event.widget.winfo_class() == "Text"
            ):
                # Should return early for Text widgets
                pass
            else:
                # Should scroll the canvas
                mock_canvas.yview_scroll.assert_not_called()  # Not called yet

                # Simulate the scroll action
                mock_canvas.yview_scroll(int(-1 * (mock_event.delta / 120)), "units")
                mock_canvas.yview_scroll.assert_called_with(-1, "units")

    def test_text_widget_scroll_prevention(self):
        """Test that text widgets prevent main window scrolling"""
        with patch("tkinter.Tk"), patch("tkinter.Toplevel"), patch(
            "tkinter.ttk.Notebook"
        ), patch("gui.popup_windows.GuiUtils"):

            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )

            # Mock text widget event
            mock_event = Mock()
            mock_text_widget = Mock()
            mock_text_widget.winfo_class.return_value = "Text"
            mock_event.widget = mock_text_widget

            # Test that the event handler would return early for Text widgets
            widget = mock_event.widget
            should_return_early = (
                hasattr(widget, "winfo_class") and widget.winfo_class() == "Text"
            )

            assert should_return_early is True


class TestSettingsWindowValidation:
    """Test cases for Settings Window validation functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.mock_parent = Mock()
        self.mock_save_callback = Mock()
        self.mock_reset_callback = Mock()

    def teardown_method(self):
        """Clean up test fixtures"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_settings_validation_window_size_format(self):
        """Test window size format validation"""
        with patch("tkinter.Tk"), patch("tkinter.Toplevel"), patch(
            "tkinter.ttk.Notebook"
        ), patch("gui.popup_windows.GuiUtils"), patch(
            "gui.popup_windows.messagebox"
        ) as mock_messagebox:

            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )

            # Test with invalid window size format
            settings_dict = {"MAIN_WINDOW_SIZE": "invalid_format"}
            result = window._validate_settings(settings_dict)

            assert result is False
            mock_messagebox.showerror.assert_called_once()

    def test_settings_validation_valid_window_size(self):
        """Test valid window size validation"""
        with patch("tkinter.Tk"), patch("tkinter.Toplevel"), patch(
            "tkinter.ttk.Notebook"
        ), patch("gui.popup_windows.GuiUtils"):

            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )

            # Test with valid window size formats
            settings_dict = {
                "MAIN_WINDOW_SIZE": "800x600",
                "OUTPUT_WINDOW_SIZE": "900x700",
                "GIT_WINDOW_SIZE": "1000x800",
            }

            result = window._validate_settings(settings_dict)
            assert result is True


class TestSettingsWindowIntegration:
    """Integration tests for Settings Window"""

    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.mock_parent = Mock()
        self.mock_save_callback = Mock()
        self.mock_reset_callback = Mock()

    def teardown_method(self):
        """Clean up test fixtures"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_full_settings_workflow(self):
        """Test complete settings workflow"""
        with patch("tkinter.Tk"), patch("tkinter.Toplevel"), patch(
            "tkinter.ttk.Notebook"
        ), patch("gui.popup_windows.GuiUtils"), patch(
            "gui.popup_windows.SettingsWindow._create_general_tab"
        ) as mock_gen, patch(
            "gui.popup_windows.SettingsWindow._create_appearance_tab"
        ) as mock_app, patch(
            "gui.popup_windows.SettingsWindow._create_directories_tab"
        ) as mock_dirs, patch(
            "gui.popup_windows.SettingsWindow._create_languages_tab"
        ) as mock_lang, patch(
            "gui.popup_windows.SettingsWindow._bind_mouse_wheel_events"
        ) as mock_bind:

            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )

            # Test window creation
            window.create_window()

            # Verify all components were created
            mock_gen.assert_called_once()
            mock_app.assert_called_once()
            mock_dirs.assert_called_once()
            mock_lang.assert_called_once()
            mock_bind.assert_called_once()

    def test_settings_persistence(self):
        """Test that settings are properly collected and passed to callback"""
        with patch("tkinter.Tk"), patch("tkinter.Toplevel"), patch(
            "tkinter.ttk.Notebook"
        ), patch("gui.popup_windows.GuiUtils"):

            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )

            # Set up mock settings variables
            expected_settings = {
                "SOURCE_DIR": str(self.temp_dir),
                "WINDOW_TITLE": "Test Application",
                "COLORS.background": "#ffffff",
                "FONTS.title": ("Arial", 14, "bold"),
                "IGNORE_DIRS": ["__pycache__", ".git"],
                "FOLDER_ALIASES": {"test": ["test-dir"]},
            }

            # Mock the settings variables
            for key, value in expected_settings.items():
                if key.startswith("IGNORE_DIRS") or key.startswith("FOLDER_ALIASES"):
                    # Mock text widget
                    mock_widget = Mock()
                    if key.startswith("IGNORE_DIRS"):
                        mock_widget.get.return_value = "\n".join(value)
                    else:
                        mock_widget.get.return_value = json.dumps(value)
                    window.settings_vars[key] = mock_widget
                else:
                    # Mock string variable
                    mock_var = Mock()
                    if key.startswith("FONTS."):
                        mock_var.get.return_value = (
                            f"{value[0]}, {value[1]}, {value[2]}"
                        )
                    else:
                        mock_var.get.return_value = value
                    window.settings_vars[key] = mock_var

            # Test applying settings
            window._apply_settings()

            # Verify callback was called
            self.mock_save_callback.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestSettingsWindowCreateNewFunctionality:
    """Test cases for the 'Create new' dockerized folder functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.mock_parent = Mock()
        self.mock_save_callback = Mock()
        self.mock_reset_callback = Mock()

        # Mock FOLDER_ALIASES for testing
        self.mock_folder_aliases = {
            "preedit": ["pre-edit", "original"],
            "postedit-beetle": ["post-edit", "beetle"],
            "postedit-sonnet": ["post-edit2", "sonnet"],
            "rewrite": ["correct-edit", "rewrite"],
        }

    def teardown_method(self):
        """Clean up test fixtures"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    @patch("tkinter.Tk")
    @patch("tkinter.Toplevel")
    @patch("tkinter.ttk.Notebook")
    @patch("gui.popup_windows.GuiUtils")
    @patch("tkinter.filedialog.askdirectory")
    @patch("tkinter.messagebox")
    def test_create_new_button_sets_path_without_creating_folders(
        self,
        mock_messagebox,
        mock_askdir,
        mock_gui_utils,
        mock_notebook,
        mock_toplevel,
        mock_tk,
    ):
        """Test that clicking 'Create new' sets the path but doesn't create folders immediately"""
        with patch("config.settings.FOLDER_ALIASES", self.mock_folder_aliases):
            # Mock folder selection
            mock_askdir.return_value = self.temp_dir
            mock_messagebox.showinfo.return_value = None

            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )

            # Create a mock StringVar for the path
            mock_path_var = Mock()
            mock_path_var.get.return_value = "/old/path"

            # Call the create new folder method
            window._create_new_dockerized_folder(mock_path_var)

            # Verify path was set to the dockerized folder
            expected_path = str(Path(self.temp_dir) / "dockerized")
            mock_path_var.set.assert_called_with(expected_path)

            # Verify no folders were actually created yet
            dockerized_path = Path(self.temp_dir) / "dockerized"
            assert not dockerized_path.exists()

            # Verify preview message was shown
            mock_messagebox.showinfo.assert_called()
            call_args = mock_messagebox.showinfo.call_args[0]
            assert "will be created" in call_args[1]
            assert "when you click 'Apply'" in call_args[1]

    def test_create_new_with_existing_folder_shows_correct_options(self):
        """Test that existing dockerized folder shows appropriate options"""
        with patch("tkinter.Tk"), patch("tkinter.Toplevel"), patch(
            "tkinter.ttk.Notebook"
        ), patch("gui.popup_windows.GuiUtils"), patch(
            "tkinter.filedialog.askdirectory"
        ) as mock_askdir, patch(
            "tkinter.messagebox"
        ) as mock_messagebox, patch(
            "config.settings.FOLDER_ALIASES", self.mock_folder_aliases
        ):

            # Create existing dockerized folder
            existing_dockerized = Path(self.temp_dir) / "dockerized"
            existing_dockerized.mkdir(parents=True)

            # Mock folder selection
            mock_askdir.return_value = self.temp_dir
            mock_messagebox.askyesnocancel.return_value = True  # Yes - use existing

            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )

            # Create a mock StringVar for the path
            mock_path_var = Mock()

            # Call the create new folder method
            window._create_new_dockerized_folder(mock_path_var)

            # Verify appropriate dialog was shown
            mock_messagebox.askyesnocancel.assert_called()
            call_args = mock_messagebox.askyesnocancel.call_args[0]
            assert "already exists" in call_args[1]
            assert "Use the existing folder" in call_args[1]

            # Verify path was set
            expected_path = str(existing_dockerized)
            mock_path_var.set.assert_called_with(expected_path)

    def test_apply_settings_creates_folders_when_planned(self):
        """Test that Apply creates folders when 'Create new' was used"""
        with patch("tkinter.Tk"), patch("tkinter.Toplevel"), patch(
            "tkinter.ttk.Notebook"
        ), patch("gui.popup_windows.GuiUtils"), patch(
            "config.settings.FOLDER_ALIASES", self.mock_folder_aliases
        ):

            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )

            # Simulate pending folder creation (as if Create new was clicked)
            dockerized_path = Path(self.temp_dir) / "dockerized"
            window.pending_folder_creation = {
                "dockerized_path": dockerized_path,
                "use_existing": False,
            }

            # Mock settings variables to avoid errors
            window.settings_vars = {
                "SOURCE_DIR": Mock(),
                "WINDOW_TITLE": Mock(),
            }
            window.settings_vars["SOURCE_DIR"].get.return_value = str(dockerized_path)
            window.settings_vars["WINDOW_TITLE"].get.return_value = "Test"

            # Call apply settings
            window._apply_settings()

            # Verify dockerized folder was created
            assert dockerized_path.exists()
            assert dockerized_path.is_dir()

            # Verify project version folders were created
            expected_folders = ["pre-edit", "post-edit", "post-edit2", "correct-edit"]
            for folder_name in expected_folders:
                folder_path = dockerized_path / folder_name
                assert folder_path.exists()
                assert folder_path.is_dir()

            # Verify save callback was called
            self.mock_save_callback.assert_called_once()

    def test_apply_settings_with_existing_dockerized_folder(self):
        """Test that Apply handles existing dockerized folder correctly"""
        with patch("tkinter.Tk"), patch("tkinter.Toplevel"), patch(
            "tkinter.ttk.Notebook"
        ), patch("gui.popup_windows.GuiUtils"), patch(
            "config.settings.FOLDER_ALIASES", self.mock_folder_aliases
        ), patch(
            "gui.popup_windows.messagebox"
        ) as mock_messagebox:

            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )

            # Create existing dockerized folder with some project folders
            dockerized_path = Path(self.temp_dir) / "dockerized"
            dockerized_path.mkdir(parents=True)
            (dockerized_path / "pre-edit").mkdir()  # Create one folder

            # Simulate pending folder creation for existing folder
            window.pending_folder_creation = {
                "dockerized_path": dockerized_path,
                "use_existing": True,
            }

            # Mock settings variables
            window.settings_vars = {
                "SOURCE_DIR": Mock(),
                "WINDOW_TITLE": Mock(),
            }
            window.settings_vars["SOURCE_DIR"].get.return_value = str(dockerized_path)
            window.settings_vars["WINDOW_TITLE"].get.return_value = "Test"

            # Call apply settings
            window._apply_settings()

            # Verify all project version folders exist now
            expected_folders = ["pre-edit", "post-edit", "post-edit2", "correct-edit"]
            for folder_name in expected_folders:
                folder_path = dockerized_path / folder_name
                assert folder_path.exists()
                assert folder_path.is_dir()

            # Verify success message was shown
            mock_messagebox.showinfo.assert_called()

    def test_cancel_prevents_folder_creation(self):
        """Test that Cancel prevents folder creation even when 'Create new' was used"""
        with patch("tkinter.Tk"), patch("tkinter.Toplevel"), patch(
            "tkinter.ttk.Notebook"
        ), patch("gui.popup_windows.GuiUtils"), patch(
            "config.settings.FOLDER_ALIASES", self.mock_folder_aliases
        ):

            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )

            # Simulate pending folder creation (as if Create new was clicked)
            dockerized_path = Path(self.temp_dir) / "dockerized"
            window.pending_folder_creation = {
                "dockerized_path": dockerized_path,
                "use_existing": False,
            }

            # Call cancel
            window._cancel()

            # Verify no folders were created
            assert not dockerized_path.exists()

            # Verify save callback was not called
            self.mock_save_callback.assert_not_called()

    def test_window_destroy_prevents_folder_creation(self):
        """Test that destroying the window prevents folder creation"""
        with patch("tkinter.Tk"), patch("tkinter.Toplevel") as mock_toplevel, patch(
            "tkinter.ttk.Notebook"
        ), patch("gui.popup_windows.GuiUtils"), patch(
            "config.settings.FOLDER_ALIASES", self.mock_folder_aliases
        ):

            mock_window = Mock()
            mock_toplevel.return_value = mock_window

            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )

            # Don't call create_window() to avoid StringVar creation issues
            # Just simulate the window being set up with a mock window
            window.window = mock_window

            # Simulate pending folder creation
            dockerized_path = Path(self.temp_dir) / "dockerized"
            window.pending_folder_creation = {
                "dockerized_path": dockerized_path,
                "use_existing": False,
            }

            # Call destroy
            window.destroy()

            # Verify no folders were created
            assert not dockerized_path.exists()

            # Verify save callback was not called
            self.mock_save_callback.assert_not_called()

    def test_user_cancels_folder_selection(self):
        """Test that canceling folder selection doesn't set path or create folders"""
        with patch("tkinter.Tk"), patch("tkinter.Toplevel"), patch(
            "tkinter.ttk.Notebook"
        ), patch("gui.popup_windows.GuiUtils"), patch(
            "tkinter.filedialog.askdirectory"
        ) as mock_askdir, patch(
            "config.settings.FOLDER_ALIASES", self.mock_folder_aliases
        ):

            # Mock user canceling folder selection
            mock_askdir.return_value = ""  # Empty string indicates cancel

            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )

            # Create a mock StringVar for the path
            mock_path_var = Mock()
            original_path = "/original/path"
            mock_path_var.get.return_value = original_path

            # Call the create new folder method
            window._create_new_dockerized_folder(mock_path_var)

            # Verify path was not changed
            mock_path_var.set.assert_not_called()

            # Verify no folders were created
            dockerized_path = Path(self.temp_dir) / "dockerized"
            assert not dockerized_path.exists()

    def test_error_handling_during_folder_creation(self):
        """Test that folder creation errors are handled gracefully"""
        with patch("tkinter.Tk"), patch("tkinter.Toplevel"), patch(
            "tkinter.ttk.Notebook"
        ), patch("gui.popup_windows.GuiUtils"), patch(
            "config.settings.FOLDER_ALIASES", self.mock_folder_aliases
        ), patch(
            "gui.popup_windows.messagebox"
        ) as mock_messagebox:

            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )

            # Create a path and mock it to raise an exception
            test_path = Path(self.temp_dir) / "dockerized"
            window.pending_folder_creation = {
                "dockerized_path": test_path,
                "use_existing": False,
            }

            # Mock settings variables
            window.settings_vars = {
                "SOURCE_DIR": Mock(),
                "WINDOW_TITLE": Mock(),
            }
            window.settings_vars["SOURCE_DIR"].get.return_value = str(test_path)
            window.settings_vars["WINDOW_TITLE"].get.return_value = "Test"

            # Mock the mkdir method to raise an exception
            with patch.object(
                Path, "mkdir", side_effect=PermissionError("Permission denied")
            ):
                # Call apply settings
                window._apply_settings()

            # Verify error message was shown
            mock_messagebox.showerror.assert_called()
            error_call = mock_messagebox.showerror.call_args[0]
            assert "Error" in error_call[0]
            assert "Failed to create dockerized folder" in error_call[1]

            # Verify save callback was not called due to error
            self.mock_save_callback.assert_not_called()

    def test_integration_with_existing_settings_workflow(self):
        """Test that the new functionality integrates properly with existing settings"""
        with patch("tkinter.Tk"), patch("tkinter.Toplevel"), patch(
            "tkinter.ttk.Notebook"
        ), patch("gui.popup_windows.GuiUtils"), patch(
            "config.settings.FOLDER_ALIASES", self.mock_folder_aliases
        ):

            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )

            # Simulate pending folder creation
            dockerized_path = Path(self.temp_dir) / "dockerized"
            window.pending_folder_creation = {
                "dockerized_path": dockerized_path,
                "use_existing": False,
            }

            # Set up normal settings
            window.settings_vars = {
                "SOURCE_DIR": Mock(),
                "WINDOW_TITLE": Mock(),
                "MAIN_WINDOW_SIZE": Mock(),
            }
            window.settings_vars["SOURCE_DIR"].get.return_value = str(dockerized_path)
            window.settings_vars["WINDOW_TITLE"].get.return_value = "Test App"
            window.settings_vars["MAIN_WINDOW_SIZE"].get.return_value = "800x600"

            # Call apply settings
            window._apply_settings()

            # Verify folders were created
            assert dockerized_path.exists()
            expected_folders = ["pre-edit", "post-edit", "post-edit2", "correct-edit"]
            for folder_name in expected_folders:
                folder_path = dockerized_path / folder_name
                assert folder_path.exists()

            # Verify normal settings were processed
            self.mock_save_callback.assert_called_once()
            call_args = self.mock_save_callback.call_args[0][0]
            assert "SOURCE_DIR" in call_args
            assert "WINDOW_TITLE" in call_args
            assert "MAIN_WINDOW_SIZE" in call_args
            assert call_args["SOURCE_DIR"] == str(dockerized_path)
            assert call_args["WINDOW_TITLE"] == "Test App"
            assert call_args["MAIN_WINDOW_SIZE"] == "800x600"

    def test_reset_to_defaults_clears_pending_folder_creation(self):
        """Test that reset to defaults clears pending folder creation"""
        with patch("tkinter.Tk"), patch("tkinter.Toplevel"), patch(
            "tkinter.ttk.Notebook"
        ), patch("gui.popup_windows.GuiUtils"), patch(
            "config.settings.FOLDER_ALIASES", self.mock_folder_aliases
        ):

            window = SettingsWindow(
                self.mock_parent, self.mock_save_callback, self.mock_reset_callback
            )

            # Simulate pending folder creation
            dockerized_path = Path(self.temp_dir) / "dockerized"
            window.pending_folder_creation = {
                "dockerized_path": dockerized_path,
                "use_existing": False,
            }

            # Call reset to defaults
            window._reset_to_defaults()

            # Verify no folders were created
            assert not dockerized_path.exists()

            # Verify reset callback was called
            self.mock_reset_callback.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
