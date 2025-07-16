"""
File monitoring service for detecting changes in project directories
"""

import os
import time
import threading
from pathlib import Path
from typing import Dict, Callable, Set, Optional
from dataclasses import dataclass
import logging
from config.config import get_config

logger = logging.getLogger(__name__)

# Get config values
config = get_config()
IGNORE_DIRS = config.project.ignore_dirs
IGNORE_FILES = config.project.ignore_files


@dataclass
class FileInfo:
    """Information about a file for change detection"""

    path: Path
    modified_time: float
    size: int


class FileMonitorService:
    """Service for monitoring file changes in project directories"""

    def __init__(self, check_interval: float = 1.0):
        self.check_interval = check_interval
        self.monitored_projects: Dict[str, Dict] = (
            {}
        )  # project_key -> {path, callback, last_check, files}
        self.monitoring_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.lock = threading.Lock()

    def start_monitoring(
        self, project_key: str, project_path: Path, callback: Callable[[str], None]
    ):
        """Start monitoring a project directory for file changes"""
        with self.lock:
            self.monitored_projects[project_key] = {
                "path": project_path,
                "callback": callback,
                "last_check": time.time(),
                "files": self._scan_directory(project_path),
            }

            # Start monitoring thread if not already running
            if self.monitoring_thread is None or not self.monitoring_thread.is_alive():
                self.stop_event.clear()
                self.monitoring_thread = threading.Thread(
                    target=self._monitor_loop, daemon=True
                )
                self.monitoring_thread.start()
                logger.info(f"Started monitoring {project_key} at {project_path}")

    def stop_monitoring(self, project_key: str):
        """Stop monitoring a specific project"""
        with self.lock:
            if project_key in self.monitored_projects:
                del self.monitored_projects[project_key]
                logger.info(f"Stopped monitoring {project_key}")

            # Stop monitoring thread if no projects left
            if not self.monitored_projects:
                self.stop_event.set()

    def stop_all_monitoring(self):
        """Stop monitoring all projects"""
        with self.lock:
            self.monitored_projects.clear()
            self.stop_event.set()
            logger.info("Stopped monitoring all projects")

    def _scan_directory(self, path: Path) -> Dict[str, FileInfo]:
        """Scan directory and return file information"""
        files = {}
        if not path.exists():
            return files

        try:
            for root, dirs, filenames in os.walk(path):
                # Skip hidden directories and common ignore patterns
                dirs[:] = [
                    d for d in dirs if not d.startswith(".") and d not in IGNORE_DIRS
                ]

                for filename in filenames:
                    # Skip hidden files and common ignore patterns
                    if filename in IGNORE_FILES:
                        continue

                    file_path = Path(root) / filename
                    try:
                        stat = file_path.stat()
                        files[str(file_path)] = FileInfo(
                            path=file_path,
                            modified_time=stat.st_mtime,
                            size=stat.st_size,
                        )
                    except OSError:
                        # Skip files we can't access
                        continue

        except OSError as e:
            logger.warning(f"Error scanning directory {path}: {e}")

        return files

    def _monitor_loop(self):
        """Main monitoring loop"""
        while not self.stop_event.is_set():
            try:
                with self.lock:
                    projects_to_check = list(self.monitored_projects.items())

                for project_key, project_info in projects_to_check:
                    try:
                        self._check_project_changes(project_key, project_info)
                    except Exception as e:
                        logger.error(f"Error checking project {project_key}: {e}")

                # Sleep but check for stop signal
                self.stop_event.wait(self.check_interval)

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(self.check_interval)

    def _check_project_changes(self, project_key: str, project_info: Dict):
        """Check for changes in a specific project"""
        current_files = self._scan_directory(project_info["path"])
        previous_files = project_info["files"]

        # Check for changes
        changes_detected = False

        # Check for new files
        for file_path, file_info in current_files.items():
            if file_path not in previous_files:
                changes_detected = True
                logger.debug(f"New file detected: {file_path}")
                break

            # Check for modified files
            prev_file = previous_files[file_path]
            if (
                file_info.modified_time != prev_file.modified_time
                or file_info.size != prev_file.size
            ):
                changes_detected = True
                logger.debug(f"Modified file detected: {file_path}")
                break

        # Check for deleted files
        if not changes_detected:
            for file_path in previous_files:
                if file_path not in current_files:
                    changes_detected = True
                    logger.debug(f"Deleted file detected: {file_path}")
                    break

        # Update stored files and notify if changes detected
        project_info["files"] = current_files
        project_info["last_check"] = time.time()

        if changes_detected:
            try:
                project_info["callback"](project_key)
            except Exception as e:
                logger.error(f"Error in change callback for {project_key}: {e}")


# Global instance for the application
file_monitor = FileMonitorService()
