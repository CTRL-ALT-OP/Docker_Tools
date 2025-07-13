import threading


class WebTerminalBuffer:
    def __init__(self):
        self._output = ""
        self._lock = threading.Lock()

    def append(self, text):
        with self._lock:
            self._output += text
            # Limit buffer size to last 50KB
            if len(self._output) > 50000:
                self._output = self._output[-50000:]

    def get(self):
        with self._lock:
            return self._output

    def clear(self):
        with self._lock:
            self._output = ""


# Singleton instance
web_terminal_buffer = WebTerminalBuffer()
