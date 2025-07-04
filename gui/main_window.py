"""
Main Window GUI Components for Project Control Panel
"""

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional, Callable, Dict, Any, List
from pathlib import Path

from config.settings import WINDOW_TITLE, MAIN_WINDOW_SIZE, COLORS, FONTS
from gui.gui_utils import GuiUtils
from gui.popup_windows import AddProjectWindow
from services.project_group_service import ProjectGroup
from models.project import Project


class MainWindow:
    """Main window GUI components and layout management"""

    def __init__(self, root_dir: str = "."):
        self.root_dir = Path(root_dir).resolve()

        # Initialize main window
        self.window = tk.Tk()
        self.window.title(WINDOW_TITLE)
        self.window.geometry(MAIN_WINDOW_SIZE)
        self.window.configure(bg=COLORS["background"])

        # GUI components
        self.scrollable_frame = None
        self.project_selector = None
        self.navigation_frame = None

        # Callbacks for main window operations
        self.on_project_selected_callback = None
        self.refresh_projects_callback = None
        self.open_add_project_window_callback = None
        self.cleanup_project_callback = None
        self.archive_project_callback = None
        self.docker_build_callback = None
        self.git_view_callback = None
        self.sync_run_tests_callback = None
        self.edit_run_tests_callback = None
        self.validate_project_group_callback = None
        self.build_docker_files_callback = None
        self.git_checkout_all_callback = None

    def set_callbacks(self, callbacks: Dict[str, Callable]):
        """Set callback functions for GUI events"""
        self.on_project_selected_callback = callbacks.get("on_project_selected")
        self.refresh_projects_callback = callbacks.get("refresh_projects")
        self.open_add_project_window_callback = callbacks.get("open_add_project_window")

        self.cleanup_project_callback = callbacks.get("cleanup_project")
        self.archive_project_callback = callbacks.get("archive_project")
        self.docker_build_callback = callbacks.get("docker_build_and_test")
        self.git_view_callback = callbacks.get("git_view")

        self.sync_run_tests_callback = callbacks.get("sync_run_tests_from_pre_edit")
        self.edit_run_tests_callback = callbacks.get("edit_run_tests")
        self.validate_project_group_callback = callbacks.get("validate_project_group")
        self.build_docker_files_callback = callbacks.get(
            "build_docker_files_for_project_group"
        )
        self.git_checkout_all_callback = callbacks.get("git_checkout_all")

    def setup_window_protocol(self, on_close_callback: Callable):
        """Set up window close protocol"""
        self.window.protocol("WM_DELETE_WINDOW", on_close_callback)

    def create_gui(self):
        """Create the main GUI layout"""
        # Create navigation frame
        self._create_navigation_frame()

        # Create main frame with scrollbar
        main_frame = GuiUtils.create_styled_frame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create scrollable frame
        canvas, self.scrollable_frame, scrollbar = GuiUtils.create_scrollable_frame(
            main_frame
        )

    def _create_navigation_frame(self):
        """Create the navigation frame with project selector and navigation buttons"""
        self.navigation_frame = GuiUtils.create_styled_frame(self.window)
        self.navigation_frame.pack(fill="x", padx=10, pady=(0, 10))

        # Project selection row
        selection_frame = GuiUtils.create_styled_frame(self.navigation_frame)
        selection_frame.pack(fill="x", pady=5)

        # Project selector label
        selector_label = GuiUtils.create_styled_label(
            selection_frame, text="Project:", font_key="project_name"
        )
        selector_label.pack(side="left", padx=(0, 10))

        # Project selector dropdown
        self.project_selector = ttk.Combobox(
            selection_frame, state="readonly", font=FONTS["project_name"], width=30
        )
        self.project_selector.pack(side="left", padx=(0, 10))
        self.project_selector.bind("<<ComboboxSelected>>", self._on_project_selected)

        # Refresh button
        refresh_btn = GuiUtils.create_styled_button(
            selection_frame,
            text="🔄 Refresh",
            command=self._refresh_projects,
            style="refresh",
        )
        refresh_btn.pack(side="right")

        # Add Project button
        add_project_btn = GuiUtils.create_styled_button(
            selection_frame,
            text="➕ Add Project",
            command=self._open_add_project_window,
            style="git",
        )
        add_project_btn.pack(side="right", padx=(0, 10))

    def _on_project_selected(self, event=None):
        """Handle project selection from dropdown"""
        if self.on_project_selected_callback:
            self.on_project_selected_callback(event)

    def _refresh_projects(self):
        """Handle refresh projects button click"""
        if self.refresh_projects_callback:
            self.refresh_projects_callback()

    def _open_add_project_window(self):
        """Handle add project button click"""
        if self.open_add_project_window_callback:
            self.open_add_project_window_callback()

    def update_project_selector(
        self, group_names: List[str], current_group_name: Optional[str] = None
    ):
        """Update the project selector dropdown with available projects"""
        # Update combobox values
        self.project_selector["values"] = group_names

        if current_group_name:
            self.project_selector.set(current_group_name)
        elif group_names:
            self.project_selector.set(group_names[0])

    def get_selected_project(self) -> Optional[str]:
        """Get the currently selected project name"""
        return self.project_selector.get() if self.project_selector else None

    def clear_content(self):
        """Clear the scrollable content area"""
        if self.scrollable_frame:
            for widget in self.scrollable_frame.winfo_children():
                widget.destroy()

    def show_no_projects_message(self):
        """Show message when no projects are found"""
        no_projects_label = GuiUtils.create_styled_label(
            self.scrollable_frame,
            text=f"No projects found in:\n{self.root_dir}",
            font_key="project_name",
        )
        no_projects_label.pack(pady=20)

    def show_no_versions_message(self):
        """Show message when no versions are found for a project"""
        no_versions_label = GuiUtils.create_styled_label(
            self.scrollable_frame,
            text="No versions found for this project",
            font_key="project_name",
        )
        no_versions_label.pack(pady=20)

    def create_project_header(self, project_group: ProjectGroup):
        """Create a header for the current project group"""
        header_frame = GuiUtils.create_styled_frame(
            self.scrollable_frame, bg_color="white", relief="raised", bd=2
        )
        header_frame.pack(fill="x", padx=20, pady=(10, 0))

        # Project name
        name_label = GuiUtils.create_styled_label(
            header_frame,
            text=f"📁 Project: {project_group.name}",
            font_key="title",
            color_key="project_header",
            bg=COLORS["white"],
        )
        name_label.pack(pady=15)

    def create_project_actions_frame(self, project_group: ProjectGroup):
        """Create a frame for project-level action buttons"""
        actions_frame = GuiUtils.create_styled_frame(
            self.scrollable_frame, bg_color="background", relief="flat"
        )
        actions_frame.pack(fill="x", padx=20, pady=(0, 10))

        # Buttons container
        buttons_container = GuiUtils.create_styled_frame(
            actions_frame,
            bg_color="background",
        )
        buttons_container.pack(fill="x")

        # Sync button
        sync_btn = GuiUtils.create_styled_button(
            buttons_container,
            text="🔄 Sync run_tests.sh",
            command=lambda: self._sync_run_tests(project_group),
            style="sync",
        )
        sync_btn.pack(side="left", padx=(0, 10))

        # Edit run_tests.sh button
        edit_run_tests_btn = GuiUtils.create_styled_button(
            buttons_container,
            text="✏️ Edit run_tests.sh",
            command=lambda: self._edit_run_tests(project_group),
            style="edit",
        )
        edit_run_tests_btn.pack(side="left", padx=(0, 10))

        # Validation button
        validate_btn = GuiUtils.create_styled_button(
            buttons_container,
            text="🔍 Validate All",
            command=lambda: self._validate_project_group(project_group),
            style="validate",
        )
        validate_btn.pack(side="left", padx=(0, 10))

        # Build Docker files button
        build_docker_btn = GuiUtils.create_styled_button(
            buttons_container,
            text="🐳 Build Docker files",
            command=lambda: self._build_docker_files(project_group),
            style="build_docker",
        )
        build_docker_btn.pack(side="left", padx=(0, 10))

        # Git Checkout All button
        git_checkout_all_btn = GuiUtils.create_styled_button(
            buttons_container,
            text="🔀 Git Checkout All",
            command=lambda: self._git_checkout_all(project_group),
            style="git",
        )
        git_checkout_all_btn.pack(side="left", padx=(0, 10))

    def _sync_run_tests(self, project_group: ProjectGroup):
        """Handle sync run tests button click"""
        if self.sync_run_tests_callback:
            self.sync_run_tests_callback(project_group)

    def _edit_run_tests(self, project_group: ProjectGroup):
        """Handle edit run tests button click"""
        if self.edit_run_tests_callback:
            self.edit_run_tests_callback(project_group)

    def _validate_project_group(self, project_group: ProjectGroup):
        """Handle validate project group button click"""
        if self.validate_project_group_callback:
            self.validate_project_group_callback(project_group)

    def _build_docker_files(self, project_group: ProjectGroup):
        """Handle build docker files button click"""
        if self.build_docker_files_callback:
            self.build_docker_files_callback(project_group)

    def _git_checkout_all(self, project_group: ProjectGroup):
        """Handle git checkout all button click"""
        if self.git_checkout_all_callback:
            self.git_checkout_all_callback(project_group)

    def create_version_section(self, project: Project, project_service):
        """Create a version section for a project"""
        # Get alias for better display
        alias = project_service.get_folder_alias(project.parent)

        # Version header
        version_header_frame = GuiUtils.create_styled_frame(self.scrollable_frame)
        version_header_frame.pack(anchor="w", padx=30, pady=(10, 5))

        # Main version name
        version_label = GuiUtils.create_styled_label(
            version_header_frame,
            text=f"📂 {project.parent}",
            font_key="header",
            color_key="project_header",
        )
        version_label.pack(side="left")

        # Alias in faded text if it exists
        if alias:
            alias_label = GuiUtils.create_styled_label(
                version_header_frame,
                text=f" ({alias})",
                font_key="info",
                color_key="muted",
            )
            alias_label.pack(side="left")

        # Project row
        self.create_project_row(project)

    def create_project_row(self, project: Project):
        """Create a project row with buttons"""
        # Create project frame
        project_frame = GuiUtils.create_styled_frame(
            self.scrollable_frame, bg_color="white", relief="raised", bd=1
        )
        project_frame.pack(fill="x", padx=40, pady=2)

        # Project info
        info_frame = GuiUtils.create_styled_frame(project_frame, bg_color="white")
        info_frame.pack(side="left", fill="x", expand=True, padx=10, pady=8)

        name_label = GuiUtils.create_styled_label(
            info_frame, text=project.name, font_key="project_name", bg=COLORS["white"]
        )
        name_label.pack(anchor="w")

        path_label = GuiUtils.create_styled_label(
            info_frame,
            text=f"Path: {project.relative_path}",
            font_key="info",
            color_key="muted",
            bg=COLORS["white"],
        )
        path_label.pack(anchor="w")

        # Buttons frame
        buttons_frame = GuiUtils.create_styled_frame(project_frame, bg_color="white")
        buttons_frame.pack(side="right", padx=10, pady=8)

        # Create buttons
        self.create_project_buttons(buttons_frame, project)

    def create_project_buttons(self, parent, project: Project):
        """Create the action buttons for a project"""
        # Cleanup button
        cleanup_btn = GuiUtils.create_styled_button(
            parent,
            text="🧹 Cleanup",
            command=lambda: self._cleanup_project(project),
            style="cleanup",
        )
        cleanup_btn.pack(side="left", padx=(0, 5))

        # Archive button
        archive_btn = GuiUtils.create_styled_button(
            parent,
            text="📦 Archive",
            command=lambda: self._archive_project(project),
            style="archive",
        )
        archive_btn.pack(side="left", padx=(0, 5))

        # Docker button
        docker_btn = GuiUtils.create_styled_button(
            parent,
            text="🐳 Docker",
            command=lambda: self._docker_build(project),
            style="docker",
        )
        docker_btn.pack(side="left", padx=(0, 5))

        # Git View button
        git_btn = GuiUtils.create_styled_button(
            parent,
            text="🔀 Git View",
            command=lambda: self._git_view(project),
            style="git",
        )
        git_btn.pack(side="left")

    def _cleanup_project(self, project: Project):
        """Handle cleanup project button click"""
        if self.cleanup_project_callback:
            self.cleanup_project_callback(project)

    def _archive_project(self, project: Project):
        """Handle archive project button click"""
        if self.archive_project_callback:
            self.archive_project_callback(project)

    def _docker_build(self, project: Project):
        """Handle docker build button click"""
        if self.docker_build_callback:
            self.docker_build_callback(project)

    def _git_view(self, project: Project):
        """Handle git view button click"""
        if self.git_view_callback:
            self.git_view_callback(project)

    def add_version_spacing(self):
        """Add spacing between versions"""
        tk.Frame(self.scrollable_frame, height=10, bg=COLORS["background"]).pack()

    def schedule_task(self, task: Callable, delay: int = 0):
        """Schedule a task to run on the GUI thread"""
        self.window.after(delay, task)

    def run(self):
        """Start the GUI main loop"""
        self.window.mainloop()

    def destroy(self):
        """Destroy the main window"""
        self.window.destroy()
