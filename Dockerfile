# Use an official Python runtime as a parent image, slim version for reduced size
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose the port the app runs on
EXPOSE 8501

# Command to run the application
CMD ["uvicorn", "panda.__main__:api_server", "--host", "0.0.0.0", "--port", "8501"]
