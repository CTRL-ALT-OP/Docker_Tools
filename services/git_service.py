"""
Git Service - Standardized Async Version
"""

from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

from config.commands import GIT_COMMANDS
from utils.async_base import (
    AsyncServiceInterface,
    ServiceResult,
    ProcessError,
    ValidationError,
    ResourceError,
    AsyncServiceContext,
)
from utils.async_utils import run_subprocess_async, run_in_executor


@dataclass
class GitCommit:
    """Represents a git commit with standardized structure"""

    hash: str
    author: str
    date: str
    subject: str
    parents: Optional[List[str]] = None
    source_branch: Optional[str] = None

    @property
    def is_merge_commit(self) -> bool:
        """Check if this is a merge commit (has multiple parents)"""
        return self.parents and len(self.parents) > 1

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
            "parents": self.parents,
            "source_branch": self.source_branch,
            "is_merge_commit": self.is_merge_commit,
            "display": self.display,
        }


@dataclass
class GitRepositoryInfo:
    """Information about a git repository"""

    has_remote: bool
    remote_urls: List[str]
    current_branch: str
    current_commit: str
    is_clean: bool
    uncommitted_changes: int


class GitService(AsyncServiceInterface):
    """Standardized Git service with consistent async interface"""

    def __init__(self):
        super().__init__("GitService")

    async def health_check(self) -> ServiceResult[Dict[str, Any]]:
        """Check Git service health"""
        async with self.operation_context("health_check", timeout=10.0) as ctx:
            try:
                # Check if git is available
                result = await run_subprocess_async(
                    GIT_COMMANDS["version"], capture_output=True, timeout=5.0
                )

                if result.returncode == 0:
                    return ServiceResult.success(
                        {
                            "status": "healthy",
                            "git_version": result.stdout.strip(),
                            "available_commands": list(GIT_COMMANDS.keys()),
                        }
                    )
                error = ProcessError(
                    "Git is not available",
                    return_code=result.returncode,
                    stderr=result.stderr,
                )
                return ServiceResult.error(error)

            except Exception as e:
                error = ProcessError(f"Failed to check Git availability: {str(e)}")
                return ServiceResult.error(error)

    async def get_repository_info(
        self, project_path: Path
    ) -> ServiceResult[GitRepositoryInfo]:
        """Get comprehensive information about a git repository"""
        # Validate input
        if not project_path.exists():
            error = ValidationError(f"Project path does not exist: {project_path}")
            return ServiceResult.error(error)

        async with self.operation_context("get_repository_info", timeout=30.0) as ctx:
            try:
                # Check if it's a git repository
                git_dir_check = await run_subprocess_async(
                    GIT_COMMANDS["rev_parse_git_dir"],
                    cwd=str(project_path),
                    capture_output=True,
                )

                if git_dir_check.returncode != 0:
                    error = ResourceError(f"Not a git repository: {project_path}")
                    return ServiceResult.error(error)

                # Get remote information
                remote_result = await run_subprocess_async(
                    GIT_COMMANDS["remote_check"],
                    cwd=str(project_path),
                    capture_output=True,
                )

                has_remote = (
                    remote_result.returncode == 0 and remote_result.stdout.strip()
                )
                remote_urls = (
                    remote_result.stdout.strip().split("\n") if has_remote else []
                )

                # Get current branch
                branch_result = await run_subprocess_async(
                    GIT_COMMANDS["branch_show_current"],
                    cwd=str(project_path),
                    capture_output=True,
                )
                current_branch = (
                    branch_result.stdout.strip()
                    if branch_result.returncode == 0
                    else "unknown"
                )

                # Get current commit
                commit_result = await run_subprocess_async(
                    GIT_COMMANDS["rev_parse_head"],
                    cwd=str(project_path),
                    capture_output=True,
                )
                current_commit = (
                    commit_result.stdout.strip()
                    if commit_result.returncode == 0
                    else "unknown"
                )

                # Check if working tree is clean
                status_result = await run_subprocess_async(
                    GIT_COMMANDS["status_porcelain"],
                    cwd=str(project_path),
                    capture_output=True,
                )

                is_clean = (
                    status_result.returncode == 0 and not status_result.stdout.strip()
                )
                uncommitted_changes = (
                    len(status_result.stdout.strip().split("\n"))
                    if status_result.stdout.strip()
                    else 0
                )

                repo_info = GitRepositoryInfo(
                    has_remote=has_remote,
                    remote_urls=remote_urls,
                    current_branch=current_branch,
                    current_commit=current_commit[:8],  # Short commit hash
                    is_clean=is_clean,
                    uncommitted_changes=uncommitted_changes,
                )

                return ServiceResult.success(
                    repo_info, "Repository information retrieved successfully"
                )

            except Exception as e:
                self.logger.exception("Unexpected error getting repository info")
                error = ProcessError(f"Failed to get repository info: {str(e)}")
                return ServiceResult.error(error)

    async def fetch_latest_commits(self, project_path: Path) -> ServiceResult[str]:
        """Fetch latest commits from remote repository"""
        # Validate input
        if not project_path.exists():
            error = ValidationError(f"Project path does not exist: {project_path}")
            return ServiceResult.error(error)

        async with self.operation_context("fetch_latest_commits", timeout=60.0) as ctx:
            try:
                # Check repository info first
                repo_info_result = await self.get_repository_info(project_path)
                if repo_info_result.is_error:
                    return ServiceResult.error(repo_info_result.error)

                repo_info = repo_info_result.data
                if not repo_info.has_remote:
                    error = ResourceError("No remote repository configured")
                    return ServiceResult.error(error)

                # Fetch from all remotes
                fetch_result = await run_subprocess_async(
                    GIT_COMMANDS["fetch"], cwd=str(project_path), capture_output=True
                )

                if fetch_result.returncode == 0:
                    return ServiceResult.success(
                        "fetch_completed",
                        message="Successfully fetched latest commits",
                        metadata={
                            "remote_urls": repo_info.remote_urls,
                            "fetch_output": fetch_result.stdout,
                        },
                    )
                error = ProcessError(
                    f"Fetch failed: {fetch_result.stderr}",
                    return_code=fetch_result.returncode,
                    stderr=fetch_result.stderr,
                )
                return ServiceResult.error(error)

            except Exception as e:
                self.logger.exception("Unexpected error during fetch")
                error = ProcessError(f"Error during fetch: {str(e)}")
                return ServiceResult.error(error)

    async def get_git_commits(
        self, project_path: Path, limit: int = None
    ) -> ServiceResult[List[GitCommit]]:
        """Get list of git commits with standardized result format (all commits by default)"""
        # Validate input
        if not project_path.exists():
            error = ValidationError(f"Project path does not exist: {project_path}")
            return ServiceResult.error(error)

        if limit is not None and limit <= 0:
            error = ValidationError("Commit limit must be positive")
            return ServiceResult.error(error)

        async with self.operation_context("get_git_commits", timeout=60.0) as ctx:
            try:
                # Check if it's a git repository
                repo_info_result = await self.get_repository_info(project_path)
                if repo_info_result.is_error:
                    return ServiceResult.error(repo_info_result.error)

                # Run git log command with or without limit
                if limit is not None:
                    git_log_cmd = GIT_COMMANDS["log"] + [f"-{limit}"]
                else:
                    git_log_cmd = GIT_COMMANDS["log"]  # Get ALL commits

                result = await run_subprocess_async(
                    git_log_cmd, cwd=str(project_path), capture_output=True
                )

                if result.returncode != 0:
                    error = ProcessError(
                        f"Error getting git log: {result.stderr}",
                        return_code=result.returncode,
                        stderr=result.stderr,
                    )
                    return ServiceResult.error(error)

                # Parse commits in executor to avoid blocking
                commits = await run_in_executor(
                    self._parse_commits, result.stdout.strip()
                )

                return ServiceResult.success(
                    commits,
                    message=f"Retrieved {len(commits)} commits"
                    + (f" (limited to {limit})" if limit else " (all commits)"),
                    metadata={
                        "total_commits": len(commits),
                        "limit_applied": limit,
                        "repository_path": str(project_path),
                    },
                )

            except Exception as e:
                self.logger.exception("Unexpected error getting git commits")
                error = ProcessError(f"Error accessing git repository: {str(e)}")
                return ServiceResult.error(error)

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
                            hash=hash_val.strip(),
                            author=author.strip(),
                            date=date.strip(),
                            subject=subject.strip(),
                        )
                        commits.append(commit)
        return commits

    async def checkout_commit(
        self, project_path: Path, commit_hash: str
    ) -> ServiceResult[str]:
        """Checkout to specific commit with standardized result format"""
        # Validate input
        if not project_path.exists():
            error = ValidationError(f"Project path does not exist: {project_path}")
            return ServiceResult.error(error)

        if not commit_hash or len(commit_hash) < 6:
            error = ValidationError("Commit hash must be at least 6 characters")
            return ServiceResult.error(error)

        async with self.operation_context("checkout_commit", timeout=30.0) as ctx:
            try:
                # Check repository status first
                repo_info_result = await self.get_repository_info(project_path)
                if repo_info_result.is_error:
                    return ServiceResult.error(repo_info_result.error)

                repo_info = repo_info_result.data

                # Create checkout command with commit hash
                checkout_cmd = [
                    cmd.format(commit=commit_hash) if "{commit}" in cmd else cmd
                    for cmd in GIT_COMMANDS["checkout"]
                ]

                # Perform checkout
                result = await run_subprocess_async(
                    checkout_cmd, cwd=str(project_path), capture_output=True
                )

                if result.returncode == 0:
                    return ServiceResult.success(
                        commit_hash,
                        message=f"Successfully checked out to commit: {commit_hash}",
                        metadata={
                            "previous_commit": repo_info.current_commit,
                            "previous_branch": repo_info.current_branch,
                            "checkout_output": result.stdout,
                        },
                    )
                    # Check if this is due to local changes
                error = (
                    ResourceError(
                        f"Cannot checkout due to local changes: {result.stderr}",
                        resource_path=str(project_path),
                    )
                    if self.has_local_changes(project_path, result.stderr)
                    else ProcessError(
                        f"Checkout failed: {result.stderr}",
                        return_code=result.returncode,
                        stderr=result.stderr,
                    )
                )
                return ServiceResult.error(error)

            except Exception as e:
                self.logger.exception("Unexpected error during checkout")
                error = ProcessError(f"Error during checkout: {str(e)}")
                return ServiceResult.error(error)

    async def force_checkout_commit(
        self, project_path: Path, commit_hash: str
    ) -> ServiceResult[str]:
        """Force checkout to specific commit, discarding local changes"""
        # Validate input
        if not project_path.exists():
            error = ValidationError(f"Project path does not exist: {project_path}")
            return ServiceResult.error(error)

        async with self.operation_context("force_checkout_commit", timeout=60.0) as ctx:
            try:
                # Get repository info before changes
                repo_info_result = await self.get_repository_info(project_path)
                if repo_info_result.is_error:
                    return ServiceResult.error(repo_info_result.error)

                repo_info = repo_info_result.data

                # First, reset any staged changes
                reset_result = await run_subprocess_async(
                    GIT_COMMANDS["reset_hard"],
                    cwd=str(project_path),
                    capture_output=True,
                )

                # Clean untracked files
                clean_result = await run_subprocess_async(
                    GIT_COMMANDS["clean"], cwd=str(project_path), capture_output=True
                )

                # Now try force checkout
                force_result = await run_subprocess_async(
                    [
                        cmd.format(commit=commit_hash) if "{commit}" in cmd else cmd
                        for cmd in GIT_COMMANDS["force_checkout"]
                    ],
                    cwd=str(project_path),
                    capture_output=True,
                )

                if force_result.returncode == 0:
                    return ServiceResult.success(
                        commit_hash,
                        message=f"Successfully force checked out to commit: {commit_hash}",
                        metadata={
                            "previous_commit": repo_info.current_commit,
                            "previous_branch": repo_info.current_branch,
                            "discarded_changes": repo_info.uncommitted_changes,
                            "reset_output": reset_result.stdout,
                            "clean_output": clean_result.stdout,
                        },
                    )
                error = ProcessError(
                    f"Force checkout failed: {force_result.stderr}",
                    return_code=force_result.returncode,
                    stderr=force_result.stderr,
                )
                return ServiceResult.error(error)

            except Exception as e:
                self.logger.exception("Unexpected error during force checkout")
                error = ProcessError(f"Error during force checkout: {str(e)}")
                return ServiceResult.error(error)

    def has_local_changes(self, project_path: Path, error_message: str) -> bool:
        """Check if error message indicates local changes would be overwritten"""
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
    ) -> ServiceResult[Path]:
        """Clone a Git repository to the specified destination"""
        # Validate input
        if not repo_url:
            error = ValidationError("Repository URL cannot be empty")
            return ServiceResult.error(error)

        if not project_name:
            error = ValidationError("Project name cannot be empty")
            return ServiceResult.error(error)

        async with self.operation_context("clone_repository", timeout=300.0) as ctx:
            try:
                # Ensure destination directory exists
                destination_path.mkdir(parents=True, exist_ok=True)
                target_path = destination_path / project_name

                # Check if target already exists
                if target_path.exists():
                    error = ResourceError(
                        f"Target directory already exists: {target_path}"
                    )
                    return ServiceResult.error(error)

                # Now perform the clone
                clone_cmd = [
                    (
                        part.format(repo_url=repo_url, project_name=project_name)
                        if "{repo_url}" in part or "{project_name}" in part
                        else part
                    )
                    for part in GIT_COMMANDS["clone"]
                ]
                result = await run_subprocess_async(
                    clone_cmd,
                    cwd=str(destination_path),
                    capture_output=True,
                    timeout=300.0,
                )

                if result.returncode == 0:
                    return ServiceResult.success(
                        target_path,
                        message=f"Successfully cloned repository to {target_path}",
                        metadata={
                            "repo_url": repo_url,
                            "project_name": project_name,
                            "clone_output": result.stdout,
                        },
                    )
                error = ProcessError(
                    f"Clone failed: {result.stderr}",
                    return_code=result.returncode,
                    stderr=result.stderr,
                )
                return ServiceResult.error(error)

            except Exception as e:
                self.logger.exception("Unexpected error during repository clone")
                error = ProcessError(f"Error cloning repository: {str(e)}")
                return ServiceResult.error(error)
