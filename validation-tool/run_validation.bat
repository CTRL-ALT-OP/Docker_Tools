@echo off
setlocal enabledelayedexpansion

REM Jump to main logic, skip function definitions
goto :main

:show_usage
echo Usage: %~nx0 [OPTIONS]
echo.
echo Options:
echo   --preedit           Validate only preedit codebase
echo   --postedit-beetle   Validate only postedit-beetle codebase
echo   --postedit-sonnet   Validate only postedit-sonnet codebase
echo   --rewrite           Validate only rewrite codebase
echo   --platform PLATFORM Docker platform (e.g., linux/amd64, linux/arm64)
echo   --version           Show version information
echo   --help, -h          Show this help message
echo.
echo If no option is specified, all codebases will be validated.
goto :eof

:run_docker_compose
set compose_args=%*

docker compose version >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo Using docker compose command...
    docker compose %compose_args%
    goto :eof
)

where docker-compose >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo Using docker-compose command...
    docker-compose %compose_args%
    goto :eof
)

echo ERROR: Neither 'docker compose' nor 'docker-compose' commands are available.
echo        Please install Docker Compose and try again.
pause
exit /b 1

:main
REM Parse command line arguments
set CODEBASE_FILTER=
set FILTER_TYPE=
set PLATFORM_ARG=

:parse_args
if "%~1"=="" goto :args_done
if "%~1"=="--preedit" (
    set CODEBASE_FILTER=--preedit
    set FILTER_TYPE=preedit
    shift
    goto :parse_args
)
if "%~1"=="--postedit-beetle" (
    set CODEBASE_FILTER=--postedit-beetle
    set FILTER_TYPE=postedit-beetle
    shift
    goto :parse_args
)
if "%~1"=="--postedit-sonnet" (
    set CODEBASE_FILTER=--postedit-sonnet
    set FILTER_TYPE=postedit-sonnet
    shift
    goto :parse_args
)
if "%~1"=="--rewrite" (
    set CODEBASE_FILTER=--rewrite
    set FILTER_TYPE=rewrite
    shift
    goto :parse_args
)
if "%~1"=="--platform" (
    if "%~2"=="" (
        echo ERROR: --platform requires a value (e.g., linux/amd64, linux/arm64)
        call :show_usage
        pause
        exit /b 1
    )
    set PLATFORM_ARG=--platform %~2
    shift
    shift
    goto :parse_args
)
if "%~1"=="--version" (
    echo Codebase Validation Tool v062325_0840
    pause
    exit /b 0
)
if "%~1"=="--help" (
    call :show_usage
    pause
    exit /b 0
)
if "%~1"=="-h" (
    call :show_usage
    pause
    exit /b 0
)
echo ERROR: Unknown option: %~1
call :show_usage
pause
exit /b 1

:args_done

echo ===========================================
echo    Codebase Validation Tool
echo ===========================================
echo.

if not "%FILTER_TYPE%"=="" (
    echo Validating only: %FILTER_TYPE%
    echo.
)

REM Check if Docker is running
docker info >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: Docker is not running. Please start Docker and try again.
    pause
    exit /b 1
)

REM Check if codebases directory exists
if not exist "codebases" (
    echo ERROR: Codebases directory not found. Please create a 'codebases' directory and add your ZIP files.
    pause
    exit /b 1
)

REM Count ZIP files
set zip_count=0
for %%f in (codebases\*.zip) do (
    set /a zip_count+=1
)

if %zip_count% equ 0 (
    echo ERROR: No ZIP files found in codebases directory.
    echo        Please add your codebase ZIP files to the 'codebases' directory.
    pause
    exit /b 1
)

echo Found %zip_count% ZIP file(s) to validate
echo.

REM Create output directory if it doesn't exist
if not exist "output" mkdir output

echo Starting validation process...
echo    - Codebases directory: ./codebases
echo    - Output directory: ./output
echo    - Results file: ./output/validation_results.csv
if not "%FILTER_TYPE%"=="" (
    echo    - Filter: %FILTER_TYPE% only
)
echo.

REM Build the Docker command with optional filter and platform
set DOCKER_CMD=python validate_codebases.py --output /app/output/validation_results.csv --verbose
if not "%CODEBASE_FILTER%"=="" (
    set DOCKER_CMD=%DOCKER_CMD% %CODEBASE_FILTER%
)
if not "%PLATFORM_ARG%"=="" (
    set DOCKER_CMD=%DOCKER_CMD% %PLATFORM_ARG%
)

REM Run the validation with real-time output
echo Building image and running Docker containers and tests...
if not "%CODEBASE_FILTER%"=="" (
    REM Build the image first, then use the regular validator service with custom command
    call :run_docker_compose build validator
    call :run_docker_compose run --rm validator %DOCKER_CMD%
) else if not "%PLATFORM_ARG%"=="" (
    REM Build the image first, then use the regular validator service with custom command
    call :run_docker_compose build validator
    call :run_docker_compose run --rm validator %DOCKER_CMD%
) else (
    REM Use the regular service for default validation
    call :run_docker_compose up --build validator
)

REM Check if results were generated
if exist "output\validation_results.csv" (
    echo.
    echo Validation completed successfully!
    echo Results saved to: output\validation_results.csv
) else (
    echo.
    echo ERROR: Validation failed - no results file generated
    pause
    exit /b 1
)

REM Keep window open when done
echo.
echo Press any key to close this window...
pause