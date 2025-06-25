#!/bin/bash
set -e

show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --preedit           Validate only preedit codebase"
    echo "  --postedit-beetle   Validate only postedit-beetle codebase"
    echo "  --postedit-sonnet   Validate only postedit-sonnet codebase"
    echo "  --rewrite           Validate only rewrite codebase"
    echo "  --platform PLATFORM Docker platform (e.g., linux/amd64, linux/arm64)"
    echo "  --version           Show version information"
    echo "  --help, -h          Show this help message"
    echo ""
    echo "If no option is specified, all codebases will be validated."
}

run_docker_compose() {
    local compose_args="$@"
    
    if docker compose version >/dev/null 2>&1; then
        echo "🐳 Using docker compose command..."
        COMPOSE_BAKE=true docker compose $compose_args
    elif command -v docker-compose >/dev/null 2>&1; then
        echo "🐳 Using docker-compose command..."
        COMPOSE_BAKE=true docker-compose $compose_args
    else
        echo "❌ Neither 'docker compose' nor 'docker-compose' commands are available."
        echo "   Please install Docker Compose and try again."
        exit 1
    fi
}

# Parse command line arguments
CODEBASE_FILTER=""
FILTER_TYPE=""
PLATFORM_ARG=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --preedit)
            CODEBASE_FILTER="--preedit"
            FILTER_TYPE="preedit"
            shift
            ;;
        --postedit-beetle)
            CODEBASE_FILTER="--postedit-beetle"
            FILTER_TYPE="postedit-beetle"
            shift
            ;;
        --postedit-sonnet)
            CODEBASE_FILTER="--postedit-sonnet"
            FILTER_TYPE="postedit-sonnet"
            shift
            ;;
        --rewrite)
            CODEBASE_FILTER="--rewrite"
            FILTER_TYPE="rewrite"
            shift
            ;;
        --platform)
            if [[ -n "$2" && "$2" != --* ]]; then
                PLATFORM_ARG="--platform $2"
                shift 2
            else
                echo "❌ --platform requires a value (e.g., linux/amd64, linux/arm64)"
                show_usage
                exit 1
            fi
            ;;
        --version)
            echo "Codebase Validation Tool v062325_0840"
            exit 0
            ;;
        --help|-h)
            show_usage
            exit 0
            ;;
        *)
            echo "❌ Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

echo "==========================================="
echo "   Codebase Validation Tool"
echo "==========================================="
echo ""

if [ -n "$FILTER_TYPE" ]; then
    echo "🔍 Validating only: $FILTER_TYPE"
    echo ""
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if codebases directory exists
if [ ! -d "codebases" ]; then
    echo "❌ Codebases directory not found. Please create a 'codebases' directory and add your ZIP files."
    exit 1
fi

# Count ZIP files
zip_count=$(find codebases -name "*.zip" 2>/dev/null | wc -l | tr -d ' ')
if [ "$zip_count" -eq 0 ]; then
    echo "❌ No ZIP files found in codebases directory."
    echo "   Please add your codebase ZIP files to the 'codebases' directory."
    exit 1
fi

echo "✅ Found $zip_count ZIP file(s) to validate"
echo ""

# Create output directory if it doesn't exist
mkdir -p output

echo "Starting validation process..."
echo "   - Codebases directory: ./codebases"
echo "   - Output directory: ./output"
echo "   - Results file: ./output/validation_results.csv"
if [ -n "$FILTER_TYPE" ]; then
    echo "   - Filter: $FILTER_TYPE only"
fi
echo ""

# Build the Docker command with optional filter and platform
DOCKER_CMD="python validate_codebases.py --output /app/output/validation_results.csv --verbose"
if [ -n "$CODEBASE_FILTER" ]; then
    DOCKER_CMD="$DOCKER_CMD $CODEBASE_FILTER"
fi
if [ -n "$PLATFORM_ARG" ]; then
    DOCKER_CMD="$DOCKER_CMD $PLATFORM_ARG"
fi

# Run the validation with real-time output
echo "⏳ Building image and running Docker containers and tests..."
if [ -n "$CODEBASE_FILTER" ] || [ -n "$PLATFORM_ARG" ]; then
    # Build the image first, then use the regular validator service with custom command
    run_docker_compose build validator
    run_docker_compose run --rm validator $DOCKER_CMD
else
    # Use the regular service for default validation
    run_docker_compose up --build validator
fi

if [ -f "output/validation_results.csv" ]; then
    echo ""
    echo "✅ Validation completed successfully!"
    echo "Results saved to: output/validation_results.csv"
else
    echo ""
    echo "❌ Validation failed - no results file generated"
    exit 1
fi