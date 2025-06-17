"""
Data models for the Project Control Panel
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class Project:
    """Represents a project with its metadata"""

    parent: str
    name: str
    path: Path
    relative_path: str

    @property
    def display_name(self) -> str:
        """Get the display name for the project"""
        return self.name

    @property
    def full_path(self) -> str:
        """Get the full path as string"""
        return str(self.path)

    def __str__(self) -> str:
        return f"{self.parent}/{self.name}"
