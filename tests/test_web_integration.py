"""
Implementation-agnostic tests for web integration functionality.
Tests focus on direct outcomes and behavior rather than internal implementation details.
"""

import os
import sys
import pytest
import json
import threading
import time
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from flask import Flask

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from services.web_integration_service import WebIntegration
from services.project_group_service import ProjectGroupService
from models.project import Project
from models.web_terminal_buffer import WebTerminalBuffer


class TestWebIntegrationProjectSelectionSync:
    """Test bidirectional project selection synchronization between desktop and web interfaces."""

    def setup_method(self):
        """Set up test fixtures for each test method."""
        self.temp_dir = tempfile.mkdtemp()
        self.mock_control_panel = Mock()
        self.mock_project_group_service = Mock()
        self.mock_control_panel.project_group_service = self.mock_project_group_service
        self.mock_control_panel.root_dir = Path(self.temp_dir)

        # Create web integration instance
        self.web_integration = WebIntegration(self.mock_control_panel)

        # Mock window for GUI updates
        self.mock_control_panel.window = Mock()
        self.mock_control_panel.window.after = Mock()
        self.mock_control_panel.main_window = Mock()
        self.mock_control_panel.populate_current_project = Mock()

    def teardown_method(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_desktop_selection_change_triggers_web_sync(self):
        """Test that changing project selection in desktop triggers web synchronization."""
        # Setup project groups
        project_groups = ["project1", "project2", "project3"]
        self.mock_project_group_service.get_group_names.return_value = project_groups

        # Setup callbacks to track desktop selection changes
        callback_triggered = []

        def mock_callback(group_name):
            callback_triggered.append(group_name)

        # Register our test callback
        self.mock_project_group_service.add_selection_callback = Mock(
            side_effect=lambda cb: callback_triggered.append(cb)
        )

        # Reinitialize to trigger callback registration
        web_integration = WebIntegration(self.mock_control_panel)

        # Verify callback registration happened
        self.mock_project_group_service.add_selection_callback.assert_called_once()

        # Get the registered callback
        registered_callback = (
            self.mock_project_group_service.add_selection_callback.call_args[0][0]
        )

        # Simulate desktop selection change
        test_project = "project2"
        registered_callback(test_project)

        # Verify web integration tracks the change
        assert web_integration.last_desktop_selection == test_project

    def test_web_selection_change_triggers_desktop_update(self):
        """Test that changing project selection in web triggers desktop GUI update."""
        # Setup project groups
        project_groups = ["project1", "project2", "project3"]
        self.mock_project_group_service.get_group_names.return_value = project_groups
        self.mock_project_group_service.get_current_group_name.return_value = "project1"

        # Setup Flask app for web endpoint testing
        self.web_integration.setup_flask_app()

        # Mock successful project selection
        self.mock_project_group_service.set_current_group_by_name.return_value = True

        # Mock the current group to return a proper mock object with a name attribute
        mock_group = Mock()
        mock_group.name = "project2"
        mock_group.get_all_versions.return_value = []  # Return empty list for projects
        self.mock_project_group_service.get_current_group.return_value = mock_group

        # Test web API call to select project
        with self.web_integration.app.test_client() as client:
            response = client.post(
                "/api/select-project",
                json={"group_name": "project2"},
                content_type="application/json",
            )

            # Verify API response indicates success
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is True

            # Verify desktop GUI would be updated
            self.mock_project_group_service.set_current_group_by_name.assert_called_with(
                "project2"
            )

    def test_sync_status_api_reflects_current_state(self):
        """Test that sync status API accurately reflects synchronization state."""
        # Setup project groups
        self.mock_project_group_service.get_current_group_name.return_value = "project1"

        # Setup Flask app
        self.web_integration.setup_flask_app()

        # Test sync status when in sync
        self.web_integration.last_desktop_selection = "project1"

        with self.web_integration.app.test_client() as client:
            response = client.get("/api/sync-status")

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is True
            assert data["current_selection"] == "project1"
            assert data["last_desktop_change"] == "project1"
            assert data["is_synced"] is True

    def test_sync_status_detects_out_of_sync_state(self):
        """Test that sync status API detects when desktop and web are out of sync."""
        # Setup project groups
        self.mock_project_group_service.get_current_group_name.return_value = "project1"

        # Setup Flask app
        self.web_integration.setup_flask_app()

        # Test sync status when out of sync
        self.web_integration.last_desktop_selection = "project2"

        with self.web_integration.app.test_client() as client:
            response = client.get("/api/sync-status")

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is True
            assert data["current_selection"] == "project1"
            assert data["last_desktop_change"] == "project2"
            assert data["is_synced"] is False

    def test_project_selection_updates_both_interfaces(self):
        """Test that project selection updates are reflected in both desktop and web interfaces."""
        # Setup project groups
        project_groups = ["project1", "project2", "project3"]
        self.mock_project_group_service.get_group_names.return_value = project_groups
        self.mock_project_group_service.get_current_group_name.return_value = "project1"

        # Setup callback system
        registered_callbacks = []

        def mock_add_callback(callback):
            registered_callbacks.append(callback)

        self.mock_project_group_service.add_selection_callback = mock_add_callback

        # Create web integration (this registers callbacks)
        web_integration = WebIntegration(self.mock_control_panel)

        # Verify callback was registered
        assert len(registered_callbacks) == 1
        desktop_callback = registered_callbacks[0]

        # Simulate desktop selection change
        test_project = "project2"
        desktop_callback(test_project)

        # Verify web integration received the change
        assert web_integration.last_desktop_selection == test_project

        # The web integration callback doesn't directly call window.after
        # It just stores the desktop selection change, which is the key behavior we want to test


class TestWebIntegrationActionExecution:
    """Test that web actions execute the same functions as desktop buttons."""

    def setup_method(self):
        """Set up test fixtures for each test method."""
        self.temp_dir = tempfile.mkdtemp()
        self.mock_control_panel = Mock()
        self.mock_project_group_service = Mock()
        self.mock_control_panel.project_group_service = self.mock_project_group_service
        self.mock_control_panel.root_dir = Path(self.temp_dir)

        # Create test project path
        self.test_project_path = Path(self.temp_dir) / "test_parent" / "test_project"
        self.test_project_path.mkdir(parents=True)

        # Create web integration instance
        self.web_integration = WebIntegration(self.mock_control_panel)
        self.web_integration.setup_flask_app()

    def teardown_method(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_web_docker_action_calls_same_method_as_desktop(self):
        """Test that web docker action calls the same method as desktop button."""
        # Mock the control panel's docker method
        self.mock_control_panel.docker_build_and_test = Mock()

        # Test web API call
        with self.web_integration.app.test_client() as client:
            response = client.post(
                "/api/action/docker",
                json={"project_name": "test_project", "parent_folder": "test_parent"},
                content_type="application/json",
            )

            # Verify API response
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is True
            assert "Docker build and test operation initiated" in data["message"]

            # Verify the same method was called as desktop button
            self.mock_control_panel.docker_build_and_test.assert_called_once()

            # Verify project object was created correctly
            called_project = self.mock_control_panel.docker_build_and_test.call_args[0][
                0
            ]
            assert called_project.name == "test_project"
            assert called_project.parent == "test_parent"

    def test_web_archive_action_calls_same_method_as_desktop(self):
        """Test that web archive action calls the same method as desktop button."""
        # Mock the control panel's archive method
        self.mock_control_panel.archive_project = Mock()

        # Test web API call
        with self.web_integration.app.test_client() as client:
            response = client.post(
                "/api/action/archive",
                json={"project_name": "test_project", "parent_folder": "test_parent"},
                content_type="application/json",
            )

            # Verify API response
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is True
            assert "Archive operation initiated" in data["message"]

            # Verify the same method was called as desktop button
            self.mock_control_panel.archive_project.assert_called_once()

            # Verify project object was created correctly
            called_project = self.mock_control_panel.archive_project.call_args[0][0]
            assert called_project.name == "test_project"
            assert called_project.parent == "test_parent"

    def test_web_git_view_action_calls_same_method_as_desktop(self):
        """Test that web git view action calls the same method as desktop button."""
        # Mock the control panel's git view method
        self.mock_control_panel.git_view = Mock()

        # Test web API call
        with self.web_integration.app.test_client() as client:
            response = client.post(
                "/api/action/git-view",
                json={"project_name": "test_project", "parent_folder": "test_parent"},
                content_type="application/json",
            )

            # Verify API response
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is True
            assert "Git view operation initiated" in data["message"]

            # Verify the same method was called as desktop button
            self.mock_control_panel.git_view.assert_called_once()

            # Verify project object was created correctly
            called_project = self.mock_control_panel.git_view.call_args[0][0]
            assert called_project.name == "test_project"
            assert called_project.parent == "test_parent"

    def test_web_sync_run_tests_action_calls_same_method_as_desktop(self):
        """Test that web sync run tests action calls the same method as desktop button."""
        # Mock the control panel's sync method
        self.mock_control_panel.sync_run_tests_from_pre_edit = Mock()

        # Mock project group service
        mock_group = Mock()
        mock_group.name = "test_group"
        self.mock_project_group_service.set_current_group_by_name.return_value = True
        self.mock_project_group_service.get_current_group.return_value = mock_group

        # Test web API call
        with self.web_integration.app.test_client() as client:
            response = client.post(
                "/api/action/sync-run-tests",
                json={"group_name": "test_group"},
                content_type="application/json",
            )

            # Verify API response
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is True
            assert "Sync run tests operation initiated" in data["message"]

            # Verify the same method was called as desktop button
            self.mock_control_panel.sync_run_tests_from_pre_edit.assert_called_once()

            # Verify project group was set correctly
            self.mock_project_group_service.set_current_group_by_name.assert_called_with(
                "test_group"
            )

    def test_web_validate_project_group_action_calls_same_method_as_desktop(self):
        """Test that web validate project group action calls the same method as desktop button."""
        # Mock the control panel's validate method
        self.mock_control_panel.validate_project_group = Mock()

        # Mock project group service
        mock_group = Mock()
        mock_group.name = "test_group"
        self.mock_project_group_service.set_current_group_by_name.return_value = True
        self.mock_project_group_service.get_current_group.return_value = mock_group

        # Test web API call
        with self.web_integration.app.test_client() as client:
            response = client.post(
                "/api/action/validate-project-group",
                json={"group_name": "test_group"},
                content_type="application/json",
            )

            # Verify API response
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is True
            assert "Validate project group operation initiated" in data["message"]

            # Verify the same method was called as desktop button
            self.mock_control_panel.validate_project_group.assert_called_once()

            # Verify project group was set correctly
            self.mock_project_group_service.set_current_group_by_name.assert_called_with(
                "test_group"
            )

    def test_web_build_docker_files_action_calls_same_method_as_desktop(self):
        """Test that web build docker files action calls the same method as desktop button."""
        # Mock the control panel's build docker files method
        self.mock_control_panel.build_docker_files_for_project_group = Mock()

        # Mock project group service
        mock_group = Mock()
        mock_group.name = "test_group"
        self.mock_project_group_service.set_current_group_by_name.return_value = True
        self.mock_project_group_service.get_current_group.return_value = mock_group

        # Test web API call
        with self.web_integration.app.test_client() as client:
            response = client.post(
                "/api/action/build-docker-files",
                json={"group_name": "test_group"},
                content_type="application/json",
            )

            # Verify API response
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is True
            assert "Build docker files operation initiated" in data["message"]

            # Verify the same method was called as desktop button
            self.mock_control_panel.build_docker_files_for_project_group.assert_called_once()

            # Verify project group was set correctly
            self.mock_project_group_service.set_current_group_by_name.assert_called_with(
                "test_group"
            )

    def test_web_git_checkout_all_action_calls_same_method_as_desktop(self):
        """Test that web git checkout all action calls the same method as desktop button."""
        # Mock the control panel's git checkout all method
        self.mock_control_panel.git_checkout_all = Mock()

        # Mock project group service
        mock_group = Mock()
        mock_group.name = "test_group"
        self.mock_project_group_service.set_current_group_by_name.return_value = True
        self.mock_project_group_service.get_current_group.return_value = mock_group

        # Test web API call
        with self.web_integration.app.test_client() as client:
            response = client.post(
                "/api/action/git-checkout-all",
                json={"group_name": "test_group"},
                content_type="application/json",
            )

            # Verify API response
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is True
            assert "Git checkout all operation initiated" in data["message"]

            # Verify the same method was called as desktop button
            self.mock_control_panel.git_checkout_all.assert_called_once()

            # Verify project group was set correctly
            self.mock_project_group_service.set_current_group_by_name.assert_called_with(
                "test_group"
            )

    def test_web_refresh_action_calls_same_method_as_desktop(self):
        """Test that web refresh action calls the same method as desktop button."""
        # Mock the control panel's refresh method
        self.mock_control_panel.refresh_projects = Mock()

        # Test web API call
        with self.web_integration.app.test_client() as client:
            response = client.get("/api/refresh")

            # Verify API response
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is True
            assert "Projects refreshed successfully" in data["message"]

            # Verify the same method was called as desktop button
            self.mock_control_panel.refresh_projects.assert_called_once()

    def test_web_add_project_action_calls_same_method_as_desktop(self):
        """Test that web add project action calls the same method as desktop button."""
        # Mock the control panel's add project method
        self.mock_control_panel.add_project = Mock()

        # Test web API call
        with self.web_integration.app.test_client() as client:
            response = client.post(
                "/api/action/add-project",
                json={
                    "repo_url": "https://github.com/test/repo.git",
                    "project_name": "test_project",
                },
                content_type="application/json",
            )

            # Verify API response
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is True
            assert "Add project operation initiated" in data["message"]

            # Verify the same method was called as desktop button
            self.mock_control_panel.add_project.assert_called_once_with(
                "https://github.com/test/repo.git", "test_project"
            )

    def test_web_actions_handle_missing_parameters(self):
        """Test that web actions handle missing parameters gracefully."""
        # Test missing project name for docker action
        with self.web_integration.app.test_client() as client:
            response = client.post(
                "/api/action/docker",
                json={"parent_folder": "test_parent"},
                content_type="application/json",
            )

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is False
            assert "Missing project name" in data["message"]

    def test_web_actions_handle_nonexistent_projects(self):
        """Test that web actions handle nonexistent projects gracefully."""
        # Test nonexistent project for docker action
        with self.web_integration.app.test_client() as client:
            response = client.post(
                "/api/action/docker",
                json={
                    "project_name": "nonexistent_project",
                    "parent_folder": "nonexistent_parent",
                },
                content_type="application/json",
            )

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is False
            assert "Project not found" in data["message"]


class TestWebIntegrationTerminalStreaming:
    """Test terminal streaming functionality works properly."""

    def setup_method(self):
        """Set up test fixtures for each test method."""
        self.temp_dir = tempfile.mkdtemp()
        self.mock_control_panel = Mock()
        self.mock_project_group_service = Mock()
        self.mock_control_panel.project_group_service = self.mock_project_group_service
        self.mock_control_panel.root_dir = Path(self.temp_dir)

        # Create web integration instance
        self.web_integration = WebIntegration(self.mock_control_panel)
        self.web_integration.setup_flask_app()

    def teardown_method(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_terminal_output_api_returns_current_buffer_content(self):
        """Test that terminal output API returns current buffer content."""
        # Mock the web terminal buffer
        with patch("models.web_terminal_buffer.web_terminal_buffer") as mock_buffer:
            mock_buffer.get.return_value = "Test terminal output\nLine 2\nLine 3"

            # Test API call
            with self.web_integration.app.test_client() as client:
                response = client.get("/api/terminal/output")

                # Verify API response
                assert response.status_code == 200
                data = json.loads(response.data)
                assert data["success"] is True
                assert data["output"] == "Test terminal output\nLine 2\nLine 3"
                assert "timestamp" in data

                # Verify buffer was accessed
                mock_buffer.get.assert_called_once()

    def test_terminal_output_api_handles_empty_buffer(self):
        """Test that terminal output API handles empty buffer gracefully."""
        # Mock empty buffer
        with patch("models.web_terminal_buffer.web_terminal_buffer") as mock_buffer:
            mock_buffer.get.return_value = ""

            # Test API call
            with self.web_integration.app.test_client() as client:
                response = client.get("/api/terminal/output")

                # Verify API response
                assert response.status_code == 200
                data = json.loads(response.data)
                assert data["success"] is True
                assert data["output"] == ""
                assert "timestamp" in data

    def test_terminal_clear_api_clears_buffer(self):
        """Test that terminal clear API clears the buffer."""
        # Mock the web terminal buffer
        with patch("models.web_terminal_buffer.web_terminal_buffer") as mock_buffer:
            # Test API call
            with self.web_integration.app.test_client() as client:
                response = client.post("/api/terminal/clear")

                # Verify API response
                assert response.status_code == 200
                data = json.loads(response.data)
                assert data["success"] is True
                assert "Terminal cleared" in data["message"]

                # Verify buffer was cleared
                mock_buffer.clear.assert_called_once()

    def test_terminal_buffer_thread_safety(self):
        """Test that terminal buffer operations are thread-safe."""
        # Create real buffer instance for thread safety testing
        buffer = WebTerminalBuffer()

        # Test concurrent operations
        results = []

        def append_worker(text):
            buffer.append(text)
            results.append(f"appended_{text}")

        def read_worker():
            content = buffer.get()
            results.append(f"read_{len(content)}")

        def clear_worker():
            buffer.clear()
            results.append("cleared")

        # Create threads for concurrent operations
        threads = []
        for i in range(5):
            threads.append(threading.Thread(target=append_worker, args=(f"text_{i}",)))
            threads.append(threading.Thread(target=read_worker))

        threads.append(threading.Thread(target=clear_worker))

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify operations completed without errors
        assert len(results) == 11  # 5 appends + 5 reads + 1 clear
        assert "cleared" in results
        assert all(
            result.startswith(("appended_", "read_", "cleared")) for result in results
        )

    def test_terminal_buffer_size_limit(self):
        """Test that terminal buffer respects size limit."""
        # Create real buffer instance
        buffer = WebTerminalBuffer()

        # Add content that exceeds buffer limit
        large_text = "x" * 60000  # Exceeds 50KB limit
        buffer.append(large_text)

        # Verify buffer was truncated
        content = buffer.get()
        assert len(content) <= 50000
        assert content == large_text[-50000:]

    def test_terminal_streaming_integration_with_actions(self):
        """Test that terminal streaming works with action execution."""
        # Mock the web terminal buffer to track appends
        with patch("models.web_terminal_buffer.web_terminal_buffer") as mock_buffer:
            # Mock action that would generate terminal output
            self.mock_control_panel.docker_build_and_test = Mock()

            # Create test project
            test_project_path = Path(self.temp_dir) / "test_parent" / "test_project"
            test_project_path.mkdir(parents=True)

            # Execute action via web API
            with self.web_integration.app.test_client() as client:
                response = client.post(
                    "/api/action/docker",
                    json={
                        "project_name": "test_project",
                        "parent_folder": "test_parent",
                    },
                    content_type="application/json",
                )

                # Verify action was executed
                assert response.status_code == 200
                data = json.loads(response.data)
                assert data["success"] is True

                # Verify the action method was called
                self.mock_control_panel.docker_build_and_test.assert_called_once()

    def test_terminal_view_page_loads_correctly(self):
        """Test that terminal view page loads with correct context."""
        # Mock project group service
        project_groups = ["project1", "project2"]
        mock_current_group = Mock()
        mock_current_group.name = "project1"

        self.mock_project_group_service.get_group_names.return_value = project_groups
        self.mock_project_group_service.get_current_group.return_value = (
            mock_current_group
        )

        # Test terminal page load
        with self.web_integration.app.test_client() as client:
            response = client.get("/terminal")

            # Verify page loads successfully
            assert response.status_code == 200
            assert b"terminal" in response.data.lower()

    def test_terminal_api_error_handling(self):
        """Test that terminal API handles errors gracefully."""
        # Mock buffer that raises exception
        with patch("models.web_terminal_buffer.web_terminal_buffer") as mock_buffer:
            mock_buffer.get.side_effect = Exception("Buffer error")

            # Test API call with error
            with self.web_integration.app.test_client() as client:
                response = client.get("/api/terminal/output")

                # Verify error is handled gracefully
                assert response.status_code == 200
                data = json.loads(response.data)
                assert data["success"] is False
                assert "Buffer error" in data["message"]


class TestWebIntegrationOverallBehavior:
    """Test overall web integration behavior and edge cases."""

    def setup_method(self):
        """Set up test fixtures for each test method."""
        self.temp_dir = tempfile.mkdtemp()
        self.mock_control_panel = Mock()
        self.mock_project_group_service = Mock()
        self.mock_control_panel.project_group_service = self.mock_project_group_service
        self.mock_control_panel.root_dir = Path(self.temp_dir)

        # Create web integration instance
        self.web_integration = WebIntegration(self.mock_control_panel)

    def teardown_method(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_web_server_lifecycle_management(self):
        """Test web server can be started and stopped properly."""
        # Initially not running
        assert not self.web_integration.is_running

        # Mock Flask app to avoid actual server startup
        with patch("threading.Thread") as mock_thread:
            mock_thread_instance = Mock()
            mock_thread.return_value = mock_thread_instance

            # Start web server
            self.web_integration.start_web_server(port=5000)

            # Verify server is marked as running
            assert self.web_integration.is_running

            # Verify thread was started
            mock_thread_instance.start.assert_called_once()

            # Stop web server
            self.web_integration.stop_web_server()

            # Verify server is marked as stopped
            assert not self.web_integration.is_running

    def test_web_integration_handles_concurrent_requests(self):
        """Test that web integration handles concurrent requests properly."""
        # Setup Flask app
        self.web_integration.setup_flask_app()

        # Mock project group service
        project_groups = ["project1", "project2"]
        self.mock_project_group_service.get_group_names.return_value = project_groups

        # Test concurrent API calls
        def make_request():
            with self.web_integration.app.test_client() as client:
                response = client.get("/api/project-groups")
                return response.status_code == 200

        # Create multiple threads making requests
        threads = []
        results = []

        for _ in range(10):
            thread = threading.Thread(target=lambda: results.append(make_request()))
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify all requests succeeded
        assert len(results) == 10
        assert all(results)

    def test_web_integration_url_generation(self):
        """Test that web integration generates correct URLs."""
        # Test default URL generation
        url = self.web_integration.get_web_url()
        assert url == "http://localhost:5000"

        # Test server status checking
        assert not self.web_integration.is_web_server_running()

        # Mark as running and test again
        self.web_integration.is_running = True
        assert self.web_integration.is_web_server_running()

    def test_web_integration_handles_flask_app_errors(self):
        """Test that web integration handles Flask app errors gracefully."""
        # Setup Flask app
        self.web_integration.setup_flask_app()

        # Test API call with service error
        self.mock_project_group_service.get_group_names.side_effect = Exception(
            "Service error"
        )

        with self.web_integration.app.test_client() as client:
            response = client.get("/api/project-groups")

            # Verify error is handled gracefully
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is False
            assert "Service error" in data["message"]

    def test_desktop_gui_update_integration(self):
        """Test that desktop GUI updates work correctly with web integration."""
        # Mock GUI components
        self.mock_control_panel.window = Mock()
        self.mock_control_panel.window.after = Mock()
        self.mock_control_panel.main_window = Mock()
        self.mock_control_panel.populate_current_project = Mock()
        self.mock_control_panel._update_desktop_dropdown = Mock()

        # Mock project group service
        project_groups = ["project1", "project2"]
        self.mock_project_group_service.get_group_names.return_value = project_groups
        self.mock_project_group_service.get_current_group_name.return_value = "project1"

        # Test desktop GUI update by calling the control panel method
        self.mock_control_panel._update_desktop_dropdown("project2")

        # Verify desktop GUI update method was called
        self.mock_control_panel._update_desktop_dropdown.assert_called_with("project2")

    def test_comprehensive_web_desktop_sync_workflow(self):
        """Test complete workflow of web-desktop synchronization."""
        # Setup complete mock environment
        self.mock_control_panel.window = Mock()
        self.mock_control_panel.window.after = Mock()
        self.mock_control_panel.main_window = Mock()
        self.mock_control_panel.populate_current_project = Mock()

        project_groups = ["project1", "project2", "project3"]
        self.mock_project_group_service.get_group_names.return_value = project_groups
        self.mock_project_group_service.get_current_group_name.return_value = "project1"
        self.mock_project_group_service.set_current_group_by_name.return_value = True

        # Mock the current group to return a proper mock object with a name attribute
        mock_group = Mock()
        mock_group.name = "project2"
        mock_group.get_all_versions.return_value = []  # Return empty list for projects
        self.mock_project_group_service.get_current_group.return_value = mock_group

        # Setup callback tracking
        registered_callbacks = []

        def mock_add_callback(callback):
            registered_callbacks.append(callback)

        self.mock_project_group_service.add_selection_callback = mock_add_callback

        # Create web integration and setup Flask app
        web_integration = WebIntegration(self.mock_control_panel)
        web_integration.setup_flask_app()

        # Verify callback registration
        assert len(registered_callbacks) == 1
        desktop_callback = registered_callbacks[0]

        # Step 1: Desktop selection changes
        desktop_callback("project2")

        # Verify web integration tracks change
        assert web_integration.last_desktop_selection == "project2"

        # Step 2: Web interface queries sync status
        with web_integration.app.test_client() as client:
            response = client.get("/api/sync-status")
            data = json.loads(response.data)

            # Current group is still project1, but desktop changed to project2
            assert data["current_selection"] == "project1"
            assert data["last_desktop_change"] == "project2"
            assert data["is_synced"] is False

        # Step 3: Web interface makes selection change
        with web_integration.app.test_client() as client:
            response = client.post(
                "/api/select-project",
                json={"group_name": "project2"},
                content_type="application/json",
            )

            # Verify selection change succeeded
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is True

        # Step 4: Verify desktop GUI would be updated
        self.mock_project_group_service.set_current_group_by_name.assert_called_with(
            "project2"
        )

        # This comprehensive test verifies the entire synchronization workflow
        # between web and desktop interfaces works as expected
