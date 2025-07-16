"""
GUI Coordinator for Centralized GUI Synchronization and Management
Handles all GUI thread coordination, window management, and async bridge operations
"""

import asyncio
import logging
import tkinter as tk
from tkinter import messagebox
from typing import Dict, Any, Optional, Callable, List, Union
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
from enum import Enum
import uuid
import threading
import weakref

from config.config import get_config

COLORS = get_config().gui.colors


class WindowType(Enum):
    """Types of windows for lifecycle management"""

    TERMINAL = "terminal"
    GIT = "git"
    MODAL = "modal"
    POPUP = "popup"


@dataclass
class WindowInfo:
    """Information about a managed window"""

    window_id: str
    window_type: WindowType
    window_ref: weakref.ref
    title: str
    parent_window: Optional[tk.Tk] = None
    creation_time: float = field(
        default_factory=lambda: asyncio.get_event_loop().time()
    )
    callbacks: Dict[str, Callable] = field(default_factory=dict)


@dataclass
class GUITask:
    """Represents a GUI task to be executed on the main thread"""

    task_id: str
    function: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    callback: Optional[Callable] = None
    priority: int = 0  # Higher priority tasks execute first


class GUICoordinator:
    """Centralized GUI coordination and synchronization system"""

    def __init__(self, main_window: tk.Tk, async_bridge=None):
        self.main_window = main_window
        self.async_bridge = async_bridge
        self.logger = logging.getLogger("GUICoordinator")

        # Window management
        self._managed_windows: Dict[str, WindowInfo] = {}
        self._window_creation_callbacks: Dict[WindowType, List[Callable]] = {}
        self._window_destruction_callbacks: Dict[WindowType, List[Callable]] = {}

        # Task management
        self._pending_tasks: List[GUITask] = []
        self._task_processing_active = False

        # Synchronization
        self._sync_events: Dict[str, asyncio.Event] = {}
        self._sync_callbacks: Dict[str, Callable] = {}

        # Thread safety
        self._lock = threading.Lock()

        # Status management
        self._status_widgets: List[weakref.ref] = []

        # Start task processing
        self._start_task_processing()

    def _start_task_processing(self):
        """Start the GUI task processing loop"""
        if not self._task_processing_active:
            self._task_processing_active = True
            self._process_pending_tasks()

    def _process_pending_tasks(self):
        """Process pending GUI tasks on the main thread"""
        if not self._task_processing_active:
            return

        with self._lock:
            if self._pending_tasks:
                # Sort by priority (highest first)
                self._pending_tasks.sort(key=lambda t: t.priority, reverse=True)
                task = self._pending_tasks.pop(0)
            else:
                task = None

        if task:
            try:
                result = task.function(*task.args, **task.kwargs)
                if task.callback:
                    task.callback(result)
            except Exception as e:
                self.logger.error(f"Error executing GUI task {task.task_id}: {e}")

        # Schedule next task processing
        if self._task_processing_active:
            self.main_window.after(10, self._process_pending_tasks)

    def schedule_task(
        self,
        function: Callable,
        *args,
        priority: int = 0,
        callback: Optional[Callable] = None,
        delay: int = 0,
        **kwargs,
    ) -> str:
        """Schedule a task to run on the GUI thread"""
        task_id = str(uuid.uuid4())
        task = GUITask(
            task_id=task_id,
            function=function,
            args=args,
            kwargs=kwargs,
            callback=callback,
            priority=priority,
        )

        with self._lock:
            self._pending_tasks.append(task)

        if delay > 0:
            self.main_window.after(delay, lambda: None)  # Just to trigger processing

        return task_id

    def schedule_immediate(self, function: Callable, *args, **kwargs):
        """Execute a function immediately on the GUI thread"""
        self.main_window.after(0, lambda: function(*args, **kwargs))

    def schedule_delayed(self, delay: int, function: Callable, *args, **kwargs):
        """Execute a function after a delay on the GUI thread"""
        self.main_window.after(delay, lambda: function(*args, **kwargs))

    async def create_window_async(
        self,
        window_type: WindowType,
        window_factory: Callable,
        title: str,
        *args,
        **kwargs,
    ) -> str:
        """Create a window asynchronously with proper coordination"""
        window_id = str(uuid.uuid4())

        # Create synchronization event if async bridge is available
        if self.async_bridge:
            event_id, window_ready_event = self.async_bridge.create_sync_event()
        else:
            event_id = None
            window_ready_event = None

        # Window creation function
        def create_window():
            try:
                window = window_factory(*args, **kwargs)

                # Register the window
                window_info = WindowInfo(
                    window_id=window_id,
                    window_type=window_type,
                    window_ref=weakref.ref(window),
                    title=title,
                    parent_window=self.main_window,
                )
                self._managed_windows[window_id] = window_info

                # Set up destruction callback
                if hasattr(window, "protocol"):
                    original_destroy = getattr(window, "destroy", None)

                    def on_destroy():
                        self._unregister_window(window_id)
                        if original_destroy:
                            original_destroy()

                    window.protocol("WM_DELETE_WINDOW", on_destroy)

                # Notify callbacks
                self._notify_window_created(window_type, window)

                # Signal completion if event exists
                if event_id and self.async_bridge:
                    self.async_bridge.signal_from_gui(event_id)

                return window

            except Exception as e:
                self.logger.error(f"Error creating window {title}: {e}")
                if event_id and self.async_bridge:
                    self.async_bridge.signal_from_gui(event_id)
                return None

        # Schedule window creation
        self.schedule_immediate(create_window)

        # Wait for completion if async bridge is available
        if window_ready_event:
            await window_ready_event.wait()
            if self.async_bridge:
                self.async_bridge.cleanup_event(event_id)
        else:
            # Small delay to allow window creation
            await asyncio.sleep(0.1)

        return window_id

    def register_existing_window(
        self, window, window_type: WindowType, title: str
    ) -> str:
        """Register an existing window for management"""
        window_id = str(uuid.uuid4())

        window_info = WindowInfo(
            window_id=window_id,
            window_type=window_type,
            window_ref=weakref.ref(window),
            title=title,
            parent_window=self.main_window,
        )
        self._managed_windows[window_id] = window_info

        # Set up destruction callback
        if hasattr(window, "protocol"):
            original_destroy = getattr(window, "destroy", None)

            def on_destroy():
                self._unregister_window(window_id)
                if original_destroy:
                    original_destroy()

            window.protocol("WM_DELETE_WINDOW", on_destroy)

        return window_id

    def _unregister_window(self, window_id: str):
        """Unregister a managed window"""
        if window_id in self._managed_windows:
            window_info = self._managed_windows[window_id]
            self._notify_window_destroyed(window_info.window_type, window_info)
            del self._managed_windows[window_id]

    def get_managed_windows(
        self, window_type: Optional[WindowType] = None
    ) -> List[WindowInfo]:
        """Get list of managed windows, optionally filtered by type"""
        windows = list(self._managed_windows.values())
        if window_type:
            windows = [w for w in windows if w.window_type == window_type]
        return windows

    def close_all_windows(self, window_type: Optional[WindowType] = None):
        """Close all managed windows of a specific type (or all if type is None)"""
        windows_to_close = []

        for window_info in self._managed_windows.values():
            if window_type is None or window_info.window_type == window_type:
                window = window_info.window_ref()
                if window:
                    windows_to_close.append(window)

        def close_windows():
            for window in windows_to_close:
                try:
                    window.destroy()
                except Exception as e:
                    self.logger.error(f"Error closing window: {e}")

        self.schedule_immediate(close_windows)

    def register_window_callback(
        self, window_type: WindowType, event: str, callback: Callable
    ):
        """Register callbacks for window lifecycle events"""
        if event == "created":
            if window_type not in self._window_creation_callbacks:
                self._window_creation_callbacks[window_type] = []
            self._window_creation_callbacks[window_type].append(callback)
        elif event == "destroyed":
            if window_type not in self._window_destruction_callbacks:
                self._window_destruction_callbacks[window_type] = []
            self._window_destruction_callbacks[window_type].append(callback)

    def _notify_window_created(self, window_type: WindowType, window):
        """Notify callbacks about window creation"""
        callbacks = self._window_creation_callbacks.get(window_type, [])
        for callback in callbacks:
            try:
                callback(window)
            except Exception as e:
                self.logger.error(f"Error in window creation callback: {e}")

    def _notify_window_destroyed(
        self, window_type: WindowType, window_info: WindowInfo
    ):
        """Notify callbacks about window destruction"""
        callbacks = self._window_destruction_callbacks.get(window_type, [])
        for callback in callbacks:
            try:
                callback(window_info)
            except Exception as e:
                self.logger.error(f"Error in window destruction callback: {e}")

    # Message Box Coordination
    def show_info(self, title: str, message: str, callback: Optional[Callable] = None):
        """Show info message box on GUI thread"""

        def show_message():
            result = messagebox.showinfo(title, message)
            if callback:
                callback(result)

        self.schedule_immediate(show_message)

    def show_error(self, title: str, message: str, callback: Optional[Callable] = None):
        """Show error message box on GUI thread"""

        def show_message():
            result = messagebox.showerror(title, message)
            if callback:
                callback(result)

        self.schedule_immediate(show_message)

    def show_warning(
        self, title: str, message: str, callback: Optional[Callable] = None
    ):
        """Show warning message box on GUI thread"""

        def show_message():
            result = messagebox.showwarning(title, message)
            if callback:
                callback(result)

        self.schedule_immediate(show_message)

    def show_question(
        self, title: str, message: str, callback: Optional[Callable] = None
    ):
        """Show yes/no question dialog on GUI thread"""

        def show_message():
            result = messagebox.askyesno(title, message)
            if callback:
                callback(result)

        self.schedule_immediate(show_message)

    # Status Management
    def register_status_widget(self, widget):
        """Register a status widget for updates"""
        self._status_widgets.append(weakref.ref(widget))

    def update_status(self, message: str, color: str = None):
        """Update all registered status widgets"""

        def update_all_status():
            # Clean up dead references
            self._status_widgets[:] = [
                ref for ref in self._status_widgets if ref() is not None
            ]

            # Update active widgets
            for widget_ref in self._status_widgets:
                widget = widget_ref()
                if widget:
                    try:
                        if hasattr(widget, "config"):
                            widget.config(text=message)
                            if color and hasattr(widget, "configure"):
                                widget.configure(fg=color)
                        elif hasattr(widget, "set"):
                            widget.set(message)
                    except Exception as e:
                        self.logger.error(f"Error updating status widget: {e}")

        self.schedule_immediate(update_all_status)

    # Async Bridge Integration
    async def create_sync_event(self) -> tuple:
        """Create a synchronization event for async operations"""
        if self.async_bridge:
            return self.async_bridge.create_sync_event()
        # Fallback for when no async bridge is available
        event_id = str(uuid.uuid4())
        event = asyncio.Event()
        event.set()  # Immediately set for compatibility
        return event_id, event

    def signal_event(self, event_id: str):
        """Signal an async event from the GUI thread"""
        if self.async_bridge:
            self.async_bridge.signal_from_gui(event_id)

    def cleanup_event(self, event_id: str):
        """Clean up a synchronization event"""
        if self.async_bridge:
            self.async_bridge.cleanup_event(event_id)

    # Convenience methods for common patterns
    def safe_update(
        self, widget, property_name: str, value, callback: Optional[Callable] = None
    ):
        """Safely update a widget property on the GUI thread"""

        def update_widget():
            try:
                if hasattr(widget, property_name):
                    if property_name in {"text", "textvariable"}:
                        widget.config(**{property_name: value})
                    else:
                        setattr(widget, property_name, value)
                if callback:
                    callback()
            except Exception as e:
                self.logger.error(f"Error updating widget {property_name}: {e}")

        self.schedule_immediate(update_widget)

    def safe_call(
        self,
        function: Callable,
        *args,
        error_handler: Optional[Callable] = None,
        **kwargs,
    ):
        """Safely call a function on the GUI thread with error handling"""

        def safe_function():
            try:
                return function(*args, **kwargs)
            except Exception as e:
                self.logger.error(f"Error in safe_call: {e}")
                if error_handler:
                    error_handler(e)

        self.schedule_immediate(safe_function)

    @asynccontextmanager
    async def async_operation(self, operation_name: str):
        """Context manager for async operations with GUI coordination"""
        self.logger.debug(f"Starting async operation: {operation_name}")

        try:
            yield self
        except Exception as e:
            self.logger.error(f"Error in async operation {operation_name}: {e}")
            raise
        finally:
            self.logger.debug(f"Completed async operation: {operation_name}")

    def shutdown(self):
        """Shutdown the GUI coordinator"""
        self._task_processing_active = False
        self.close_all_windows()
        self._managed_windows.clear()
        self._pending_tasks.clear()
        self._sync_events.clear()


# Global GUI coordinator instance (set by main application)
_gui_coordinator: Optional[GUICoordinator] = None


def initialize_gui_coordinator(main_window: tk.Tk, async_bridge=None) -> GUICoordinator:
    """Initialize the global GUI coordinator"""
    global _gui_coordinator
    _gui_coordinator = GUICoordinator(main_window, async_bridge)
    return _gui_coordinator


def get_gui_coordinator() -> Optional[GUICoordinator]:
    """Get the global GUI coordinator instance"""
    return _gui_coordinator


def require_gui_coordinator() -> GUICoordinator:
    """Get the global GUI coordinator, raise error if not initialized"""
    if _gui_coordinator is None:
        raise RuntimeError(
            "GUI coordinator not initialized. Call initialize_gui_coordinator() first."
        )
    return _gui_coordinator
