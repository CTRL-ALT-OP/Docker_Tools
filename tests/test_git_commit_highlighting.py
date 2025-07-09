"""
Tests for Git Commit Highlighting functionality

Tests the current commit highlighting feature in Git View windows,
ensuring it displays correctly in Git View but not in Git Checkout All.
These tests are implementation-agnostic and focus on outcomes.
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

from services.git_service import GitService, GitCommit, GitRepositoryInfo
from gui.popup_windows import GitCommitWindow, GitCheckoutAllWindow
from models.project import Project
from services.project_group_service import ProjectGroup
from utils.async_base import ServiceResult


class TestGitCommitHighlighting:
    """Test cases for Git Commit Highlighting functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.git_service = GitService()

        # Create a test project
        self.project_path = Path(self.temp_dir) / "test-project"
        self.project_path.mkdir(parents=True)

        self.test_project = Project(
            parent="test-parent",
            name="test-project",
            path=self.project_path,
            relative_path="test-parent/test-project",
        )

    def teardown_method(self):
        """Clean up test fixtures"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def create_mock_commits(self):
        """Create a set of mock commits for testing"""
        return [
            GitCommit(
                hash="a1b2c3d4",
                author="John Doe",
                date="2024-01-15",
                subject="Latest feature implementation",
                source_branch="master",
            ),
            GitCommit(
                hash="e5f6g7h8",
                author="Jane Smith",
                date="2024-01-14",
                subject="Bug fix for authentication",
                source_branch="feature/auth-fix",
            ),
            GitCommit(
                hash="i9j0k1l2",
                author="Bob Wilson",
                date="2024-01-13",
                subject="Initial project setup",
                source_branch="master",
            ),
        ]

    def create_mock_repo_info(self, current_commit="a1b2c3d4"):
        """Create mock repository information"""
        return GitRepositoryInfo(
            has_remote=True,
            remote_urls=["https://github.com/test/repo.git"],
            current_branch="master",
            current_commit=current_commit,
            is_clean=True,
            uncommitted_changes=0,
        )

    @patch("tkinter.Tk")
    @patch("tkinter.Toplevel")
    @patch("tkinter.Listbox")
    @patch("gui.popup_windows.GuiUtils")
    def test_git_view_highlights_current_commit_exact_match(
        self, mock_gui_utils, mock_listbox, mock_toplevel, mock_tk
    ):
        """Test that GitCommitWindow highlights the current commit when hashes match exactly"""
        # Setup mocks
        mock_parent = Mock()
        mock_listbox_instance = Mock()
        mock_listbox.return_value = mock_listbox_instance

        # Create test data
        commits = self.create_mock_commits()
        current_commit_hash = "a1b2c3d4"  # Matches first commit

        # Create GitCommitWindow
        git_window = GitCommitWindow(
            parent_window=mock_parent,
            project_name="test-project",
            commits=[],
            on_checkout_callback=Mock(),
            current_commit_hash=current_commit_hash,
        )

        # Set up the GUI component mocks
        git_window.commit_listbox = mock_listbox_instance
        git_window.status_label = Mock()
        git_window.checkout_btn = Mock()

        # Update with commits - this should trigger highlighting
        git_window.update_with_commits(commits, current_commit_hash)

        # Verify that insert was called for each commit
        assert mock_listbox_instance.insert.call_count == 3

        # Check that the first commit (current) has the highlight prefix
        first_insert_call = mock_listbox_instance.insert.call_args_list[0]
        inserted_text = first_insert_call[0][1]  # Second argument (text)
        assert ">> CURRENT:" in inserted_text
        assert "Latest feature implementation" in inserted_text

        # Check that other commits do NOT have the highlight prefix
        second_insert_call = mock_listbox_instance.insert.call_args_list[1]
        second_text = second_insert_call[0][1]
        assert ">> CURRENT:" not in second_text
        assert "Bug fix for authentication" in second_text

        # Verify that itemconfig was called to set background color for current commit
        mock_listbox_instance.itemconfig.assert_called_once_with(
            0, bg="#27ae60", fg="white"  # Green background, white text
        )

    @patch("tkinter.Tk")
    @patch("tkinter.Toplevel")
    @patch("tkinter.Listbox")
    @patch("gui.popup_windows.GuiUtils")
    def test_git_view_highlights_current_commit_partial_match(
        self, mock_gui_utils, mock_listbox, mock_toplevel, mock_tk
    ):
        """Test that GitCommitWindow highlights current commit when partial hashes match"""
        # Setup mocks
        mock_parent = Mock()
        mock_listbox_instance = Mock()
        mock_listbox.return_value = mock_listbox_instance

        # Create test data with different hash lengths
        commits = [
            GitCommit(
                hash="a1b2c3d",
                author="John Doe",
                date="2024-01-15",
                subject="Latest feature",
            ),
            GitCommit(
                hash="e5f6g7h8",
                author="Jane Smith",
                date="2024-01-14",
                subject="Bug fix",
            ),
        ]
        current_commit_hash = "a1b2c3d4"  # 8 chars, but commit hash is only 7

        # Create GitCommitWindow
        git_window = GitCommitWindow(
            parent_window=mock_parent,
            project_name="test-project",
            commits=[],
            on_checkout_callback=Mock(),
            current_commit_hash=current_commit_hash,
        )

        git_window.commit_listbox = mock_listbox_instance
        git_window.status_label = Mock()
        git_window.checkout_btn = Mock()
        git_window.update_with_commits(commits, current_commit_hash)

        # Verify highlighting occurs despite different hash lengths
        first_insert_call = mock_listbox_instance.insert.call_args_list[0]
        inserted_text = first_insert_call[0][1]
        assert ">> CURRENT:" in inserted_text

        # Verify background color was set
        mock_listbox_instance.itemconfig.assert_called_once_with(
            0, bg="#27ae60", fg="white"
        )

    @patch("tkinter.Tk")
    @patch("tkinter.Toplevel")
    @patch("tkinter.Listbox")
    @patch("gui.popup_windows.GuiUtils")
    def test_git_view_no_highlight_when_no_current_commit(
        self, mock_gui_utils, mock_listbox, mock_toplevel, mock_tk
    ):
        """Test that GitCommitWindow shows no highlighting when current commit is unknown"""
        # Setup mocks
        mock_parent = Mock()
        mock_listbox_instance = Mock()
        mock_listbox.return_value = mock_listbox_instance

        commits = self.create_mock_commits()

        # Create GitCommitWindow with no current commit
        git_window = GitCommitWindow(
            parent_window=mock_parent,
            project_name="test-project",
            commits=[],
            on_checkout_callback=Mock(),
            current_commit_hash=None,
        )

        git_window.commit_listbox = mock_listbox_instance
        git_window.status_label = Mock()
        git_window.checkout_btn = Mock()
        git_window.update_with_commits(commits, None)

        # Verify that NO commits have the highlight prefix
        for call in mock_listbox_instance.insert.call_args_list:
            inserted_text = call[0][1]
            assert ">> CURRENT:" not in inserted_text

        # Verify that itemconfig was NOT called (no highlighting)
        mock_listbox_instance.itemconfig.assert_not_called()

    @patch("tkinter.Tk")
    @patch("tkinter.Toplevel")
    @patch("tkinter.Listbox")
    @patch("gui.popup_windows.GuiUtils")
    def test_git_view_no_highlight_when_no_match(
        self, mock_gui_utils, mock_listbox, mock_toplevel, mock_tk
    ):
        """Test that GitCommitWindow shows no highlighting when current commit doesn't match any in list"""
        # Setup mocks
        mock_parent = Mock()
        mock_listbox_instance = Mock()
        mock_listbox.return_value = mock_listbox_instance

        commits = self.create_mock_commits()
        current_commit_hash = "z9z9z9z9"  # Doesn't match any commit

        # Create GitCommitWindow
        git_window = GitCommitWindow(
            parent_window=mock_parent,
            project_name="test-project",
            commits=[],
            on_checkout_callback=Mock(),
            current_commit_hash=current_commit_hash,
        )

        git_window.commit_listbox = mock_listbox_instance
        git_window.status_label = Mock()
        git_window.checkout_btn = Mock()
        git_window.update_with_commits(commits, current_commit_hash)

        # Verify that NO commits have the highlight prefix
        for call in mock_listbox_instance.insert.call_args_list:
            inserted_text = call[0][1]
            assert ">> CURRENT:" not in inserted_text

        # Verify that itemconfig was NOT called (no highlighting)
        mock_listbox_instance.itemconfig.assert_not_called()

    @patch("tkinter.Tk")
    @patch("tkinter.Toplevel")
    @patch("tkinter.Listbox")
    @patch("gui.popup_windows.GuiUtils")
    def test_git_checkout_all_never_highlights_commits(
        self, mock_gui_utils, mock_listbox, mock_toplevel, mock_tk
    ):
        """Test that GitCheckoutAllWindow NEVER highlights commits (per requirements)"""
        # Setup mocks
        mock_parent = Mock()
        mock_listbox_instance = Mock()
        mock_listbox.return_value = mock_listbox_instance

        commits = self.create_mock_commits()
        current_commit_hash = "a1b2c3d4"  # Matches first commit

        # Create GitCheckoutAllWindow (should not highlight even with matching commit)
        git_checkout_window = GitCheckoutAllWindow(
            parent_window=mock_parent,
            project_group_name="test-project-group",
            commits=[],
            on_checkout_all_callback=Mock(),
            all_versions=[self.test_project],
        )

        git_checkout_window.commit_listbox = mock_listbox_instance
        git_checkout_window.update_with_commits(commits)

        # Verify that NO commits have the highlight prefix (GitCheckoutAllWindow doesn't support highlighting)
        for call in mock_listbox_instance.insert.call_args_list:
            inserted_text = call[0][1]
            assert ">> CURRENT:" not in inserted_text

        # Verify that itemconfig was NOT called (no highlighting in checkout all)
        mock_listbox_instance.itemconfig.assert_not_called()

    @patch("tkinter.Tk")
    @patch("tkinter.Toplevel")
    @patch("tkinter.Listbox")
    @patch("gui.popup_windows.GuiUtils")
    def test_git_view_status_message_updates_with_highlighting(
        self, mock_gui_utils, mock_listbox, mock_toplevel, mock_tk
    ):
        """Test that GitCommitWindow status message indicates when highlighting is active"""
        # Setup mocks
        mock_parent = Mock()
        mock_listbox_instance = Mock()
        mock_listbox.return_value = mock_listbox_instance
        mock_status_label = Mock()

        commits = self.create_mock_commits()
        current_commit_hash = "a1b2c3d4"

        # Create GitCommitWindow
        git_window = GitCommitWindow(
            parent_window=mock_parent,
            project_name="test-project",
            commits=[],
            on_checkout_callback=Mock(),
            current_commit_hash=current_commit_hash,
        )

        git_window.commit_listbox = mock_listbox_instance
        git_window.status_label = mock_status_label
        git_window.checkout_btn = Mock()
        git_window.update_with_commits(commits, current_commit_hash)

        # Verify that status message indicates highlighting is active
        status_call = mock_status_label.config.call_args
        status_text = status_call[1]["text"]  # keyword argument 'text'
        assert "current commit highlighted" in status_text
        assert "3 total" in status_text

    @patch("tkinter.Tk")
    @patch("tkinter.Toplevel")
    @patch("tkinter.Listbox")
    @patch("gui.popup_windows.GuiUtils")
    def test_git_view_status_message_no_highlighting_indicator_when_no_current(
        self, mock_gui_utils, mock_listbox, mock_toplevel, mock_tk
    ):
        """Test that GitCommitWindow status message doesn't mention highlighting when no current commit"""
        # Setup mocks
        mock_parent = Mock()
        mock_listbox_instance = Mock()
        mock_listbox.return_value = mock_listbox_instance
        mock_status_label = Mock()

        commits = self.create_mock_commits()

        # Create GitCommitWindow with no current commit
        git_window = GitCommitWindow(
            parent_window=mock_parent,
            project_name="test-project",
            commits=[],
            on_checkout_callback=Mock(),
            current_commit_hash=None,
        )

        git_window.commit_listbox = mock_listbox_instance
        git_window.status_label = mock_status_label
        git_window.checkout_btn = Mock()
        git_window.update_with_commits(commits, None)

        # Verify that status message does NOT mention highlighting
        status_call = mock_status_label.config.call_args
        status_text = status_call[1]["text"]
        assert "current" not in status_text
        assert "3 total" in status_text

    def test_different_hash_length_scenarios(self):
        """Test highlighting works with various git hash length combinations"""
        test_cases = [
            # (current_commit, commit_hash, should_highlight, description)
            ("a1b2c3d4", "a1b2c3d4", True, "Exact 8-char match"),
            ("a1b2c3d4", "a1b2c3d4e5f6", True, "8-char current vs longer commit"),
            ("a1b2c3d4e5f6", "a1b2c3d4", True, "Longer current vs 8-char commit"),
            ("a1b2c3d", "a1b2c3d4", True, "7-char vs 8-char"),
            ("a1b2c3d4", "a1b2c3d", True, "8-char vs 7-char"),
            ("a1b2c3d4", "b2c3d4e5", False, "Different hashes"),
            ("", "a1b2c3d4", False, "Empty current hash"),
            ("a1b2c3d4", "", False, "Empty commit hash"),
            (None, "a1b2c3d4", False, "None current hash"),
            ("unknown", "a1b2c3d4", False, "Unknown current hash"),
        ]

        for current_commit, commit_hash, expected_highlight, description in test_cases:
            with patch("tkinter.Tk"), patch("tkinter.Toplevel"), patch(
                "tkinter.Listbox"
            ) as mock_listbox:
                mock_listbox_instance = Mock()
                mock_listbox.return_value = mock_listbox_instance

                # Create a single commit with the test hash
                test_commit = GitCommit(
                    hash=commit_hash if commit_hash else "dummy",
                    author="Test Author",
                    date="2024-01-15",
                    subject="Test commit",
                )

                git_window = GitCommitWindow(
                    parent_window=Mock(),
                    project_name="test-project",
                    commits=[],
                    on_checkout_callback=Mock(),
                    current_commit_hash=current_commit,
                )

                git_window.commit_listbox = mock_listbox_instance
                git_window.status_label = Mock()
                git_window.checkout_btn = Mock()
                git_window.update_with_commits([test_commit], current_commit)

                # Check the result
                if expected_highlight:
                    # Should have highlighting
                    insert_call = mock_listbox_instance.insert.call_args_list[0]
                    inserted_text = insert_call[0][1]
                    assert ">> CURRENT:" in inserted_text, f"Failed case: {description}"
                    mock_listbox_instance.itemconfig.assert_called_once()
                else:
                    # Should NOT have highlighting
                    insert_call = mock_listbox_instance.insert.call_args_list[0]
                    inserted_text = insert_call[0][1]
                    assert (
                        ">> CURRENT:" not in inserted_text
                    ), f"Failed case: {description}"
                    mock_listbox_instance.itemconfig.assert_not_called()
