FROM mcr.microsoft.com/dotnet/sdk:8.0.411-alpine3.22@sha256:071ec6075f01f91ceaef8f1eaed5d43873635d46441f99221473c456f37f8c20

WORKDIR /app

# Copy sln and project folders
COPY . .

# Restore deps for all projects
RUN dotnet restore

# Build & run tests
RUN ["sh"]
