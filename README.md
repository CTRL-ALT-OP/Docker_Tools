# Docker Tools - Advanced Test-Driven Development Control Panel

**A sophisticated GUI-based project management tool designed to streamline Test-Driven Development workflows using Docker containers.**

https://github.com/CTRL-ALT-OP/Docker_Tools

## Overview

Docker Tools provides a comprehensive solution for managing multiple versions of dockerized projects throughout the development lifecycle. Built with a modern async architecture and intuitive GUI, it automates the tedious aspects of TDD workflows while maintaining full control over your development process.

### Key Features

- **Multi-Version Project Management**: Seamlessly manage 4 project versions (pre-edit, post-edit, post-edit2, correct-edit)
- **Automated Docker Integration**: One-click Docker building and testing across all project versions
- **Advanced Git Operations**: Commit viewing, branch management, and checkout operations
- **Async Architecture**: Modern async/await implementation for responsive background operations
- **Multi-Language Support**: Python, JavaScript, TypeScript, Java, Rust, C, Go, C++, C#
- **Project Archiving**: Automated ZIP archive creation with intelligent file filtering
- **Test Synchronization**: Sync and edit test scripts across project versions
- **Validation Framework**: Comprehensive project group compliance validation
- **File Monitoring**: Real-time file system monitoring for project changes

## This project was built on Windows, but should have support for MacOS and Linux as well. Platform-specific commands can be modified in `config/commands.py`

## Requirements

- **Python 3.7+** (Python 3.8+ recommended for full async support)
- **Docker**: Required for containerized testing
- **Git**: Required for version control operations
- See `requirements.txt` for complete dependency details

## Quick Start

### Option 1: Try with Example Projects

You can immediately explore the app using the included example directory with git submodules:

```bash
git clone https://github.com/CTRL-ALT-OP/Docker_Tools.git
cd Docker_Tools
git submodule init
git submodule update
pip install -r requirements.txt
python general_tools.py
```

### Option 2: Set Up Your Own Projects

1. Create a folder that will contain your dockerized projects.
2. Add 4 subfolders, one for your pre-edit versions, one for your post-edit versions, one for your second post-edit versions, and one for your rewrite versions.
3. Change the SOURCE_DIR setting using the settings menu to the new folder (created in step 1)
4. Open the app (run `python general_tools.py`
5. Click add project, and paste in your Github URL
6. Use the dropdown menu to navigate to your new project if necessary
7. Click "Build Dockerfiles". This should create the necessary dockerfiles for your codebase.
8. Ensure `config/settings.py.FOLDER_ALIASES` maps correctly to the folders you created in step 3.
9. Expand directories/files that should be culled in `config/settings.py.IGNORE_DIRS` and `config/settings.py.IGNORE_FILES`

## Project Structure

Your source directory should follow this structure:
```
your_source_directory/
├── pre-edit/          # Original project versions
├── post-edit/         # First model edits
├── post-edit2/        # Second model edits
└── correct-edit/      # Final correct versions
```

Each subdirectory can contain multiple projects that will be automatically grouped together by name.

## Configuration

### config/settings.py

The main configuration file contains several important settings:

#### Core Settings
- **`SOURCE_DIR`**: Absolute path to your project directory (MUST be configured)
- **`FOLDER_ALIASES`**: Maps folder names to project workflow stages
- **`IGNORE_DIRS`**: Directories excluded from cleanup and archiving operations
- **`IGNORE_FILES`**: Files excluded from cleanup and archiving operations

#### Language Support
- **`LANGUAGE_EXTENSIONS`**: File extensions for automatic language detection
- **`LANGUAGE_REQUIRED_FILES`**: Required dependency files per language

#### GUI Customization
- **`COLORS`**: Complete color scheme for the interface
- **`FONTS`**: Typography settings for all UI elements
- **`BUTTON_STYLES`**: Visual styling for different button types

### config/commands.py

Contains all platform-specific commands used throughout the application. Modify these for your specific platform requirements.

## Architecture

### Async Architecture
The application uses a modern async/await architecture with:
- **AsyncTaskManager**: Centralized task execution and monitoring
- **TkinterAsyncBridge**: Seamless integration between async operations and GUI
- **Background Processing**: Non-blocking operations for better user experience

### Modular Design
- **Services**: Core business logic (Docker, Git, File operations, etc.)
- **GUI**: Tkinter-based interface components
- **Utils**: Shared utilities and async helpers
- **Models**: Data structures and project representations

### Testing Framework
Comprehensive testing setup with:
- **pytest**: Core testing framework with async support
- **Coverage reporting**: Detailed code coverage analysis
- **Multiple test types**: Unit, integration, GUI, and platform-specific tests
- **Performance benchmarking**: Built-in performance testing capabilities

## Designed workflow
### Get ready
1. Update the source git repository with the tests that will drive development down the chain.
2. Select your project from the dropdown in the GUI.
3. Update the `run_tests.sh` script using the button and popup window.
4. Use the Git Checkout all or Git view buttons to checkout to the correct commit.
### Pre-edits
1. Use the Docker button to build and run the tests on your pre-edit version.
2. Use the Archive button to create a .zip folder with the current state of the project. It will be located in the folder that you created the archive of.
3. Upload the new .zip file.
### Model Response 1
1. Apply the edits from the first model in the right post-edit version.
2. Use the Docker button to build and run the tests on the model's version.
3. Use the Archive button to create a .zip folder with the current state of the project. It will be located in the folder that you created the archive of.
4. Upload the new .zip file.
### Model Response 2
1. Apply the edits from the second model in the right post-edit version.
2. Use the Docker button to build and run the tests on the model's version.
3. Use the Archive button to create a .zip folder with the current state of the project. It will be located in the folder that you created the archive of.
4. Upload the new .zip file.
### Correct version
1. Make the correct edits (or pull from the correct commit, using the Git View button)
2. Use the Docker button to build and run the tests on the model's version.
3. Use the Archive button to create a .zip folder with the current state of the project. It will be located in the folder that you created the archive of.
4. Upload the new .zip file.

### Validate codebases
Click validate all to check the compliance of your codebases. Note that the new GUI validator can be finicky.

## Using the GUI
- **Project Selection**: Use the dropdown to select which project to work on. Projects with the same name across different folders are automatically grouped together.
- **Version Display**: All versions of the selected project are displayed in order (pre-edit → post-edit → post-edit2 → correct-edit).
- **Refresh**: Use the refresh button to reload projects if you've added new ones or made changes to the folder structure.
- **Settings**: Use the settings button (⚙️) to customize application appearance, behavior, and configuration.

## Settings System

The application features a comprehensive settings system that allows you to customize every aspect of the interface and behavior without modifying the original configuration files.

### How It Works

The settings system uses a two-tier approach:
1. **Default Settings** (`config/settings.py`) - Original settings tracked by Git
2. **User Overrides** (`config/user_settings.json`) - Personal customizations NOT tracked by Git

When the application starts, it loads the default settings first, then applies any user customizations on top. This ensures your personal preferences are preserved while keeping the original configuration intact for Git operations.

### Accessing Settings

Click the **⚙️ Settings** button in the main toolbar to open the settings window. The settings are organized into four tabs:

#### General Tab
- **Source Directory**: Main directory where projects are located (with browse button)
- **Window Settings**: Application title and window sizes

#### Appearance Tab  
- **Colors**: Complete color scheme with live preview
- **Fonts**: Typography settings for all UI elements

#### Directories Tab
- **Ignore Directories**: Folders excluded from cleanup operations  
- **Ignore Files**: Files excluded from cleanup operations
- **Folder Aliases**: Custom names for project workflow stages

#### Languages Tab
- **Language Extensions**: File extensions for automatic language detection
- **Required Files**: Dependency files required for each programming language

### Settings Management

- **Apply and Restart**: Saves your changes and restarts the application with new settings
- **Reset to Defaults**: Removes all customizations and restores original settings  
- **Cancel**: Closes the settings without saving changes

### Technical Details

- Only changed settings are saved (efficient storage)
- User settings file is automatically excluded from Git
- Settings are validated before applying
- Safe restart mechanism preserves your work
- Automatic backup of original configuration

## Troubleshooting

### Common Issues

**"No projects found"**: Ensure your `SOURCE_DIR` is correctly set and contains the required folder structure.

**Docker build failures**: Verify Docker is running and your projects contain valid Dockerfiles.

**Git operations fail**: Ensure Git is installed and your projects are valid Git repositories.

**Async operation errors**: For Python < 3.8, ensure all async dependencies are properly installed.

### Performance Tips

- Use the async operations for better responsiveness
- Archive projects regularly to manage disk space
- Configure `IGNORE_DIRS` to exclude unnecessary files from operations
- Monitor the task statistics in the application logs

## Advanced Features

### Custom Validation
The validation service can be extended to check project-specific compliance rules.

### Docker File Generation
Automatic Dockerfile generation based on detected project languages and dependencies.

### File Monitoring
Real-time monitoring of project files with automatic refresh capabilities.

### Background Task Management
Advanced task scheduling and monitoring with detailed statistics and timeout handling.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass: `pytest`
5. Submit a pull request
