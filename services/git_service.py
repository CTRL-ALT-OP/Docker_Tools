"""
Service for Git operations - Async version
"""

import os
from pathlib import Path
from typing import List, Dict, Tuple, Optional

from config.commands import GIT_COMMANDS
from utils.async_utils import run_subprocess_async, run_in_executor


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
    """Service for Git operations - Async version"""

    async def fetch_latest_commits(self, project_path: Path) -> Tuple[bool, str]:
        """
        Fetch latest commits from remote repository
        Returns (success, message)
        """
        try:
            # Check if there's a remote repository
            remote_check = await run_subprocess_async(
                GIT_COMMANDS["remote_check"], cwd=str(project_path)
            )

            if remote_check.returncode != 0 or not remote_check.stdout.strip():
                return False, "No remote repository configured"

            # Fetch from all remotes
            fetch_result = await run_subprocess_async(
                GIT_COMMANDS["fetch"], cwd=str(project_path)
            )

            if fetch_result.returncode == 0:
                return True, "Successfully fetched latest commits"
            else:
                return False, f"Fetch failed: {fetch_result.stderr}"

        except Exception as e:
            return False, f"Error during fetch: {str(e)}"

    async def get_git_commits(
        self, project_path: Path
    ) -> Tuple[Optional[List[GitCommit]], Optional[str]]:
        """
        Get list of all git commits

        Args:
            project_path: Path to the git repository
        """
        try:
            # Run git log command
            result = await run_subprocess_async(
                GIT_COMMANDS["log"], cwd=str(project_path)
            )

            if result.returncode != 0:
                return None, f"Error getting git log: {result.stderr}"

            # Parse commits in executor to avoid blocking
            commits = await run_in_executor(self._parse_commits, result.stdout.strip())
            return commits, None

        except Exception as e:
            return None, f"Error accessing git repository: {str(e)}"

    def _parse_commits(self, log_output: str) -> List[GitCommit]:
        """Parse git log output into GitCommit objects"""
        commits = []
        for line in log_output.split("\n"):
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
        return commits

    async def checkout_commit(
        self, project_path: Path, commit_hash: str
    ) -> Tuple[bool, str]:
        """
        Checkout to specific commit
        Returns (success, message)
        """
        try:
            # Create checkout command with commit hash
            checkout_cmd = [
                cmd.format(commit=commit_hash) if "{commit}" in cmd else cmd
                for cmd in GIT_COMMANDS["checkout"]
            ]

            # Perform checkout
            result = await run_subprocess_async(checkout_cmd, cwd=str(project_path))

            if result.returncode == 0:
                return True, f"Successfully checked out to commit: {commit_hash}"
            else:
                return False, result.stderr

        except Exception as e:
            return False, f"Error during checkout: {str(e)}"

    async def force_checkout_commit(
        self, project_path: Path, commit_hash: str
    ) -> Tuple[bool, str]:
        """
        Force checkout to specific commit, discarding local changes
        Returns (success, message)
        """
        try:
            # First, reset any staged changes
            reset_result = await run_subprocess_async(
                GIT_COMMANDS["reset_hard"], cwd=str(project_path)
            )

            # Clean untracked files
            clean_result = await run_subprocess_async(
                GIT_COMMANDS["clean"], cwd=str(project_path)
            )

            # Now try force checkout
            force_result = await run_subprocess_async(
                [
                    cmd.format(commit=commit_hash) if "{commit}" in cmd else cmd
                    for cmd in GIT_COMMANDS["force_checkout"]
                ],
                cwd=str(project_path),
            )

            if force_result.returncode == 0:
                return True, f"Successfully force checked out to commit: {commit_hash}"
            else:
                return False, force_result.stderr

        except Exception as e:
            return False, f"Error during force checkout: {str(e)}"

    def has_local_changes(self, project_path: Path, error_message: str) -> bool:
        """
        Check if error message indicates local changes would be overwritten
        """
        local_change_indicators = [
            "would be overwritten",
            "local changes",
            "working tree clean",
            "uncommitted changes",
        ]

        return any(
            indicator in error_message.lower() for indicator in local_change_indicators
        )

    async def clone_repository(
        self, repo_url: str, project_name: str, destination_path: Path
    ) -> Tuple[bool, str]:
        """
        Clone a Git repository to the specified destination
        Returns (success, message)
        """
        try:
            # Create clone command with repo URL and project name
            clone_cmd = [
                (
                    cmd.format(repo_url=repo_url, project_name=project_name)
                    if "{repo_url}" in cmd or "{project_name}" in cmd
                    else cmd
                )
                for cmd in GIT_COMMANDS["clone"]
            ]

            # Perform clone in the destination directory
            result = await run_subprocess_async(clone_cmd, cwd=str(destination_path))

            if result.returncode == 0:
                return True, f"Successfully cloned repository to {project_name}"
            else:
                return False, f"Clone failed: {result.stderr}"

        except Exception as e:
            return False, f"Error during clone: {str(e)}"
