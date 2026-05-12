# Use the official Playwright Python image as base
# This image includes all necessary system dependencies for Chromium
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# Set the working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN apt-get update && apt-get install -y curl && \
    pip install --no-cache-dir -r requirements.txt

# Install Liberation fonts via apt and verify installation
RUN apt-get update && apt-get install -y fonts-liberation fonts-liberation2 && \
    fc-cache -fv

# Create symlinks to ensure fonts are in the expected location
RUN mkdir -p /usr/share/fonts/truetype/liberation && \
    find /usr/share/fonts -name "*Liberation*.ttf" -exec cp {} /usr/share/fonts/truetype/liberation/ \; 2>/dev/null || true && \
    fc-cache -fv

# Verify font installation
RUN echo "Checking for Liberation fonts:" && \
    find /usr/share/fonts -name "*Liberation*" -type f 2>/dev/null || echo "No Liberation fonts found"

# Install the Chromium browser binary
RUN playwright install chromium

# Copy the rest of the application code
COPY . .

# Ensure the automated_images directory exists
RUN mkdir -p automated_images

# Expose the Flask port
EXPOSE 5000

# Command to run the Flask app with Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "300", "app:app"]
