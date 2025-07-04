"""
Configuration for platform-specific commands used in the Project Control Panel
"""

# Docker commands
DOCKER_COMMANDS = {
    "build_script": "./build_docker.sh {tag}",
    "run_tests": "docker run --rm {tag} ./run_tests.sh",
    "version": ["docker", "--version"],
    "info": ["docker", "info"],
    "images": ["docker", "images", "-q", "{image_name}"],
    "run": ["docker", "run", "--rm", "{image_name}"],
    "rmi": ["docker", "rmi", "{image_name}"],
    "compose_up": ["docker", "compose", "up", "--build"],
}

# Git commands
GIT_COMMANDS = {
    "version": ["git", "--version"],
    "rev_parse_git_dir": ["git", "rev-parse", "--git-dir"],
    "rev_parse_head": ["git", "rev-parse", "HEAD"],
    "branch_show_current": ["git", "branch", "--show-current"],
    "status_porcelain": ["git", "status", "--porcelain"],
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

# File opening commands by platform
FILE_OPEN_COMMANDS = {
    "windows": ["start", "{file_path}"],
    "darwin": ["open", "{file_path}"],
    "linux": ["xdg-open", "{file_path}"],
}

# Test execution commands
TEST_COMMANDS = {
    "pytest": ["python", "-m", "pytest"],
    "pytest_verbose": ["python", "-m", "pytest", "-v"],
    "pytest_with_coverage": ["python", "-m", "pytest", "--cov"],
    "git_init": ["git", "init", "--quiet"],
}

# System information commands
SYSTEM_COMMANDS = {
    "docker_version": ["docker", "--version"],
    "pwd": {"windows": ["cd"], "unix": ["pwd"]},
}

# ======================================================================
# TEST COMMAND CONFIGURATIONS FOR MULTI-LANGUAGE SUPPORT
# ======================================================================

# Test command templates for different languages
TEST_COMMAND_TEMPLATES = {
    "python": "pytest -vv -s {test_paths}",
    "javascript": "npm test {test_paths}",
    "typescript": "npm run build && npm test {test_paths}",
    "java": "mvn test -Dtest={test_paths}",
    "rust": "cargo test {test_paths}",
    "c": "ctest --verbose -R {test_paths}",
}

# Default commands when no specific test paths are provided
DEFAULT_TEST_COMMANDS = {
    "python": "pytest -vv -s tests/",
    "javascript": "npm test",
    "typescript": "npm run build && npm test",
    "java": "mvn test",
    "rust": "cargo test",
    "c": "ctest --verbose",
    "cpp": "ctest --verbose",
    "csharp": "dotnet test",
    "go": "go test",
}

# Test file patterns for each language
TEST_FILE_PATTERNS = {
    "python": [("test_*.py", "*_test.py")],
    "javascript": [("*.test.js", "*.spec.js")],
    "typescript": [("*.test.ts", "*.spec.ts", "*.test.tsx", "*.spec.tsx")],
    "java": [("*Test.java", "*Tests.java")],
    "rust": [("*_test.rs", "test_*.rs")],
    "c": [("test_*.c", "*_test.c", "test_*.cpp", "*_test.cpp")],
    "cpp": [("test_*.c", "*_test.c", "test_*.cpp", "*_test.cpp")],
    "csharp": [("*Test.cs", "*Tests.cs")],
    "go": [("*_test.go",)],
}

# Test directories for each language
TEST_DIRECTORIES = {
    "python": ["tests/"],
    "javascript": ["tests/", "test/", "__tests__/", "src/"],
    "typescript": ["tests/", "test/", "__tests__/", "src/"],
    "java": ["src/test/java/", "test/"],
    "rust": ["tests/", "src/"],
    "c": ["tests/", "test/"],
    "cpp": ["tests/", "test/"],
    "csharp": ["tests/", "test/"],
    "go": ["./"],  # Go tests are typically in the same directory
}

# Command patterns for detecting test commands in run_tests.sh files
TEST_COMMAND_PATTERNS = {
    "python": ["pytest"],
    "javascript": ["npm test"],
    "typescript": ["npm run build", "npm test"],
    "java": ["mvn", "test"],
    "rust": ["cargo test"],
    "c": ["ctest"],
    "cpp": ["ctest"],
    "csharp": ["dotnet test"],
    "go": ["go test"],
}

# Language aliases (alternative names for languages)
LANGUAGE_ALIASES = {
    "js": "javascript",
    "ts": "typescript",
    "py": "python",
    "rs": "rust",
    "cs": "csharp",
    "c++": "cpp",
    "cxx": "cpp",
}
