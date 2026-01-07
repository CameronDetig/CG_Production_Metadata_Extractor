FROM ubuntu:22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies (excluding blender - we'll install it separately)
RUN apt-get update && apt-get install -y \
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

# Copy ONLY requirements first (for better caching)
# This layer will only rebuild if requirements.txt changes
COPY requirements.txt .

# Install Python dependencies
# This expensive step is cached unless requirements.txt changes
RUN pip3 install --no-cache-dir -r requirements.txt

# Download and install Blender 4.5.5 LTS
# Placed AFTER pip install so Blender version changes don't invalidate pip cache
RUN wget -q https://download.blender.org/release/Blender4.5/blender-4.5.5-linux-x64.tar.xz \
    && tar -xf blender-4.5.5-linux-x64.tar.xz -C /opt \
    && rm blender-4.5.5-linux-x64.tar.xz \
    && ln -s /opt/blender-4.5.5-linux-x64/blender /usr/local/bin/blender

# Copy application code LAST
# Code changes won't invalidate the pip install or Blender install cache above
COPY src/ ./src/

# Create directory for database
RUN mkdir -p /app/db

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

# Default command
CMD ["python3", "src/scanner.py"]
