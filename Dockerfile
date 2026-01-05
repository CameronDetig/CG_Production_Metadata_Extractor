FROM ubuntu:22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    blender \
    python3 \
    python3-pip \
    ffmpeg \
    libmediainfo0v5 \
    wget \
    xz-utils \
    libgl1-mesa-glx \
    libxi6 \
    libxrender1 \
    libxkbcommon-x11-0 \
    libsm6 \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Create python symlink so both 'python' and 'python3' work
RUN ln -s /usr/bin/python3 /usr/bin/python

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
ENV PYTHONPATH=/app/src

# Default command
CMD ["python3", "src/scanner.py"]
