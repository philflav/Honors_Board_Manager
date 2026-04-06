# Use the official Playwright Python image as base
# This image includes all necessary system dependencies for Chromium
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# Set the working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN apt-get update && apt-get install -y fonts-liberation && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt

# Install the Chromium browser binary
RUN playwright install chromium

# Copy the rest of the application code
COPY . .

# Ensure the automated_images directory exists
RUN mkdir -p automated_images

# Expose the default Streamlit port
EXPOSE 8501

# Command to run the Streamlit app
# --server.address 0.0.0.0 is critical for Docker reachability
# --server.port 8501 ensures it matches the EXPOSE and Render config
# --server.enableCORS=false and --server.enableXsrfProtection=false resolve static asset loading issues on Render
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.enableCORS=false", "--server.enableXsrfProtection=false"]
