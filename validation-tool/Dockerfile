FROM python:3.10-slim

# Install Docker CLI inside the container
RUN apt-get update && apt-get install -y \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY validate_codebases.py .

# Create directory for codebases
RUN mkdir -p /app/codebases

# Make script executable
RUN chmod +x validate_codebases.py

# Set default command
CMD ["python", "validate_codebases.py", "--help"]