FROM ubuntu:22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies (excluding blender - we'll install it separately)
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    ffmpeg \
    libmediainfo0v5 \
    libsdl1.2debian \
    libegl1 \
    wget \
    xz-utils \
    libgl1-mesa-glx \
    libglu1-mesa \
    libjpeg62 \
    libxi6 \
    libxrender1 \
    libxkbcommon-x11-0 \
    libsm6 \
    xvfb \
    build-essential \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Compile and install Python 2.6.9 (Required for Blender 2.49b)
# We configure with --enable-shared to generate libpython2.6.so
RUN wget https://www.python.org/ftp/python/2.6.9/Python-2.6.9.tgz \
    && tar -xvf Python-2.6.9.tgz \
    && cd Python-2.6.9 \
    && ./configure --enable-shared --prefix=/opt/python2.6 \
    && make \
    && make install \
    && cd .. \
    && rm -rf Python-2.6.9 Python-2.6.9.tgz

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

# Download and install Blender 2.49b (very old files: 2.4x era - Big Buck Bunny)
# This version is static and contains its own Python 2.6
RUN wget -q https://download.blender.org/release/Blender2.49b/blender-2.49b-linux-glibc236-py26-x86_64.tar.bz2 \
    && tar -xf blender-2.49b-linux-glibc236-py26-x86_64.tar.bz2 -C /opt \
    && rm blender-2.49b-linux-glibc236-py26-x86_64.tar.bz2

# Download and install Blender 2.79b (legacy files: 2.5x - 2.7x)
# Placed after pip install so Blender version changes don't invalidate pip cache
RUN wget -q https://download.blender.org/release/Blender2.79/blender-2.79b-linux-glibc219-x86_64.tar.bz2 \
    && tar -xf blender-2.79b-linux-glibc219-x86_64.tar.bz2 -C /opt \
    && rm blender-2.79b-linux-glibc219-x86_64.tar.bz2

# Download and install Blender 3.6 LTS (bridge for 2.80+ and 3.x era)
RUN wget -q https://download.blender.org/release/Blender3.6/blender-3.6.9-linux-x64.tar.xz \
    && tar -xf blender-3.6.9-linux-x64.tar.xz -C /opt \
    && rm blender-3.6.9-linux-x64.tar.xz

# Download and install Blender 4.5.5 LTS (modern files: 2.8+)
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
