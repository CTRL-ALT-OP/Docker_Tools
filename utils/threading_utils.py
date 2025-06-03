"""
Threading utilities for the Project Control Panel
"""

import threading
from typing import Callable, Any


def run_in_thread(func: Callable, *args, **kwargs) -> threading.Thread:
    """Run a function in a separate daemon thread"""
    thread = threading.Thread(target=func, args=args, kwargs=kwargs)
    thread.daemon = True
    thread.start()
    return thread


def run_in_background(func: Callable) -> Callable:
    """Decorator to run a function in a background thread"""

    def wrapper(*args, **kwargs):
        return run_in_thread(func, *args, **kwargs)

    return wrapper
