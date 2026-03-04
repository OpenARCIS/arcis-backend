# Use an official Python runtime as a parent image, slim version for reduced size
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install System Dependencies (Node.js and required build tools)
RUN apt-get update && \
    apt-get install -y curl ca-certificates gnupg && \
    # Install Node.js 20.x from NodeSource
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    # Clean up apt cache to reduce image size
    apt-get clean && rm -rf /var/lib/apt/lists/*
    
# Install uv (Keep for MCP servers that might need it)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install dependencies using standard pip
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose the port the app runs on (if still relevant for other parts)
EXPOSE 8501

# Command to run the application directly
CMD ["python", "-m", "arcis"]
