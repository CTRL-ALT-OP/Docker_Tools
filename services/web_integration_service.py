"""
Web Integration Module for Docker Tools
Embeds Flask web server into the main ProjectControlPanel application
"""

import os
import json
import threading
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import time

from flask import Flask, render_template, request, jsonify, Response
from models.project import Project


logger = logging.getLogger(__name__)

# Suppress Flask's default info level logging
log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)

service_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(service_dir)

template_dir = os.path.join(root_dir, "templates")
static_dir = os.path.join(root_dir, "static")


class WebIntegration:
    """Web interface integration for ProjectControlPanel"""

    def __init__(self, control_panel):
        """Initialize web integration with reference to main control panel"""
        self.control_panel = control_panel
        self.app = None
        self.web_thread = None
        self.is_running = False
        self.last_desktop_selection = None

        # Register callback for desktop selection changes
        self._setup_desktop_sync_callback()

    def _setup_desktop_sync_callback(self):
        """Set up callback to sync desktop selection changes to web"""

        def on_desktop_selection_change(group_name: str):
            """Handle desktop selection changes"""
            self.last_desktop_selection = group_name
            logger.info(f"Desktop selection changed to: {group_name}")

        # Register the callback with the project group service
        self.control_panel.project_group_service.add_selection_callback(
            on_desktop_selection_change
        )

    def _generate_dynamic_css(self):
        """Generate CSS with dynamic values from settings.py"""
        from config.settings import COLORS, FONTS, BUTTON_STYLES

        # All COLORS keys (including terminal-specific) are injected as CSS variables below
        # Convert colors to CSS variables
        color_vars = []
        for key, value in COLORS.items():
            css_var_name = key.replace("_", "-")
            color_vars.append(f"    --{css_var_name}: {value};")

        # Convert button styles to CSS variables
        button_vars = []
        for button_type, styles in BUTTON_STYLES.items():
            for style_prop, value in styles.items():
                css_var_name = f"{button_type}-{style_prop}".replace("_", "-")
                button_vars.append(f"    --{css_var_name}: {value};")

        # Convert fonts to CSS variables
        font_vars = []
        for font_key, font_value in FONTS.items():
            if isinstance(font_value, tuple):
                # Handle font tuples like ("Arial", 16, "bold")
                font_family = font_value[0]
                font_size = f"{font_value[1]}px"
                font_weight = font_value[2] if len(font_value) > 2 else "normal"

                css_var_name = font_key.replace("_", "-")
                font_vars.extend(
                    (
                        f'    --font-{css_var_name}-family: "{font_family}", sans-serif;',
                        f"    --font-{css_var_name}-size: {font_size*2};",
                    )
                )
                if font_weight != "normal":
                    font_vars.append(
                        f"    --font-{css_var_name}-weight: {font_weight};"
                    )

        # Read the base CSS template
        css_template_path = Path("static/css/style.css")
        if css_template_path.exists():
            with open(css_template_path, "r", encoding="utf-8") as f:
                base_css = f.read()
        else:
            # Fallback basic CSS structure
            base_css = """
/* Docker Tools Web Interface Styles - Dynamic Version */

/* Root Variables (dynamically generated from config/settings.py) */
:root {
    /* Colors will be inserted here */
    /* Button styles will be inserted here */
    /* Fonts will be inserted here */
}

/* Base styles and the rest of the CSS will be loaded from static file or defined here */
"""

        # Replace the :root section with dynamic variables
        root_section_start = base_css.find(":root {")
        root_section_end = base_css.find("}", root_section_start)

        dynamic_root = ":root {\n" + "    /* Colors from settings.py */\n"
        dynamic_root += "\n".join(color_vars) + "\n\n"
        dynamic_root += "    /* Button styles from settings.py */\n"
        dynamic_root += "\n".join(button_vars) + "\n\n"
        dynamic_root += "    /* Fonts from settings.py */\n"
        dynamic_root += "\n".join(font_vars) + "\n"
        if root_section_start != -1 and root_section_end != -1:
            dynamic_root += "}"

            # Replace the existing :root section
            return (
                base_css[:root_section_start]
                + dynamic_root
                + base_css[root_section_end + 1 :]
            )
        else:
            dynamic_root += "}\n\n"

            return dynamic_root + base_css

    def setup_flask_app(self):
        """Set up Flask application with routes"""
        self.app = Flask(
            __name__, template_folder=template_dir, static_folder=static_dir
        )
        self.app.secret_key = os.environ.get(
            "SECRET_KEY", "dev-secret-key-change-in-production"
        )

        # Set up routes
        self._setup_routes()

        return self.app

    def _setup_routes(self):
        """Set up all Flask routes"""

        @self.app.route("/")
        def index():
            """Main dashboard page"""
            project_groups = self.control_panel.project_group_service.get_group_names()
            current_group = self.control_panel.project_group_service.get_current_group()
            selected_group_name = request.args.get(
                "group", project_groups[0] if project_groups else None
            )

            if selected_group_name and selected_group_name in project_groups:
                self.control_panel.project_group_service.set_current_group_by_name(
                    selected_group_name
                )
                current_group = (
                    self.control_panel.project_group_service.get_current_group()
                )

            # Import colors and button styles from config
            from config.settings import COLORS, BUTTON_STYLES

            # Create project data with alias information for template
            enhanced_projects = []
            if current_group:
                for project in current_group.get_all_versions():
                    # Create a dict with project data and alias
                    project_data = {
                        "name": project.name,
                        "parent": project.parent,
                        "path": project.path,
                        "relative_path": project.relative_path,
                        "alias": self.control_panel.project_service.get_folder_alias(
                            project.parent
                        ),
                    }
                    enhanced_projects.append(project_data)

            return render_template(
                "index.html",
                project_groups=project_groups,
                current_group=current_group,
                enhanced_projects=enhanced_projects,
                selected_group_name=selected_group_name,
                colors=COLORS,
                button_styles=BUTTON_STYLES,
            )

        @self.app.route("/dynamic-style.css")
        def dynamic_css():
            """Serve dynamically generated CSS based on settings.py"""
            try:
                css_content = self._generate_dynamic_css()
                response = Response(css_content, mimetype="text/css")
                # Add cache control headers
                response.headers["Cache-Control"] = (
                    "no-cache, no-store, must-revalidate"
                )
                response.headers["Pragma"] = "no-cache"
                response.headers["Expires"] = "0"
                return response
            except Exception as e:
                logger.error(f"Error generating dynamic CSS: {e}")
                # Return empty CSS on error to prevent breaking the page
                return Response(
                    "/* Error generating dynamic CSS */", mimetype="text/css"
                )

        @self.app.route("/api/project-groups")
        def api_project_groups():
            """API endpoint to get project groups"""
            try:
                groups = self.control_panel.project_group_service.get_group_names()
                return jsonify({"success": True, "groups": groups})
            except Exception as e:
                logger.error(f"Error getting project groups: {e}")
                return jsonify({"success": False, "message": str(e)})

        @self.app.route("/api/project-group/<group_name>")
        def api_project_group(group_name):
            """API endpoint to get specific project group"""
            try:
                self.control_panel.project_group_service.set_current_group_by_name(
                    group_name
                )
                group = self.control_panel.project_group_service.get_current_group()
                if group:
                    projects_data = []
                    for project in group.get_all_versions():
                        alias = self.control_panel.project_service.get_folder_alias(
                            project.parent
                        )
                        projects_data.append(
                            {
                                "name": project.name,
                                "parent": project.parent,
                                "alias": alias,
                                "path": str(project.path),
                                "relative_path": project.relative_path,
                            }
                        )
                    return jsonify(
                        {
                            "success": True,
                            "group": {"name": group.name, "projects": projects_data},
                        }
                    )
                return jsonify({"success": False, "message": "Project group not found"})
            except Exception as e:
                logger.error(f"Error getting project group {group_name}: {e}")
                return jsonify({"success": False, "message": str(e)})

        @self.app.route("/api/current-selection")
        def api_current_selection():
            """API endpoint to get current selection status"""
            try:
                current_group = (
                    self.control_panel.project_group_service.get_current_group()
                )
                system_status = (
                    self.control_panel.project_group_service.get_system_status()
                )

                return jsonify(
                    {
                        "success": True,
                        "current_group": current_group.name if current_group else None,
                        "system_status": system_status,
                        "last_desktop_selection": self.last_desktop_selection,
                    }
                )
            except Exception as e:
                logger.error(f"Error getting current selection: {e}")
                return jsonify({"success": False, "message": str(e)})

        @self.app.route("/api/sync-status")
        def api_sync_status():
            """API endpoint to check if web interface is in sync with desktop"""
            try:
                current_group_name = (
                    self.control_panel.project_group_service.get_current_group_name()
                )
                return jsonify(
                    {
                        "success": True,
                        "current_selection": current_group_name,
                        "last_desktop_change": self.last_desktop_selection,
                        "is_synced": current_group_name == self.last_desktop_selection
                        or self.last_desktop_selection is None,
                    }
                )
            except Exception as e:
                logger.error(f"Error checking sync status: {e}")
                return jsonify({"success": False, "message": str(e)})

        @self.app.route("/api/settings/colors")
        def api_get_colors():
            """API endpoint to get current color settings"""
            try:
                from config.settings import COLORS

                return jsonify({"success": True, "colors": COLORS})
            except Exception as e:
                logger.error(f"Error getting colors: {e}")
                return jsonify({"success": False, "message": str(e)})

        @self.app.route("/api/settings/reload-css")
        def api_reload_css():
            """API endpoint to trigger CSS reload (for development/testing)"""
            try:
                # This endpoint can be called to force CSS regeneration
                return jsonify(
                    {
                        "success": True,
                        "message": "CSS will be regenerated on next request",
                        "css_url": "/dynamic-style.css",
                    }
                )
            except Exception as e:
                logger.error(f"Error in CSS reload: {e}")
                return jsonify({"success": False, "message": str(e)})

        @self.app.route("/api/action/cleanup", methods=["POST"])
        def api_cleanup_project():
            """API endpoint for cleanup project action - calls the same method as GUI"""
            try:
                data = request.get_json()
                project_name = data.get("project_name")
                parent_folder = data.get("parent_folder")

                if not project_name or not parent_folder:
                    return jsonify(
                        {
                            "success": False,
                            "message": "Missing project name or parent folder",
                        }
                    )

                # Create project object
                project_path = (
                    Path(self.control_panel.root_dir) / parent_folder / project_name
                )
                if not project_path.exists():
                    return jsonify({"success": False, "message": "Project not found"})

                project = Project(
                    parent=parent_folder,
                    name=project_name,
                    path=project_path,
                    relative_path=f"{parent_folder}/{project_name}",
                )

                # Call the SAME method that the GUI button calls
                self.control_panel.cleanup_project(project)

                return jsonify(
                    {
                        "success": True,
                        "message": "Cleanup operation initiated successfully",
                    }
                )

            except Exception as e:
                logger.error(f"Error in cleanup project: {e}")
                return jsonify({"success": False, "message": str(e)})

        @self.app.route("/api/action/archive", methods=["POST"])
        def api_archive_project():
            """API endpoint for archive project action - calls the same method as GUI"""
            try:
                data = request.get_json()
                project_name = data.get("project_name")
                parent_folder = data.get("parent_folder")

                if not project_name or not parent_folder:
                    return jsonify(
                        {
                            "success": False,
                            "message": "Missing project name or parent folder",
                        }
                    )

                # Create project object
                project_path = (
                    Path(self.control_panel.root_dir) / parent_folder / project_name
                )
                if not project_path.exists():
                    return jsonify({"success": False, "message": "Project not found"})

                project = Project(
                    parent=parent_folder,
                    name=project_name,
                    path=project_path,
                    relative_path=f"{parent_folder}/{project_name}",
                )

                # Call the SAME method that the GUI button calls
                self.control_panel.archive_project(project)

                return jsonify(
                    {
                        "success": True,
                        "message": "Archive operation initiated successfully",
                    }
                )

            except Exception as e:
                logger.error(f"Error in archive project: {e}")
                return jsonify({"success": False, "message": str(e)})

        @self.app.route("/api/action/docker", methods=["POST"])
        def api_docker_build_test():
            """API endpoint for docker build and test action - calls the same method as GUI"""
            try:
                data = request.get_json()
                project_name = data.get("project_name")
                parent_folder = data.get("parent_folder")

                if not project_name or not parent_folder:
                    return jsonify(
                        {
                            "success": False,
                            "message": "Missing project name or parent folder",
                        }
                    )

                # Create project object
                project_path = (
                    Path(self.control_panel.root_dir) / parent_folder / project_name
                )
                if not project_path.exists():
                    return jsonify({"success": False, "message": "Project not found"})

                project = Project(
                    parent=parent_folder,
                    name=project_name,
                    path=project_path,
                    relative_path=f"{parent_folder}/{project_name}",
                )

                # Call the SAME method that the GUI button calls
                self.control_panel.docker_build_and_test(project)

                return jsonify(
                    {
                        "success": True,
                        "message": "Docker build and test operation initiated successfully",
                    }
                )

            except Exception as e:
                logger.error(f"Error in docker build and test: {e}")
                return jsonify({"success": False, "message": str(e)})

        @self.app.route("/api/action/git-view", methods=["POST"])
        def api_git_view():
            """API endpoint for git view action - calls the same method as GUI"""
            try:
                data = request.get_json()
                project_name = data.get("project_name")
                parent_folder = data.get("parent_folder")

                if not project_name or not parent_folder:
                    return jsonify(
                        {
                            "success": False,
                            "message": "Missing project name or parent folder",
                        }
                    )

                # Create project object
                project_path = (
                    Path(self.control_panel.root_dir) / parent_folder / project_name
                )
                if not project_path.exists():
                    return jsonify({"success": False, "message": "Project not found"})

                project = Project(
                    parent=parent_folder,
                    name=project_name,
                    path=project_path,
                    relative_path=f"{parent_folder}/{project_name}",
                )

                # Call the SAME method that the GUI button calls
                self.control_panel.git_view(project)

                return jsonify(
                    {
                        "success": True,
                        "message": "Git view operation initiated successfully",
                    }
                )

            except Exception as e:
                logger.error(f"Error in git view: {e}")
                return jsonify({"success": False, "message": str(e)})

        @self.app.route("/api/action/sync-run-tests", methods=["POST"])
        def api_sync_run_tests():
            """API endpoint for sync run tests action - calls the same method as GUI"""
            try:
                data = request.get_json()
                group_name = data.get("group_name")

                if not group_name:
                    return jsonify({"success": False, "message": "Missing group name"})

                self.control_panel.project_group_service.set_current_group_by_name(
                    group_name
                )
                group = self.control_panel.project_group_service.get_current_group()
                if not group:
                    return jsonify(
                        {"success": False, "message": "Project group not found"}
                    )

                # Call the SAME method that the GUI button calls
                self.control_panel.sync_run_tests_from_pre_edit(group)

                return jsonify(
                    {
                        "success": True,
                        "message": "Sync run tests operation initiated successfully",
                    }
                )

            except Exception as e:
                logger.error(f"Error in sync run tests: {e}")
                return jsonify({"success": False, "message": str(e)})

        @self.app.route("/api/action/validate-project-group", methods=["POST"])
        def api_validate_project_group():
            """API endpoint for validate project group action - calls the same method as GUI"""
            try:
                data = request.get_json()
                group_name = data.get("group_name")

                if not group_name:
                    return jsonify({"success": False, "message": "Missing group name"})

                self.control_panel.project_group_service.set_current_group_by_name(
                    group_name
                )
                group = self.control_panel.project_group_service.get_current_group()
                if not group:
                    return jsonify(
                        {"success": False, "message": "Project group not found"}
                    )

                # Call the SAME method that the GUI button calls
                self.control_panel.validate_project_group(group)

                return jsonify(
                    {
                        "success": True,
                        "message": "Validate project group operation initiated successfully",
                    }
                )

            except Exception as e:
                logger.error(f"Error in validate project group: {e}")
                return jsonify({"success": False, "message": str(e)})

        @self.app.route("/api/action/build-docker-files", methods=["POST"])
        def api_build_docker_files():
            """API endpoint for build docker files action - calls the same method as GUI"""
            try:
                data = request.get_json()
                group_name = data.get("group_name")

                if not group_name:
                    return jsonify({"success": False, "message": "Missing group name"})

                self.control_panel.project_group_service.set_current_group_by_name(
                    group_name
                )
                group = self.control_panel.project_group_service.get_current_group()
                if not group:
                    return jsonify(
                        {"success": False, "message": "Project group not found"}
                    )

                # Call the SAME method that the GUI button calls
                self.control_panel.build_docker_files_for_project_group(group)

                return jsonify(
                    {
                        "success": True,
                        "message": "Build docker files operation initiated successfully",
                    }
                )

            except Exception as e:
                logger.error(f"Error in build docker files: {e}")
                return jsonify({"success": False, "message": str(e)})

        @self.app.route("/api/action/git-checkout-all", methods=["POST"])
        def api_git_checkout_all():
            """API endpoint for git checkout all action - calls the same method as GUI"""
            try:
                data = request.get_json()
                group_name = data.get("group_name")

                if not group_name:
                    return jsonify({"success": False, "message": "Missing group name"})

                self.control_panel.project_group_service.set_current_group_by_name(
                    group_name
                )
                group = self.control_panel.project_group_service.get_current_group()
                if not group:
                    return jsonify(
                        {"success": False, "message": "Project group not found"}
                    )

                # Call the SAME method that the GUI button calls
                self.control_panel.git_checkout_all(group)

                return jsonify(
                    {
                        "success": True,
                        "message": "Git checkout all operation initiated successfully",
                    }
                )

            except Exception as e:
                logger.error(f"Error in git checkout all: {e}")
                return jsonify({"success": False, "message": str(e)})

        @self.app.route("/api/refresh")
        def api_refresh():
            """API endpoint to refresh projects - calls the same method as GUI"""
            try:
                # Call the SAME method that the GUI refresh button calls
                self.control_panel.refresh_projects()
                return jsonify(
                    {"success": True, "message": "Projects refreshed successfully"}
                )
            except Exception as e:
                logger.error(f"Error refreshing projects: {e}")
                return jsonify({"success": False, "message": str(e)})

        @self.app.route("/api/select-project", methods=["POST"])
        def api_select_project():
            """API endpoint for project selection - calls the same method as GUI dropdown"""
            try:
                data = request.get_json()
                group_name = data.get("group_name")

                if not group_name:
                    return jsonify({"success": False, "message": "Missing group name"})

                # Call the SAME method that the GUI dropdown calls
                success = (
                    self.control_panel.project_group_service.set_current_group_by_name(
                        group_name
                    )
                )

                if success:
                    # Get the updated current group
                    current_group = (
                        self.control_panel.project_group_service.get_current_group()
                    )

                    if current_group:
                        # Prepare project data for response
                        projects_data = []
                        for project in current_group.get_all_versions():
                            alias = self.control_panel.project_service.get_folder_alias(
                                project.parent
                            )
                            projects_data.append(
                                {
                                    "name": project.name,
                                    "parent": project.parent,
                                    "alias": alias,
                                    "path": str(project.path),
                                    "relative_path": project.relative_path,
                                }
                            )

                        group_data = {
                            "name": current_group.name,
                            "projects": projects_data,
                        }

                        return jsonify(
                            {
                                "success": True,
                                "message": f"Selected project group: {group_name}",
                                "group": group_data,
                            }
                        )
                    else:
                        return jsonify(
                            {"success": False, "message": "Project group not found"}
                        )
                else:
                    return jsonify(
                        {"success": False, "message": "Failed to select project group"}
                    )

            except Exception as e:
                logger.error(f"Error selecting project: {e}")
                return jsonify({"success": False, "message": str(e)})

        @self.app.route("/api/action/settings", methods=["POST"])
        def api_settings():
            """API endpoint for settings - calls the same method as GUI"""
            try:
                # Call the SAME method that the GUI settings button calls
                self.control_panel.open_settings_window()

                return jsonify(
                    {
                        "success": True,
                        "message": "Settings functionality is handled by the desktop application. Please use the desktop GUI to modify settings.",
                    }
                )
            except Exception as e:
                logger.error(f"Error in settings: {e}")
                return jsonify({"success": False, "message": str(e)})

        @self.app.route("/api/action/add-project", methods=["POST"])
        def api_add_project():
            """API endpoint for add project - calls the same method as GUI"""
            try:
                data = request.get_json()
                repo_url = data.get("repo_url")
                project_name = data.get("project_name")

                if not repo_url or not project_name:
                    return jsonify(
                        {
                            "success": False,
                            "message": "Missing repo_url or project_name",
                        }
                    )

                # Call the SAME method that the GUI add project calls
                self.control_panel.add_project(repo_url, project_name)

                return jsonify(
                    {
                        "success": True,
                        "message": f"Add project operation initiated successfully for {project_name}",
                    }
                )

            except Exception as e:
                logger.error(f"Error in add project: {e}")
                return jsonify({"success": False, "message": str(e)})

        @self.app.route("/api/action/edit-run-tests", methods=["POST"])
        def api_edit_run_tests():
            """API endpoint to edit run_tests.sh for a project group"""
            try:
                data = request.get_json()
                group_name = data.get("group_name")

                if not group_name:
                    return jsonify(
                        {"success": False, "message": "Group name is required"}
                    )

                # Set the current group
                self.control_panel.project_group_service.set_current_group_by_name(
                    group_name
                )
                group = self.control_panel.project_group_service.get_current_group()

                if not group:
                    return jsonify(
                        {
                            "success": False,
                            "message": f"Project group '{group_name}' not found",
                        }
                    )

                # Call the edit run tests method directly
                self.control_panel.edit_run_tests(group)

                return jsonify(
                    {
                        "success": True,
                        "message": "Edit run_tests.sh window opened in desktop application",
                    }
                )

            except Exception as e:
                logger.error(f"Error in edit run tests API: {e}")
                return jsonify({"success": False, "message": str(e)})

        @self.app.route("/terminal")
        def terminal_view():
            """Terminal view page"""
            project_groups = self.control_panel.project_group_service.get_group_names()
            current_group = self.control_panel.project_group_service.get_current_group()
            selected_group_name = request.args.get(
                "group", project_groups[0] if project_groups else None
            )

            if selected_group_name and selected_group_name in project_groups:
                self.control_panel.project_group_service.set_current_group_by_name(
                    selected_group_name
                )
                current_group = (
                    self.control_panel.project_group_service.get_current_group()
                )

            return render_template(
                "terminal.html",
                project_groups=project_groups,
                current_group=current_group,
                selected_group_name=selected_group_name,
            )

        @self.app.route("/api/terminal/output")
        def api_terminal_output():
            """API endpoint to get current terminal output"""
            try:
                from models.web_terminal_buffer import web_terminal_buffer

                output = web_terminal_buffer.get()
                return jsonify(
                    {"success": True, "output": output, "timestamp": time.time()}
                )
            except Exception as e:
                logger.error(f"Error getting terminal output: {e}")
                return jsonify({"success": False, "message": str(e)})

        @self.app.route("/api/terminal/clear", methods=["POST"])
        def api_clear_terminal():
            """API endpoint to clear terminal output"""
            try:
                from models.web_terminal_buffer import web_terminal_buffer

                web_terminal_buffer.clear()
                return jsonify({"success": True, "message": "Terminal cleared"})
            except Exception as e:
                logger.error(f"Error clearing terminal: {e}")
                return jsonify({"success": False, "message": str(e)})

    def start_web_server(self, host="0.0.0.0", port=5000, debug=False):
        """Start the web server in a separate thread"""
        if self.is_running:
            return

        self.setup_flask_app()
        self.is_running = True

        def run_server():
            try:
                self.app.run(host=host, port=port, debug=debug, use_reloader=False)
            except Exception as e:
                logger.error(f"Web server error: {e}")
            finally:
                self.is_running = False

        self.web_thread = threading.Thread(target=run_server, daemon=True)
        self.web_thread.start()

    def stop_web_server(self):
        """Stop the web server"""
        if self.is_running:
            self.is_running = False
            logger.info("Web server stopped")

    def get_web_url(self) -> str:
        """Get the web interface URL"""
        return "http://localhost:5000"

    def is_web_server_running(self) -> bool:
        """Check if web server is running"""
        return self.is_running
