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

# Blender archives are fetched from the private build-artifact bucket before the
# Docker build. Keeping AWS credentials outside BuildKit prevents them from being
# captured in image layers. SHA256SUMS is generated when the artifacts are uploaded.
COPY build-assets/blender/ /tmp/blender/
RUN cd /tmp/blender \
    && sha256sum --check SHA256SUMS \
    && tar -xf blender-2.49b-linux-glibc236-py26-x86_64.tar.bz2 -C /opt \
    && tar -xf blender-2.79b-linux-glibc219-x86_64.tar.bz2 -C /opt \
    && tar -xf blender-3.6.9-linux-x64.tar.xz -C /opt \
    && tar -xf blender-4.5.5-linux-x64.tar.xz -C /opt \
    && rm -rf /tmp/blender \
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
