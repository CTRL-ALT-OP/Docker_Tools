# Codebase Validator

A simple web interface for validating codebases with Docker builds and tests.

## Quick Start 🚀

**Linux/macOS:**
```bash
./run.sh
```

**Windows:**
```cmd
run.bat
```

Then open http://localhost:8080

## Better Workflow 🔄

**Keep it running while you work!** 

Instead of the old CLI-only script that required manual file preparation and was slower, you now have a persistent web interface that stays open alongside your development work. Simply:

1. **Start once**: Run the script above and leave the website open in your browser
2. **Work normally**: Continue coding on your project 
3. **Test instantly**: When ready to validate, just zip your project and drag-drop it into the web interface
4. **Get results fast**: View validation results immediately in your browser, with downloadable CSV reports

**Why this is better than the old approach:**
- ⚡ **Faster**: No need to restart validation environment each time
- 🖱️ **Easier**: Web interface instead of command-line only
- 📁 **Simpler**: Just upload a ZIP - no manual file copying required
- 👀 **Visual**: See results in browser with better formatting
- 🔄 **Iterative**: Keep testing different versions quickly

### How it works:
- **True Docker-in-Docker**: Completely isolated and secure validation environment
- **Perfect for project validation**: Safe to run untrusted/external code
- **Cross-platform**: Works identically on Windows, Mac, and Linux

## Usage

1. **Upload**: Drag and drop your ZIP file or click to browse
2. **Wait**: The system will extract, build, and test automatically
3. **Results**: View the validation results and download CSV report

## Requirements

- Docker Desktop
- ZIP file containing `build_docker.sh` and `run_tests.sh`

### Platform Support

**Universal Docker-based validation:**
- **Windows**: Docker Desktop
- **macOS**: Docker Desktop (including Apple Silicon)
- **Linux**: Docker Engine or Docker Desktop

### Features

- **Secure Isolation**: Each validation runs in a completely isolated Docker environment
- **Cross-platform**: Identical behavior across all operating systems
- **Zero Configuration**: No local Python setup required
- **Safe Execution**: Untrusted code cannot affect your host system

## Command Line

You can also use the validator directly:
```bash
python validator.py your_codebase.zip [output.csv]
``` 