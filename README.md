# This project is intended to streamline some aspects of a Test-driven-development using Docker
## This project was built on Windows, but should have support for MacOS and Linux as well. Platform-specific commands can be modified in `config/commands.py`

## Requirements
- **Python 3.7+** (Python 3.8+ recommended)
- **No external dependencies** - Uses only Python standard library
- See `requirements.txt` for details

# Setup
### You can play around with the app with the example directory. It is using git submodules, so you will need to initialize and update them. Simply run `git submodule init`, `git submodule update`, and then `general_tools.py`. E.g. `python general_tools.py` after cloning.
1. Create a folder that will contain your dockerized projects.
2. Change the `config/settings.py.SOURCE_DIR` variable to be the path to this folder
3. Within this folder, create 4 new folders. One will be for the pre-edit version, one for the first post-edit version, one for the second post-edit version, and one for the correct version.
4. Within each of these folders, for each of your projects, create a new folder and pull the source git repository you want to be working on.
5. Add the required Docker files to each of the folders, as specified by the project.
6. Ensure `config/settings.py.FOLDER_ALIASES` maps correctly to the folders you created in step 3.
7. Run `general_tools.py`. E.g. `python general_tools.py`.
8. Expand directories that should be culled in `config/settings.py.IGNORE_DIRS`

# Designed workflow
### Get ready
1. Update the source git repository with the tests that will drive development down the chain.
2. Update the `run_tests.sh` script in each of the folders to use your new tests
3. Select your project from the dropdown in the GUI.
4. Use the Git View button on each version of your project to checkout to the correct commit.
### Pre-edits
1. Use the Docker button to build and run the tests on your pre-edit version.
2. Use the `Copy Test output` button to copy the output of your tests, and put them into the project.
3. Use the Archive button to create a .zip folder with the current state of the project. It will be located in the folder that you created the archive of.
4. Upload the new .zip file.
### Model Response 1
1. Apply the edits from the first model in the right post-edit version.
2. Use the Docker button to build and run the tests on the model's version.
3. Use the `Copy Test output` button to copy the output of your tests, and put them into the project.
4. Use the Archive button to create a .zip folder with the current state of the project. It will be located in the folder that you created the archive of.
5. Upload the new .zip file.
### Model Response 2
1. Apply the edits from the second model in the right post-edit version.
2. Use the Docker button to build and run the tests on the model's version.
3. Use the `Copy Test output` button to copy the output of your tests, and put them into the project.
4. Use the Archive button to create a .zip folder with the current state of the project. It will be located in the folder that you created the archive of.
5. Upload the new .zip file.
### Correct version
1. Make the correct edits (or pull from the correct commit, using the Git View button)
2. Use the Docker button to build and run the tests on the model's version.
3. Use the `Copy Test output` button to copy the output of your tests, and put them into the project.
4. Use the Archive button to create a .zip folder with the current state of the project. It will be located in the folder that you created the archive of.
5. Upload the new .zip file.

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