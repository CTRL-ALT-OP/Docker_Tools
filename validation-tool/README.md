# Raven Unit Tests - Codebase Validation Tool

A comprehensive tool for validating and testing Raven Unit Tests codebases using Docker containers. This tool is designed to validate different versions of codebases (preedit, postedit-beetle, postedit-sonnet, and rewrite) by building Docker images and running the tests.

## Features

- **Automated Docker Build & Test**: Builds Docker images and runs tests for each codebase
- **Comprehensive Reporting**: Generates detailed CSV reports with build/test results
- **Codebase Comparison**: Compares different versions and detects identical codebases
- **Unique Validation ID**: Generates unique IDs for validation sessions
- **Smart Warnings**: Detects common issues like identical codebases or missing changes
- **Automatic Cleanup**: Removes temporary files and Docker images after validation
- **Cross-Platform**: Supports both Windows and Unix/Mac environments

## Prerequisites

- **Docker**: Must be installed and running
- **Docker Compose**: Required for containerized validation
- **Operating System**: Windows, macOS, or Linux

## Quick Start

1. **Download the validation tool** (this ZIP file)
2. **Extract** to a directory of your choice
3. **Create a `codebases` directory** and add your ZIP files:
   ```
   validation-tool/
   ├── codebases/
   │   ├── my-project-preedit.zip
   │   ├── my-project-postedit-beetle.zip
   │   ├── my-project-postedit-sonnet.zip
   │   └── my-project-rewrite.zip
   └── ...
   ```
4. **Run the validation**:
   - **Windows**: Double-click `run_validation.bat` or run in cmd/PowerShell
   - **Mac/Linux**: Run `./run_validation.sh` in terminal

## Usage

### Basic Validation (All Codebases)

**Windows:**
```cmd
run_validation.bat
```

**Mac/Linux:**
```bash
./run_validation.sh
```

### Validate Specific Codebase Types

**Windows:**
```cmd
run_validation.bat --preedit
run_validation.bat --postedit-beetle
run_validation.bat --postedit-sonnet
run_validation.bat --rewrite
```

**Mac/Linux:**
```bash
./run_validation.sh --preedit
./run_validation.sh --postedit-beetle
./run_validation.sh --postedit-sonnet
./run_validation.sh --rewrite
```

### Command Line Options

Both scripts support the same options:

- `--preedit` - Validate only preedit codebase
- `--postedit-beetle` - Validate only postedit-beetle codebase  
- `--postedit-sonnet` - Validate only postedit-sonnet codebase
- `--rewrite` - Validate only rewrite codebase
- `--platform` - Specify Docker platform (e.g., linux/amd64, linux/arm64) - auto-detected if not provided
- `--help` or `-h` - Show help message

## Codebase Structure Requirements

Each codebase ZIP file must contain these files in the root:

```
your-codebase.zip
├── build_docker.sh    # Script to build Docker image
├── run_tests.sh       # Script to run tests inside container
├── Dockerfile         # Docker configuration
└── [your code files] # Your application code
```

### Required Scripts

#### `build_docker.sh`
Must build a Docker image. The script receives two arguments:
1. Image name (e.g., "my-app")  
2. Platform (e.g., "linux/arm64" or "linux/amd64")

Example:
```bash
#!/bin/bash
DOCKER_TAG=${1:-my-app}
DOCKER_DEFAULT_PLATFORM=${2:-linux/amd64}

docker build --platform $DOCKER_DEFAULT_PLATFORM -t $DOCKER_TAG .
```

#### `run_tests.sh`
Must run your tests inside the container. Example:
```bash
#!/bin/bash
pytest tests/ -v
```

## Expected Codebase Types

Name your ZIP files to include these keywords:

- **preedit**: Original codebase with failing tests (e.g., `my-project-preedit.zip`)
- **postedit-beetle**: Codebase edited with Beetle AI (e.g., `my-project-postedit-beetle.zip`)
- **postedit-sonnet**: Codebase edited with Sonnet AI (e.g., `my-project-postedit-sonnet.zip`)
- **rewrite**: Manually rewritten codebase (e.g., `my-project-rewrite.zip`)

## Output

### Console Output
```
===========================================
   Codebase Validation Tool
===========================================

✅ Found 4 ZIP file(s) to validate

Starting validation process...
   - Codebases directory: ./codebases
   - Output directory: ./output
   - Results file: ./output/validation_results.csv

⏳ Building image and running Docker containers and tests...

============================================================
CODEBASE VALIDATION SUMMARY
============================================================
Total: 4 | Build: 4/4 | Tests: 3/4
============================================================
✓ Build | ✗ Tests (2.3s) - my-project-preedit
✓ Build | ✓ Tests (1.8s) - my-project-postedit-beetle
✓ Build | ✓ Tests (1.9s) - my-project-postedit-sonnet
✓ Build | ✓ Tests (2.1s) - my-project-rewrite
============================================================

╔════════════════════════════════════════════════════════════════════════════╗
║                                                                            ║
║                           VALIDATION COMPLETE                             ║
║                                                                            ║
║  📋 Your Unique Validation ID (copy this):                                ║
║                                                                            ║
║      a1b2c3d4e5f6g7h8                                                     ║
║                                                                            ║
║  ⚠️  IMPORTANT: Save this ID! You'll need it for submission.              ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝

✅ Validation completed successfully!
Results saved to: output/validation_results.csv
```

### CSV Results

Detailed results are saved in `output/validation_results.csv` with columns:
- `unique_validation_id` - Your unique validation identifier
- `codebase_name` - Name of each codebase  
- `build_success` - Whether Docker build succeeded
- `test_success` - Whether tests passed
- `test_execution_time` - Time taken to run tests
- `differs_from_*` - Comparison results between codebases
- `build_output`/`test_output` - Detailed logs
- And more...

## Warning Messages

The tool detects common issues and shows warnings:

### ⚠️ Automatic Warnings

- **All tests passing in preedit**: Your preedit should have some failing tests
- **Failing tests in rewrite**: Your rewrite should have all tests passing
- **Identical postedit codebases**: You may have uploaded the same codebase twice
- **Preedit identical to other codebases**: You may have forgotten to apply changes
- **Build failures**: Issues with Docker builds that need fixing

## Troubleshooting

### "Docker is not running" Error
```bash
# Check Docker status
docker --version
docker info

# Start Docker
# Windows: Start Docker Desktop
# Mac: Open Docker Desktop app
# Linux: sudo systemctl start docker
```

### "No ZIP files found" Error
- Ensure you have created a `codebases/` directory
- Place your codebase ZIP files inside the `codebases/` directory
- ZIP files must have `.zip` extension

### Build Failures
- Check that your `Dockerfile` is valid
- Ensure `build_docker.sh` script works locally
- Review build output in the CSV results file

### Platform/Architecture Errors
If you get errors about platform mismatches (e.g., "should be linux/amd64 but running linux/arm64"):

**Automatic Fix (Recommended)**:
The tool automatically detects your platform and passes it to your `build_docker.sh` script as the second argument.

**Manual Override**:
```bash
# For Intel/AMD processors
./run_validation.sh --platform linux/amd64

# For Apple Silicon (M1/M2) or ARM processors  
./run_validation.sh --platform linux/arm64

# Windows
run_validation.bat --platform linux/amd64
```

**Note**: Your `build_docker.sh` script should accept the platform as the second argument:
```bash
DOCKER_TAG=${1:-my-app}
DOCKER_DEFAULT_PLATFORM=${2:-linux/amd64}
docker build --platform $DOCKER_DEFAULT_PLATFORM -t $DOCKER_TAG .
```

### Test Failures  
- Verify `run_tests.sh` script runs correctly
- Test your Docker image locally: `docker run --rm your-image ./run_tests.sh`
- Check test output in CSV for specific errors

### Permission Issues (Mac/Linux)
```bash
# Make run script executable
chmod +x run_validation.sh

# If ZIP extraction has permission issues
find codebases/ -name "*.sh" -exec chmod +x {} \;
```

## File Structure

```
validation-tool/
├── run_validation.sh          # Unix/Mac runner script  
├── run_validation.bat         # Windows runner script
├── docker-compose.yml         # Docker Compose configuration
├── Dockerfile                 # Validation container setup
├── validate_codebases.py      # Core validation logic (internal)
├── README.md                  # This file
├── codebases/                 # Your ZIP files go here
│   ├── project-preedit.zip
│   ├── project-postedit-beetle.zip  
│   ├── project-postedit-sonnet.zip
│   └── project-rewrite.zip
└── output/                    # Generated after validation
    └── validation_results.csv
```

## Advanced Usage

### Debug Mode (Python Direct)
For debugging only, you can run the Python script directly:
```bash
python validate_codebases.py --verbose
```

**Note**: This is not the recommended approach for normal validation.

### Docker Compose Details
The validation runs in isolated containers using Docker Compose:
- Mounts your `codebases/` directory as read-only
- Creates `output/` directory for results
- Uses Docker-in-Docker to build and test your codebases
- Automatically cleans up temporary containers

## Important Notes

1. **Save your Validation ID** - You'll need it for submission
2. **Keep the CSV file** - Contains detailed results and logs
3. **Check warnings** - Address any issues before submitting
4. **Test locally first** - Ensure your codebases build and run correctly

## Support

If you encounter issues:
1. Check the troubleshooting section above
2. Review the CSV output file for detailed error messages
3. Ensure Docker is running and accessible
4. Verify your codebase ZIP files contain all required files 