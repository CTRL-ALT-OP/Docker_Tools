"""
Standardized Async Base Classes and Patterns
Provides consistent async interfaces and result handling across all services
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, TypeVar, Optional, Dict, Any, Callable
from contextlib import asynccontextmanager

# Set up logging
logger = logging.getLogger(__name__)

# Generic type for async results
T = TypeVar("T")


@dataclass
class AsyncResult(Generic[T]):
    """Standardized result wrapper for all async operations"""

    success: bool
    data: Optional[T] = None
    error: Optional["AsyncError"] = None
    message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def success_result(
        cls, data: T, message: str = None, metadata: Dict[str, Any] = None
    ) -> "AsyncResult[T]":
        """Create a successful result"""
        return cls(success=True, data=data, message=message, metadata=metadata)

    @classmethod
    def error_result(
        cls, error: "AsyncError", metadata: Dict[str, Any] = None
    ) -> "AsyncResult[T]":
        """Create an error result"""
        return cls(success=False, error=error, metadata=metadata)

    # Backward compatibility aliases for existing services
    @classmethod
    def success(
        cls, data: T, message: str = None, metadata: Dict[str, Any] = None
    ) -> "AsyncResult[T]":
        """Backward compatibility alias for success_result"""
        return cls.success_result(data, message, metadata)

    @classmethod
    def error(
        cls, error: "AsyncError", metadata: Dict[str, Any] = None
    ) -> "AsyncResult[T]":
        """Backward compatibility alias for error_result"""
        return cls.error_result(error, metadata)

    @classmethod
    def partial(
        cls,
        data: T,
        error: "AsyncError",
        message: str = None,
        metadata: Dict[str, Any] = None,
    ) -> "AsyncResult[T]":
        """Backward compatibility alias for partial_result"""
        return cls.partial_result(data, error, message, metadata)

    @classmethod
    def partial_result(
        cls,
        data: T,
        error: "AsyncError",
        message: str = None,
        metadata: Dict[str, Any] = None,
    ) -> "AsyncResult[T]":
        """Create a partial success result (operation completed but with issues)"""
        result = cls(
            success=True, data=data, error=error, message=message, metadata=metadata
        )
        result._is_partial = True
        return result

    @property
    def is_success(self) -> bool:
        """Check if operation was successful"""
        return self.success and not hasattr(self, "_is_partial")

    @property
    def is_error(self) -> bool:
        """Check if operation failed"""
        return not self.success

    @property
    def is_partial(self) -> bool:
        """Check if operation partially succeeded"""
        return hasattr(self, "_is_partial") and getattr(self, "_is_partial", False)


# Alias for backward compatibility with services
ServiceResult = AsyncResult


class AsyncError(Exception):
    """Base class for async operation errors"""

    def __init__(
        self, message: str, error_code: str = None, details: Dict[str, Any] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "UNKNOWN_ERROR"
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary format"""
        return {
            "message": self.message,
            "error_code": self.error_code,
            "details": self.details,
            "type": self.__class__.__name__,
        }


class ValidationError(AsyncError):
    """Error for input validation failures"""

    def __init__(self, message: str, field: str = None):
        super().__init__(message, "VALIDATION_ERROR", {"field": field} if field else {})


class ProcessError(AsyncError):
    """Error for process execution failures"""

    def __init__(
        self,
        message: str,
        return_code: int = None,
        stdout: str = None,
        stderr: str = None,
        error_code: str = None,
    ):
        details = {}
        if return_code is not None:
            details["return_code"] = return_code
        if stdout:
            details["stdout"] = stdout
        if stderr:
            details["stderr"] = stderr

        super().__init__(message, error_code or "PROCESS_ERROR", details)
        self.return_code = return_code
        self.stdout = stdout
        self.stderr = stderr


class ResourceError(AsyncError):
    """Error for resource access failures"""

    def __init__(self, message: str, resource_path: str = None):
        super().__init__(
            message,
            "RESOURCE_ERROR",
            {"resource_path": resource_path} if resource_path else {},
        )


class AsyncServiceContext:
    """Context manager for service operations with timing and logging"""

    def __init__(self, service_name: str, operation_name: str, timeout: float = None):
        self.service_name = service_name
        self.operation_name = operation_name
        self.timeout = timeout
        self.start_time = None
        self.logger = logging.getLogger(f"{service_name}.{operation_name}")

    async def __aenter__(self):
        self.start_time = time.time()
        self.logger.debug(f"Starting {self.operation_name}")

        if self.timeout:
            # Set up timeout for the operation
            self._timeout_task = asyncio.create_task(asyncio.sleep(self.timeout))

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time if self.start_time else 0

        if hasattr(self, "_timeout_task"):
            self._timeout_task.cancel()

        if exc_type is None:
            self.logger.debug(f"Completed {self.operation_name} in {duration:.2f}s")
        elif exc_type is asyncio.CancelledError:
            self.logger.info(f"Cancelled {self.operation_name} after {duration:.2f}s")
        else:
            self.logger.error(
                f"Failed {self.operation_name} after {duration:.2f}s: {exc_val}"
            )

        return False  # Don't suppress exceptions


class AsyncServiceInterface(ABC):
    """Base interface for all async services with standardized patterns"""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.logger = logging.getLogger(service_name)

    @asynccontextmanager
    async def operation_context(self, operation_name: str, timeout: float = None):
        """Create a context manager for service operations"""
        async with AsyncServiceContext(
            self.service_name, operation_name, timeout
        ) as ctx:
            yield ctx

    @abstractmethod
    async def health_check(self) -> AsyncResult[Dict[str, Any]]:
        """Check service health - must be implemented by all services"""
        pass


class AsyncCommand(ABC):
    """Base class for all async operations triggered from GUI"""

    def __init__(
        self,
        progress_callback: Callable[[str, str], None] = None,
        completion_callback: Callable[[AsyncResult], None] = None,
    ):
        self.progress_callback = progress_callback
        self.completion_callback = completion_callback
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    async def execute(self) -> AsyncResult:
        """Execute the command and return result"""
        pass

    async def run_with_progress(self) -> AsyncResult:
        """Template method with standard progress handling"""
        try:
            if self.progress_callback:
                self.progress_callback("Starting operation...", "info")

            result = await self.execute()

            if self.completion_callback:
                self.completion_callback(result)

            return result
        except Exception as e:
            self.logger.exception(f"Command {self.__class__.__name__} failed")
            error_result = AsyncResult.error_result(
                ProcessError(f"Command failed: {e}", error_code="COMMAND_ERROR")
            )
            if self.completion_callback:
                self.completion_callback(error_result)
            return error_result

    def _update_progress(self, message: str, level: str = "info"):
        """Helper method to update progress"""
        if self.progress_callback:
            self.progress_callback(message, level)


# Data classes for common result types
@dataclass
class CleanupScanResult:
    """Result of scanning for cleanup items"""

    directories: list
    files: list
    total_size: int
    item_count: int


@dataclass
class CleanupResult:
    """Result of cleanup operation"""

    deleted_directories: list
    deleted_files: list
    total_deleted_size: int
    failed_deletions: list


@dataclass
class ArchiveResult:
    """Result of archive operation"""

    archive_path: str
    original_size: int
    compressed_size: int
    compression_ratio: float


@dataclass
class GitRepositoryInfo:
    """Information about a git repository"""

    has_remote: bool
    remote_urls: list
    current_branch: str
    commit_count: int
    last_commit_date: str
    is_clean: bool


@dataclass
class FileSyncInfo:
    """Information about file synchronization"""

    file_path: str
    exists: bool
    size: int
    modified_time: str
    checksum: str


# Export main classes
__all__ = [
    "AsyncResult",
    "ServiceResult",
    "AsyncError",
    "ValidationError",
    "ProcessError",
    "ResourceError",
    "AsyncServiceInterface",
    "AsyncCommand",
    "AsyncServiceContext",
    "CleanupScanResult",
    "CleanupResult",
    "ArchiveResult",
    "GitRepositoryInfo",
    "FileSyncInfo",
]
