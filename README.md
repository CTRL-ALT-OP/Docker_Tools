https://github.com/CTRL-ALT-OP/Docker_Tools

# This project is intended to streamline some aspects of a Test-driven-development using Docker
## This project was built on Windows, but should have support for MacOS and Linux as well. Platform-specific commands can be modified in `config/commands.py`

## Requirements
- **Python 3.7+** (Python 3.8+ recommended)
- See `requirements.txt` for details

# Setup
### You can play around with the app with the example directory. It is using git submodules, so you will need to initialize and update them. Simply run `git submodule init`, `git submodule update`, and then `general_tools.py`. E.g. `python general_tools.py` after cloning.
1. Create a folder that will contain your dockerized projects.
2. Add 4 subfolders, one for your pre-edit versions, one for your post-edit versions, one for your second post-edit versions, and one for your rewrite versions.
3. Change the `config/settings.py.SOURCE_DIR` variable to be the path to this folder (created in step 1)
4. Open the app (run `python general_tools.py`
5. Click add project, and paste in your Github URL
6. Use the dropdown menu to navigate to your new project if necessary
7. Click "Build Dockerfiles". This should create the necessary dockerfiles for your codebase.
8. Ensure `config/settings.py.FOLDER_ALIASES` maps correctly to the folders you created in step 3.
9. Expand directories/files that should be culled in `config/settings.py.IGNORE_DIRS` and `config/settings.py.IGNORE_FILES`

# Designed workflow
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

## config/settings.py

### Important configurations:
- `IGNORE_DIRS`: List of directories to delete during cleanup operations, and ignore during archiving.
- `FOLDER_ALIASES`: Dictionary of directories that have a specific alias. E.g. my source directory has folder names that are different than that of the project specifications, so this dictionary allows me to remap the folder names to the ones required by the project. Also determines the display order of versions.
- `SOURCE_DIR`: String that contains the path to the directory where your Dockerized projects live.

  

## config/commands.py

Contains all platform-specific commands used throughout the application. 
