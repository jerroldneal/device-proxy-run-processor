FROM python:3.9-slim-bullseye

# Keep Python from buffering stdout and stderr
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    apt-transport-https \
    wget \
    software-properties-common \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (LTS)
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs

# Install PowerShell
# Download the Microsoft repository GPG keys
RUN wget -q "https://packages.microsoft.com/config/debian/11/packages-microsoft-prod.deb" \
    && dpkg -i packages-microsoft-prod.deb \
    && rm packages-microsoft-prod.deb \
    && apt-get update \
    && apt-get install -y powershell

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY processor.py .

# Create data directories
RUN mkdir -p /app/data/todo /app/data/todo-on-host /app/data/working /app/data/done

# Declare volumes
VOLUME ["/app/data"]

# Start the processor
CMD ["python", "-u", "processor.py"]
