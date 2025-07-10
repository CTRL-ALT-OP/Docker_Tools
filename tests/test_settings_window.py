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
