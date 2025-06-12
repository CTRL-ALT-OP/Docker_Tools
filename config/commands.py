"""
Configuration for platform-specific commands used in the Project Control Panel
"""

# Docker commands
DOCKER_COMMANDS = {
    "build_script": "./build_docker.sh {tag}",
    "run_tests": "docker run --rm {tag} ./run_tests.sh",
}

# Git commands
GIT_COMMANDS = {
    "log": [
        "git",
        "log",
        "--oneline",
        "--pretty=format:%h|%an|%ad|%s",
        "--date=short",
        "--all",
    ],
    "checkout": ["git", "checkout", "{commit}"],
    "force_checkout": ["git", "checkout", "--force", "{commit}"],
    "reset_hard": ["git", "reset", "--hard", "HEAD"],
    "clean": ["git", "clean", "-fd"],
    "remote_check": ["git", "remote"],
    "fetch": ["git", "fetch", "--all"],
    "clone": ["git", "clone", "{repo_url}", "{project_name}"],
}

# Archive commands by platform
ARCHIVE_COMMANDS = {
    "windows": {
        "powershell": "Compress-Archive -Path ./* -DestinationPath ./{archive_name} -Force",
        "cmd": [
            "powershell",
            "-Command",
            "Compress-Archive -Path ./* -DestinationPath ./{archive_name} -Force",
        ],
    },
    "linux": {
        "zip": ["zip", "-r", "{archive_name}", ".", "-x", "{archive_name}"],
    },
    "darwin": {  # macOS
        "zip": ["zip", "-r", "{archive_name}", ".", "-x", "{archive_name}"],
    },
}

# Bash executable paths for Windows
BASH_PATHS = {
    "windows": [
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files (x86)\Git\bin\bash.exe",
        r"C:\Git\bin\bash.exe",
    ],
}

# Default shell commands
SHELL_COMMANDS = {
    "bash": "bash",
    "powershell": "powershell",
    "cmd": "cmd",
}

# Error messages by platform
ERROR_MESSAGES = {
    "windows": {
        "bash_not_found": "NOTE: Make sure Git for Windows is installed and accessible.",
        "powershell_failed": "NOTE: PowerShell command failed. Make sure PowerShell is available.",
    },
    "linux": {
        "bash_not_found": "NOTE: Make sure bash is available in your PATH.",
        "zip_not_found": "NOTE: Make sure zip is installed on your system.",
    },
    "darwin": {
        "bash_not_found": "NOTE: Make sure bash is available in your PATH.",
        "zip_not_found": "NOTE: Make sure zip is installed on your system.",
    },
}

# Command templates for string formatting
COMMAND_TEMPLATES = {
    "docker_build": "./build_docker.sh {tag}",
    "docker_test": "docker run --rm {tag} ./run_tests.sh",
    "git_checkout": "git checkout {commit}",
    "bash_execute": 'bash -c "{command}"',
    "powershell_execute": 'powershell -Command "{command}"',
}
