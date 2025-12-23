FROM ubuntu:22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    blender \
    python3 \
    python3-pip \
    libmagic1 \
    ffmpeg \
    libmediainfo0v5 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directory for database
RUN mkdir -p /app/db

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Default command
CMD ["python3", "scanner.py"]
