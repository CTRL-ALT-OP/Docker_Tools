"""
Async utilities for the Project Control Panel - Improved Version
"""

import asyncio
import subprocess
import threading
import time
import weakref
import logging
from typing import Callable, Any, Optional, Tuple, Set
from concurrent.futures import ThreadPoolExecutor
import functools

# Set up logging
logger = logging.getLogger(__name__)

# Global thread pool executor for CPU-bound tasks
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="async_worker")


async def run_subprocess_async(
    cmd,
    shell: bool = False,
    capture_output: bool = True,
    text: bool = True,
    encoding: str = "utf-8",
    errors: str = "replace",
    cwd: Optional[str] = None,
    **kwargs,
) -> subprocess.CompletedProcess:
    """
    Run subprocess command asynchronously using thread pool
    """

    # Prepare subprocess.run call as a sync function
    def run_subprocess():
        return subprocess.run(
            cmd,
            shell=shell,
            capture_output=capture_output,
            text=text,
            encoding=encoding,
            errors=errors,
            cwd=cwd,
            **kwargs,
        )

    # Use run_in_executor which handles event loop properly
    return await run_in_executor(run_subprocess)


async def run_subprocess_streaming_async(
    cmd,
    shell: bool = False,
    text: bool = True,
    encoding: str = "utf-8",
    errors: str = "replace",
    cwd: Optional[str] = None,
    output_callback: Optional[Callable[[str], None]] = None,
    timeout: Optional[float] = None,
    **kwargs,
) -> Tuple[int, str]:
    """
    Run subprocess with streaming output asynchronously using thread pool
    Returns (return_code, full_output)
    """

    def run_subprocess_with_streaming():
        """Run subprocess in thread with streaming output"""
        try:
            # Prepare command
            if shell and isinstance(cmd, list):
                cmd_to_run = " ".join(cmd)
            elif not shell and isinstance(cmd, str):
                cmd_to_run = cmd.split()
            else:
                cmd_to_run = cmd

            # Prepare environment to force unbuffered output
            import os

            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"  # Force Python to unbuffer stdout/stderr
            env["PYTHONIOENCODING"] = "utf-8"  # Ensure proper encoding

            # Create subprocess with streaming - use unbuffered mode for real-time output
            if shell:
                process = subprocess.Popen(
                    cmd_to_run,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=text,
                    encoding=encoding,
                    errors=errors,
                    cwd=cwd,
                    bufsize=0,  # Unbuffered for real-time streaming
                    universal_newlines=True,
                    env=env,  # Pass modified environment
                )
            else:
                process = subprocess.Popen(
                    cmd_to_run,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=text,
                    encoding=encoding,
                    errors=errors,
                    cwd=cwd,
                    bufsize=0,  # Unbuffered for real-time streaming
                    universal_newlines=True,
                    env=env,  # Pass modified environment
                )

            full_output = ""
            buffer = ""  # Buffer to batch small chunks

            # Stream output in real-time with batched updates
            import select
            import time
            import sys

            while True:
                # Check if process is still running
                if process.poll() is not None:
                    # Process finished, read any remaining output
                    remaining = process.stdout.read()
                    if remaining:
                        full_output += remaining
                        buffer += remaining
                    # Send final buffer
                    if buffer and output_callback:
                        output_callback(buffer)
                    break

                # Read data in small chunks but batch for GUI updates
                try:
                    # Check if data is available without blocking
                    if sys.platform != "win32":
                        # On Unix systems, use select to check for available data
                        import select

                        ready, _, _ = select.select([process.stdout], [], [], 0.1)
                        if ready:
                            chunk = process.stdout.read(64)  # Read larger chunks
                            if chunk:
                                full_output += chunk
                                buffer += chunk

                                # Send buffer when we have enough data or encounter newlines
                                if len(buffer) > 100 or "\n" in buffer:
                                    if output_callback:
                                        output_callback(buffer)
                                    buffer = ""
                        else:
                            # No data available - send any pending buffer
                            if buffer and output_callback:
                                output_callback(buffer)
                                buffer = ""
                            time.sleep(0.1)  # Wait a bit longer if no data
                    else:
                        # On Windows, read line by line for better batching
                        try:
                            line = process.stdout.readline()
                            if line:
                                full_output += line
                                buffer += line

                                # Send buffer when we have a complete line or buffer is large
                                if "\n" in buffer or len(buffer) > 100:
                                    if output_callback:
                                        output_callback(buffer)
                                    buffer = ""
                            else:
                                # No data - send any pending buffer
                                if buffer and output_callback:
                                    output_callback(buffer)
                                    buffer = ""
                                time.sleep(0.1)
                        except Exception:
                            time.sleep(0.1)

                except Exception:
                    time.sleep(0.1)

            # Wait for process to complete
            return_code = process.wait()
            return return_code, full_output

        except Exception as e:
            logger.exception("Error in subprocess streaming")
            error_msg = f"Error in subprocess: {str(e)}\n"
            if output_callback:
                output_callback(error_msg)
            return 1, error_msg

    # Use run_in_executor which handles event loop properly
    return await run_in_executor(run_subprocess_with_streaming)


async def run_in_executor(func: Callable, *args, **kwargs) -> Any:
    """
    Run a synchronous function in the thread pool executor

    Raises:
        RuntimeError: If no event loop is running
    """
    try:
        # Get the currently running event loop - fail fast if none exists
        loop = asyncio.get_running_loop()
        bound_func = functools.partial(func, *args, **kwargs)
        return await loop.run_in_executor(_executor, bound_func)
    except RuntimeError as e:
        logger.error("No event loop available for run_in_executor")
        raise RuntimeError("No async event loop available") from e


class TkinterAsyncBridge:
    """
    Bridge for coordinating between async operations and tkinter GUI
    Provides proper synchronization primitives
    """

    def __init__(self, tkinter_root, task_manager=None):
        self.root = tkinter_root
        self.task_manager = task_manager
        self._sync_events = {}
        self._event_counter = 0

    def create_sync_event(self) -> Tuple[str, asyncio.Event]:
        """Create a new synchronization event for GUI coordination"""
        event_id = f"sync_event_{self._event_counter}"
        self._event_counter += 1

        # Create the event - but only if we have an active loop
        if (
            self.task_manager
            and self.task_manager._loop
            and not self.task_manager._loop.is_closed()
        ):
            try:
                # Create event in the target loop's context
                event = asyncio.Event()
                self._sync_events[event_id] = event
                return event_id, event
            except Exception as e:
                logger.error("Failed to create sync event: %s", e)
                # Return a dummy event that's already set
                dummy_event = asyncio.Event()
                dummy_event.set()
                return event_id, dummy_event
        else:
            logger.warning("Cannot create sync event - no active async loop")
            # Return a dummy event that's already set
            dummy_event = asyncio.Event()
            dummy_event.set()
            return event_id, dummy_event

    def signal_from_gui(self, event_id: str):
        """Signal an event from the GUI thread (thread-safe)"""
        if event_id in self._sync_events:
            event = self._sync_events[event_id]
            # Use the task manager's loop reference instead of trying to get running loop
            if self.task_manager and self.task_manager._loop:
                try:
                    self.task_manager._loop.call_soon_threadsafe(event.set)
                except RuntimeError as e:
                    logger.warning("Cannot signal event %s: %s", event_id, e)
            else:
                logger.warning(
                    "Cannot signal event %s - task manager loop not available", event_id
                )

    def cleanup_event(self, event_id: str):
        """Clean up a synchronization event"""
        self._sync_events.pop(event_id, None)


class ImprovedAsyncTaskManager:
    """
    Improved task manager for handling async tasks in a tkinter application
    - Better event loop management
    - Proper task lifecycle tracking
    - Enhanced error handling and logging
    """

    def __init__(self):
        self._tasks: Set[asyncio.Future] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._shutdown_requested = False
        self._loop_ready = threading.Event()  # Synchronization for loop startup

    def setup_event_loop(self):
        """Setup event loop in background thread with improved error handling"""
        if self._shutdown_requested or self._thread is not None:
            return

        def run_event_loop():
            """Run the event loop in a background thread"""
            try:
                # Create new event loop for this thread
                self._loop = asyncio.new_event_loop()

                # Set exception handler for better error reporting
                def handle_exception(loop, context):
                    exception = context.get("exception")
                    task = context.get("task")

                    if exception:
                        if isinstance(exception, asyncio.CancelledError):
                            logger.debug(
                                "Task cancelled: %s",
                                task.get_name() if task else "unknown",
                            )
                        else:
                            logger.error(
                                "Async task exception: %s",
                                exception,
                                exc_info=exception,
                            )
                    else:
                        logger.error(
                            "Async task error: %s", context.get("message", "Unknown")
                        )

                self._loop.set_exception_handler(handle_exception)

                # Signal that the loop is ready
                self._loop_ready.set()

                logger.info("Async event loop thread started")
                self._loop.run_forever()

            except Exception as e:
                logger.exception("Critical error in event loop thread")
                self._loop_ready.set()  # Signal even on error to prevent deadlock
            finally:
                # Clean up the loop
                if self._loop and not self._loop.is_closed():
                    try:
                        # Cancel any remaining tasks
                        pending = asyncio.all_tasks(self._loop)
                        if pending:
                            logger.info("Cancelling %d pending tasks", len(pending))
                            for task in pending:
                                task.cancel()

                        self._loop.close()
                    except Exception as e:
                        logger.error("Error during loop cleanup: %s", e)

                logger.info("Async event loop thread ended")

        # Start the event loop thread
        self._thread = threading.Thread(
            target=run_event_loop, daemon=True, name="AsyncEventLoop"
        )
        self._thread.start()

        # Wait for the loop to be ready (with timeout)
        if not self._loop_ready.wait(timeout=5.0):
            raise RuntimeError("Failed to start async event loop within timeout")

        if self._loop is None:
            raise RuntimeError("Failed to create async event loop")

        logger.info("Async event loop setup complete")

    def run_task(
        self, coro, callback: Optional[Callable] = None, task_name: Optional[str] = None
    ) -> asyncio.Future:
        """
        Run an async task in the background thread

        Args:
            coro: Coroutine to run
            callback: Optional callback function called with (result, error)
            task_name: Optional name for the task (for debugging)

        Returns:
            Future object representing the task

        Raises:
            RuntimeError: If task manager is shutting down or not set up
        """
        if self._shutdown_requested:
            raise RuntimeError("Task manager is shutting down")

        if not self._loop or self._loop.is_closed():
            self.setup_event_loop()

        if not self._loop or self._loop.is_closed():
            raise RuntimeError("Event loop is not available")

        try:
            # Create a named task for better debugging
            async def wrapped_coro():
                try:
                    return await coro
                except asyncio.CancelledError:
                    logger.debug("Task cancelled: %s", task_name or "unnamed")
                    raise
                except Exception as e:
                    logger.exception("Error in task %s: %s", task_name or "unnamed", e)
                    raise

            # Schedule the coroutine to run in the background loop
            future = asyncio.run_coroutine_threadsafe(wrapped_coro(), self._loop)
            self._tasks.add(future)

            # Set up cleanup and callback
            def cleanup_and_callback(completed_future):
                """Handle task completion with proper cleanup"""
                # Remove from tracking set
                self._tasks.discard(completed_future)

                # Call user callback if provided
                if callback:
                    try:
                        if completed_future.cancelled():
                            callback(None, asyncio.CancelledError("Task was cancelled"))
                        else:
                            result = completed_future.result()
                            callback(result, None)
                    except Exception as e:
                        logger.exception(
                            "Error in task callback for %s", task_name or "unnamed"
                        )
                        callback(None, e)

            future.add_done_callback(cleanup_and_callback)
            return future

        except Exception as e:
            logger.error(
                "Failed to create async task %s: %s", task_name or "unnamed", e
            )
            raise RuntimeError(f"Failed to schedule async task: {e}") from e

    def cancel_all_tasks(self, timeout: float = 5.0):
        """Cancel all running tasks with timeout"""
        if not self._tasks:
            return

        logger.info("Cancelling %d tasks", len(self._tasks))

        # Cancel all tasks
        cancelled_tasks = []
        for task in self._tasks.copy():
            if not task.done():
                task.cancel()
                cancelled_tasks.append(task)

        # Wait for cancellation to complete (with timeout)
        if cancelled_tasks:
            start_time = time.time()
            while cancelled_tasks and (time.time() - start_time) < timeout:
                cancelled_tasks = [task for task in cancelled_tasks if not task.done()]
                if cancelled_tasks:
                    time.sleep(0.1)

            if cancelled_tasks:
                logger.warning(
                    "%d tasks did not cancel within timeout", len(cancelled_tasks)
                )

        # Clear the set after cancellation
        self._tasks.clear()

    def get_task_count(self) -> int:
        """Get current number of tracked tasks"""
        # Clean up completed tasks first
        completed = {task for task in self._tasks if task.done()}
        self._tasks -= completed
        return len(self._tasks)

    def get_task_stats(self) -> dict:
        """Get detailed task statistics"""
        total = len(self._tasks)
        completed = sum(1 for task in self._tasks if task.done())
        running = total - completed

        return {"total": total, "running": running, "completed": completed}

    def shutdown(self, timeout: float = 5.0):
        """
        Shutdown the task manager with proper cleanup and timeout
        """
        logger.info("Shutting down async task manager")
        self._shutdown_requested = True

        # Cancel all running tasks with timeout
        self.cancel_all_tasks(
            timeout=timeout / 2
        )  # Use half timeout for task cancellation

        # Stop the event loop gracefully
        if self._loop and not self._loop.is_closed():
            try:
                # Schedule a graceful shutdown function to run in the loop
                def graceful_shutdown():
                    # Cancel any remaining tasks in the loop
                    try:
                        pending = asyncio.all_tasks(self._loop)
                        if pending:
                            logger.info(
                                "Cancelling %d remaining tasks in loop", len(pending)
                            )
                            for task in pending:
                                task.cancel()

                            # Wait a moment for cancellation to propagate
                            async def wait_for_cancellation():
                                try:
                                    await asyncio.gather(
                                        *pending, return_exceptions=True
                                    )
                                except Exception:
                                    pass  # Ignore exceptions from cancelled tasks
                                finally:
                                    self._loop.stop()

                            # Schedule the wait and then stop
                            asyncio.create_task(wait_for_cancellation())
                        else:
                            # No pending tasks, stop immediately
                            self._loop.stop()
                    except Exception as e:
                        logger.error("Error during graceful shutdown: %s", e)
                        self._loop.stop()

                # Schedule the graceful shutdown
                self._loop.call_soon_threadsafe(graceful_shutdown)

            except Exception as e:
                logger.error("Error scheduling graceful shutdown: %s", e)
                # Fallback to immediate stop
                try:
                    self._loop.call_soon_threadsafe(self._loop.stop)
                except Exception:
                    pass

        # Wait for thread to finish with timeout
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

            if self._thread.is_alive():
                logger.warning(
                    "Event loop thread did not shut down cleanly within %fs", timeout
                )

        # Clean up references
        self._loop = None
        self._thread = None
        self._loop_ready.clear()


# Global improved task manager instance
task_manager = ImprovedAsyncTaskManager()


class AsyncTaskGroup:
    """
    Context manager for grouping related async tasks with proper lifecycle management
    """

    def __init__(self, task_manager: ImprovedAsyncTaskManager, group_name: str = ""):
        self.task_manager = task_manager
        self.group_name = group_name
        self.tasks: Set[asyncio.Future] = set()
        self._cancelled = False

    def run_task(
        self, coro, callback=None, task_name: Optional[str] = None
    ) -> asyncio.Future:
        """Run a task within this group"""
        if self._cancelled:
            raise RuntimeError("Task group has been cancelled")

        full_task_name = (
            f"{self.group_name}.{task_name}"
            if self.group_name and task_name
            else task_name
        )
        future = self.task_manager.run_task(coro, callback, full_task_name)
        self.tasks.add(future)

        # Auto-remove completed tasks
        def cleanup_task(completed_future):
            self.tasks.discard(completed_future)

        future.add_done_callback(cleanup_task)
        return future

    def cancel_all(self):
        """Cancel all tasks in this group"""
        self._cancelled = True
        logger.debug(
            "Cancelling task group '%s' with %d tasks", self.group_name, len(self.tasks)
        )

        for task in self.tasks.copy():
            if not task.done():
                task.cancel()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cancel all tasks created in this group"""
        self.cancel_all()
        self.tasks.clear()


class AsyncResourceManager:
    """Improved async context manager for better resource management"""

    def __init__(self, resource_name: str, log_timing: bool = True):
        self.resource_name = resource_name
        self.start_time = None
        self.log_timing = log_timing

    async def __aenter__(self):
        self.start_time = time.time()
        if self.log_timing:
            logger.debug("Starting async operation: %s", self.resource_name)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        elapsed = time.time() - self.start_time if self.start_time else 0

        if exc_type is asyncio.CancelledError:
            if self.log_timing:
                logger.info(
                    "Async operation cancelled: %s (%.2fs)", self.resource_name, elapsed
                )
        elif exc_type:
            logger.error(
                "Async operation failed: %s (%.2fs) - %s",
                self.resource_name,
                elapsed,
                exc_val,
            )
        else:
            if self.log_timing:
                logger.debug(
                    "Async operation completed: %s (%.2fs)", self.resource_name, elapsed
                )

        # Don't suppress exceptions
        return False


def shutdown_all(timeout: float = 5.0):
    """Shutdown all async resources with timeout"""
    logger.info("Shutting down all async resources")
    task_manager.shutdown(timeout=timeout)
    _executor.shutdown(wait=False)  # Don't wait for threads to finish
