"""
Service for Git operations
"""

import os
import subprocess
from pathlib import Path
from typing import List, Dict, Tuple, Optional

from config.commands import GIT_COMMANDS


class GitCommit:
    """Represents a git commit"""

    def __init__(self, hash_val: str, author: str, date: str, subject: str):
        self.hash = hash_val
        self.author = author
        self.date = date
        self.subject = subject

    @property
    def display(self) -> str:
        """Get display string for the commit"""
        return f"{self.hash} - {self.date} - {self.author}: {self.subject}"

    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary format"""
        return {
            "hash": self.hash,
            "author": self.author,
            "date": self.date,
            "subject": self.subject,
            "display": self.display,
        }


class GitService:
    """Service for Git operations"""

    def fetch_latest_commits(self, project_path: Path) -> Tuple[bool, str]:
        """
        Fetch latest commits from remote repository
        Returns (success, message)
        """
        try:
            original_cwd = os.getcwd()
            os.chdir(project_path)

            try:
                # Check if there's a remote repository
                remote_check = subprocess.run(
                    GIT_COMMANDS["remote_check"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )

                if remote_check.returncode != 0 or not remote_check.stdout.strip():
                    return False, "No remote repository configured"

                # Fetch from all remotes
                fetch_result = subprocess.run(
                    GIT_COMMANDS["fetch"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )

                if fetch_result.returncode == 0:
                    return True, "Successfully fetched latest commits"
                else:
                    return False, f"Fetch failed: {fetch_result.stderr}"

            finally:
                os.chdir(original_cwd)

        except Exception as e:
            return False, f"Error during fetch: {str(e)}"

    def get_git_commits(
        self, project_path: Path
    ) -> Tuple[Optional[List[GitCommit]], Optional[str]]:
        """Get list of git commits"""
        try:
            # Change to project directory
            original_cwd = os.getcwd()
            os.chdir(project_path)

            try:
                # Get git log using centralized command
                result = subprocess.run(
                    GIT_COMMANDS["log"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )

                if result.returncode != 0:
                    return None, f"Error getting git log: {result.stderr}"

                commits = []
                for line in result.stdout.strip().split("\n"):
                    if line.strip() and "|" in line:
                        # Remove git graph characters
                        clean_line = line
                        for char in ["*", "|", "\\", "/", "-", " "]:
                            if clean_line.startswith(char):
                                clean_line = clean_line[1:]
                            else:
                                break
                        clean_line = clean_line.strip()

                        if "|" in clean_line:
                            parts = clean_line.split("|", 3)
                            if len(parts) >= 4:
                                hash_val, author, date, subject = parts
                                commit = GitCommit(
                                    hash_val.strip(),
                                    author.strip(),
                                    date.strip(),
                                    subject.strip(),
                                )
                                commits.append(commit)

                return commits, None

            finally:
                os.chdir(original_cwd)

        except Exception as e:
            return None, f"Error accessing git repository: {str(e)}"

    def checkout_commit(self, project_path: Path, commit_hash: str) -> Tuple[bool, str]:
        """
        Checkout to specific commit
        Returns (success, message)
        """
        try:
            original_cwd = os.getcwd()
            os.chdir(project_path)

            try:
                # Create checkout command with commit hash
                checkout_cmd = [
                    cmd.format(commit=commit_hash) if "{commit}" in cmd else cmd
                    for cmd in GIT_COMMANDS["checkout"]
                ]

                # Perform checkout
                result = subprocess.run(
                    checkout_cmd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )

                if result.returncode == 0:
                    return True, f"Successfully checked out to commit: {commit_hash}"
                else:
                    return False, result.stderr

            finally:
                os.chdir(original_cwd)

        except Exception as e:
            return False, f"Error during checkout: {str(e)}"

    def force_checkout_commit(
        self, project_path: Path, commit_hash: str
    ) -> Tuple[bool, str]:
        """
        Force checkout to specific commit, discarding local changes
        Returns (success, message)
        """
        try:
            original_cwd = os.getcwd()
            os.chdir(project_path)

            try:
                # First, reset any staged changes
                reset_result = subprocess.run(
                    GIT_COMMANDS["reset_hard"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )

                # Clean untracked files
                clean_result = subprocess.run(
                    GIT_COMMANDS["clean"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )

                # Create checkout command with commit hash
                checkout_cmd = [
                    cmd.format(commit=commit_hash) if "{commit}" in cmd else cmd
                    for cmd in GIT_COMMANDS["checkout"]
                ]

                # Now try checkout again
                force_result = subprocess.run(
                    checkout_cmd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )

                if force_result.returncode == 0:
                    return (
                        True,
                        f"Successfully discarded local changes and checked out to: {commit_hash}",
                    )
                else:
                    return (
                        False,
                        f"Failed to checkout even after discarding changes: {force_result.stderr}",
                    )

            finally:
                os.chdir(original_cwd)

        except Exception as e:
            return False, f"Error during force checkout: {str(e)}"

    def has_local_changes(self, project_path: Path, error_message: str) -> bool:
        """
        Check if the error is due to local changes
        Returns True if the error indicates local changes would be overwritten
        """
        local_change_indicators = [
            "would be overwritten",
            "local changes",
            "uncommitted changes",
            "working tree clean",
        ]

        return any(
            indicator in error_message.lower() for indicator in local_change_indicators
        )
