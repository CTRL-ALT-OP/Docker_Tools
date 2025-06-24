FROM maven:3.9.9-eclipse-temurin-17-alpine@sha256:c1b318f88ab1bcf7aae3e0fceff4f5890fe6f7c910ead1c538bd5cada01df6c6 AS builder

WORKDIR /app

# Copy POM first to leverage Docker cache for dependencies
COPY pom.xml ./

# Download all dependencies and plugins independently
# This layer will be cached unless pom.xml changes
RUN mvn \
    --batch-mode \
    --no-transfer-progress \
    dependency:go-offline \
    dependency:resolve-plugins \
    dependency:resolve \
    dependency:sources

# Copy source code after dependencies are downloaded
COPY src ./src

COPY run_tests.sh ./

# Keep the compiled classes and dependencies available
CMD ["sh"]