"""
Git Service - Standardized Async Version
"""

from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

from config.commands import COMMANDS
from services.platform_service import PlatformService
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
        branch_info = ""
        if self.source_branch:
            # Clean up branch name for display - handle all common git reference formats
            branch_display = self.source_branch

            # Remove various git reference prefixes
            if branch_display.startswith("refs/remotes/origin/"):
                branch_display = branch_display[20:]  # Remove 'refs/remotes/origin/'
            elif branch_display.startswith("refs/remotes/"):
                # Handle other remotes (not just origin)
                parts = branch_display.split("/", 3)
                if len(parts) >= 4:
                    branch_display = parts[
                        3
                    ]  # Get branch name after refs/remotes/remote/
            elif branch_display.startswith("remotes/origin/"):
                branch_display = branch_display[15:]  # Remove 'remotes/origin/'
            elif branch_display.startswith("remotes/"):
                # Handle other remotes
                parts = branch_display.split("/", 2)
                if len(parts) >= 3:
                    branch_display = parts[2]  # Get branch name after remotes/remote/
            elif branch_display.startswith("refs/heads/"):
                branch_display = branch_display[11:]  # Remove 'refs/heads/'
            elif branch_display.startswith("origin/"):
                branch_display = branch_display[7:]  # Remove 'origin/'

            # Remove any remaining git revision specifiers
            if "~" in branch_display:
                branch_display = branch_display.split("~")[0]
            if "^" in branch_display:
                branch_display = branch_display.split("^")[0]

            # Handle special cases for more meaningful display
            if branch_display.startswith("master") or branch_display.startswith("main"):
                # These are commits on the main branch
                branch_info = (
                    "[master]"  # Standardize on [master] for main branch commits
                )
            elif branch_display not in ["master", "main", "HEAD", ""]:
                # Show branch info for feature/topic branches
                # Clean up any remaining unwanted characters
                clean_branch = branch_display.strip()
                if clean_branch and not clean_branch.startswith("HEAD"):
                    branch_info = f"[{clean_branch}]"
                else:
                    branch_info = (
                        "[master]"  # Fallback to master if branch name is unclear
                    )
            else:
                # This is a master/main branch commit
                branch_info = "[master]"
        else:
            # No source branch detected, this is a main branch commit
            branch_info = "[master]"

        merge_info = "(merge)" if self.is_merge_commit else ""

        # Combine branch and merge info with space separator if both exist
        tag_info = ""
        if branch_info and merge_info:
            tag_info = f"{branch_info} {merge_info}"
        elif branch_info:
            tag_info = branch_info
        elif merge_info:
            tag_info = merge_info

        # Format: hash - date - author [branch] (merge): subject
        return f"{self.hash} - {self.date} - {self.author} {tag_info}: {self.subject}"

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
                # Check if git is available using PlatformService
                result = await PlatformService.run_command_async(
                    "GIT_COMMANDS",
                    subkey="version",
                    capture_output=True,
                    timeout=5.0,
                )

                if result.returncode == 0:
                    return ServiceResult.success(
                        {
                            "status": "healthy",
                            "git_version": result.stdout.strip(),
                            "available_commands": list(COMMANDS["GIT_COMMANDS"].keys()),
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
                git_dir_check = await PlatformService.run_command_async(
                    "GIT_COMMANDS",
                    subkey="rev_parse_git_dir",
                    cwd=str(project_path),
                    capture_output=True,
                )

                if git_dir_check.returncode != 0:
                    error = ResourceError(f"Not a git repository: {project_path}")
                    return ServiceResult.error(error)

                # Get remote information
                remote_result = await PlatformService.run_command_async(
                    "GIT_COMMANDS",
                    subkey="remote_check",
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
                branch_result = await PlatformService.run_command_async(
                    "GIT_COMMANDS",
                    subkey="branch_show_current",
                    cwd=str(project_path),
                    capture_output=True,
                )
                current_branch = (
                    branch_result.stdout.strip()
                    if branch_result.returncode == 0
                    else "unknown"
                )

                # Get current commit
                commit_result = await PlatformService.run_command_async(
                    "GIT_COMMANDS",
                    subkey="rev_parse_head",
                    cwd=str(project_path),
                    capture_output=True,
                )
                current_commit = (
                    commit_result.stdout.strip()
                    if commit_result.returncode == 0
                    else "unknown"
                )

                # Check if working tree is clean
                status_result = await PlatformService.run_command_async(
                    "GIT_COMMANDS",
                    subkey="status_porcelain",
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

                # Fetch from all remotes using PlatformService
                fetch_result = await PlatformService.run_command_async(
                    "GIT_COMMANDS",
                    subkey="fetch",
                    cwd=str(project_path),
                    capture_output=True,
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
                    # For limited results, we need to construct the command manually
                    # since the platform service doesn't handle dynamic argument appending
                    git_log_cmd = COMMANDS["GIT_COMMANDS"]["log"] + [f"-{limit}"]
                    result = await run_subprocess_async(
                        git_log_cmd, cwd=str(project_path), capture_output=True
                    )
                else:
                    # Get ALL commits using PlatformService
                    result = await PlatformService.run_command_async(
                        "GIT_COMMANDS",
                        subkey="log",
                        cwd=str(project_path),
                        capture_output=True,
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

                # Detect source branches for each commit
                commits_with_branches = await self._detect_source_branches(
                    commits, project_path
                )

                return ServiceResult.success(
                    commits_with_branches,
                    message=f"Retrieved {len(commits_with_branches)} commits with branch information"
                    + (f" (limited to {limit})" if limit else " (all commits)"),
                    metadata={
                        "total_commits": len(commits_with_branches),
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
                    parts = clean_line.split("|", 4)
                    if len(parts) >= 5:
                        hash_val, parents_str, author, date, subject = parts

                        # Parse parent hashes
                        parents = []
                        if parents_str.strip():
                            parents = [p.strip() for p in parents_str.strip().split()]

                        commit = GitCommit(
                            hash=hash_val.strip(),
                            author=author.strip(),
                            date=date.strip(),
                            subject=subject.strip(),
                            parents=parents,
                        )
                        commits.append(commit)
        return commits

    async def _detect_source_branches(
        self, commits: List[GitCommit], project_path: Path
    ) -> List[GitCommit]:
        """Detect source branches for each commit using improved logic"""
        try:
            # Get the main branch commit history first
            main_branch_commits = await self._get_main_branch_commits(project_path)

            # Process commits in batches to avoid too many subprocess calls
            batch_size = 5  # Smaller batch size for more complex operations
            updated_commits = []

            for i in range(0, len(commits), batch_size):
                batch = commits[i : i + batch_size]
                batch_results = await self._detect_branches_batch_improved(
                    batch, project_path, main_branch_commits
                )
                updated_commits.extend(batch_results)

            return updated_commits

        except Exception as e:
            self.logger.warning(f"Failed to detect source branches: {str(e)}")
            # Return original commits if branch detection fails
            return commits

    async def _get_main_branch_commits(self, project_path: Path) -> set:
        """Get set of commits that are in the main branch history"""
        try:
            # First, try to get main branch commits from the actual master/main branch
            # instead of current HEAD (which might be detached)
            main_branch_refs = ["origin/master", "origin/main", "master", "main"]

            for branch_ref in main_branch_refs:
                try:
                    # Check if this branch reference exists
                    ref_check = await run_subprocess_async(
                        ["git", "rev-parse", "--verify", f"{branch_ref}^{{commit}}"],
                        cwd=str(project_path),
                        capture_output=True,
                        timeout=5.0,
                    )

                    if ref_check.returncode == 0:
                        # Get first-parent history from this specific branch
                        result = await run_subprocess_async(
                            [
                                "git",
                                "rev-list",
                                "--first-parent",
                                "--pretty=format:%h",
                                branch_ref,
                            ],
                            cwd=str(project_path),
                            capture_output=True,
                            timeout=10.0,
                        )

                        if result.returncode == 0:
                            main_commits = set()
                            for line in result.stdout.strip().split("\n"):
                                if line.strip() and not line.startswith("commit"):
                                    if commit_hash := line.strip():
                                        main_commits.add(commit_hash)

                            self.logger.debug(
                                f"Got main branch commits from {branch_ref}: {len(main_commits)} commits"
                            )
                            return main_commits
                except Exception:
                    continue  # Try next branch reference

            # Fallback: use HEAD if no main branch found (original behavior)
            self.logger.warning("No main branch reference found, falling back to HEAD")
            result = await PlatformService.run_command_async(
                "GIT_COMMANDS",
                subkey="log_first_parent",
                cwd=str(project_path),
                capture_output=True,
                timeout=10.0,
            )

            if result.returncode == 0:
                main_commits = set()
                for line in result.stdout.strip().split("\n"):
                    if line.strip() and not line.startswith("commit"):
                        if commit_hash := line.strip():
                            main_commits.add(commit_hash)
                return main_commits
            else:
                self.logger.warning(
                    f"Failed to get main branch commits: {result.stderr}"
                )
                return set()
        except Exception as e:
            self.logger.warning(f"Error getting main branch commits: {str(e)}")
            return set()

    async def _detect_branches_batch_improved(
        self, commits: List[GitCommit], project_path: Path, main_branch_commits: set
    ) -> List[GitCommit]:
        """Detect branches for a batch of commits using improved logic"""
        import asyncio

        async def detect_single_branch_improved(commit: GitCommit) -> GitCommit:
            try:
                # Check if commit is in main branch history
                if commit.hash in main_branch_commits:
                    # This is a main branch commit, no need to show branch info
                    return commit

                # For non-main branch commits, try multiple approaches to find original branch

                # Approach 1: Use git name-rev with better parsing
                try:
                    name_rev_result = await run_subprocess_async(
                        ["git", "name-rev", "--name-only", commit.hash],
                        cwd=str(project_path),
                        capture_output=True,
                        timeout=5.0,
                    )

                    if (
                        name_rev_result.returncode == 0
                        and name_rev_result.stdout.strip()
                    ):
                        branch_name = name_rev_result.stdout.strip()

                        # Parse name-rev output to extract meaningful branch names
                        if branch_name and branch_name != "undefined":
                            cleaned_branch = self._clean_branch_name(branch_name)
                            if cleaned_branch and cleaned_branch not in [
                                "master",
                                "main",
                                "HEAD",
                            ]:
                                commit.source_branch = cleaned_branch
                                return commit
                except Exception:
                    pass  # Fall back to approach 2

                # Approach 2: Use git branch --contains with better logic
                # Using PlatformService for branch contains check
                result = await PlatformService.run_command_async(
                    "GIT_COMMANDS",
                    subkey="branch_contains",
                    commit=commit.hash,
                    cwd=str(project_path),
                    capture_output=True,
                    timeout=5.0,
                )

                if result.returncode == 0 and result.stdout.strip():
                    feature_branches = []
                    for line in result.stdout.strip().split("\n"):
                        line = line.strip()
                        if line and not line.startswith("*"):
                            # Clean up branch name using the centralized method
                            cleaned_branch = self._clean_branch_name(line)

                            # Collect feature branches (not master/main)
                            if (
                                cleaned_branch
                                and cleaned_branch not in ["master", "main", "HEAD"]
                                and not cleaned_branch.startswith("HEAD")
                                and not cleaned_branch.endswith("master")
                                and not cleaned_branch.endswith("main")
                            ):
                                feature_branches.append(cleaned_branch)

                    # If we found feature branches, use the first one
                    # (this will be the original branch for commits that exist in multiple branches)
                    if feature_branches:
                        commit.source_branch = feature_branches[0]

                return commit

            except Exception as e:
                self.logger.debug(
                    f"Failed to detect branch for commit {commit.hash}: {str(e)}"
                )
                return commit

        # Process commits in parallel for better performance
        tasks = [detect_single_branch_improved(commit) for commit in commits]
        return await asyncio.gather(*tasks)

    def _clean_branch_name(self, branch_name: str) -> str:
        """
        Cleans up a branch name to remove common git reference prefixes and suffixes.
        Returns the clean branch name without any formatting.
        """
        if not branch_name or not branch_name.strip():
            return ""

        cleaned = branch_name.strip()

        # Remove common git reference prefixes
        if cleaned.startswith("refs/remotes/origin/"):
            cleaned = cleaned[20:]  # Remove 'refs/remotes/origin/'
        elif cleaned.startswith("refs/remotes/"):
            # Handle other remotes (not just origin)
            parts = cleaned.split("/", 3)
            if len(parts) >= 4:
                cleaned = parts[3]  # Get branch name after refs/remotes/remote/
        elif cleaned.startswith("remotes/origin/"):
            cleaned = cleaned[15:]  # Remove 'remotes/origin/'
        elif cleaned.startswith("remotes/"):
            # Handle other remotes
            parts = cleaned.split("/", 2)
            if len(parts) >= 3:
                cleaned = parts[2]  # Get branch name after remotes/remote/
        elif cleaned.startswith("refs/heads/"):
            cleaned = cleaned[11:]  # Remove 'refs/heads/'
        elif cleaned.startswith("origin/"):
            cleaned = cleaned[7:]  # Remove 'origin/'

        # Remove any remaining git revision specifiers
        if "~" in cleaned:
            cleaned = cleaned.split("~")[0]
        if "^" in cleaned:
            cleaned = cleaned.split("^")[0]

        # Remove any leading/trailing whitespace and special characters
        cleaned = cleaned.strip()

        # Handle special git patterns
        return "" if cleaned.startswith("HEAD") else cleaned

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

                # Perform checkout using PlatformService
                result = await PlatformService.run_command_async(
                    "GIT_COMMANDS",
                    subkey="checkout",
                    commit=commit_hash,
                    cwd=str(project_path),
                    capture_output=True,
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

                # First, reset any staged changes using PlatformService
                reset_result = await PlatformService.run_command_async(
                    "GIT_COMMANDS",
                    subkey="reset_hard",
                    cwd=str(project_path),
                    capture_output=True,
                )

                # Clean untracked files using PlatformService
                clean_result = await PlatformService.run_command_async(
                    "GIT_COMMANDS",
                    subkey="clean",
                    cwd=str(project_path),
                    capture_output=True,
                )

                # Now try force checkout using PlatformService
                force_result = await PlatformService.run_command_async(
                    "GIT_COMMANDS",
                    subkey="force_checkout",
                    commit=commit_hash,
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

                # Now perform the clone using PlatformService
                result = await PlatformService.run_command_async(
                    "GIT_COMMANDS",
                    subkey="clone",
                    repo_url=repo_url,
                    project_name=project_name,
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
