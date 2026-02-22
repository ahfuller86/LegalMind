# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set work directory
WORKDIR /app

# Install system dependencies (ffmpeg, tesseract, etc.)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    tesseract-ocr \
    libgl1-mesa-glx \
    libpango-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY legalmind-engine/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the engine code
COPY legalmind-engine/app ./app

# Create storage directory (mounted volume in prod)
RUN mkdir -p storage

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
