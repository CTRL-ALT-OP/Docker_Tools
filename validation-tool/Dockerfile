FROM python:3.12-slim

# Install Docker CLI and other dependencies
RUN apt-get update && apt-get install -y \
    docker.io \
    bash \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user and add to docker group for DinD access
RUN groupadd -r appuser && useradd -r -g appuser appuser \
    && usermod -aG docker appuser

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create necessary directories and set permissions
RUN mkdir -p uploads results \
    && chown -R appuser:appuser /app

# Note: USER set via docker-compose for Docker-in-Docker compatibility

# Expose port
EXPOSE 8080

# Add health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Default command
CMD ["python", "app.py"] 