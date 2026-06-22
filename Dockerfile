FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Install system dependencies required by OpenCV and MediaPipe
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libglib2.0-0 \
    libgl1 \
    libxcb1 \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python dependencies, then force opencv-python-headless
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip uninstall -y opencv-python opencv-contrib-python opencv-python-headless \
    && pip install --no-cache-dir opencv-python-headless

# Copy the annotator script, Flask app, and UI assets
COPY script.py .
COPY app.py .
COPY templates/ ./templates/
COPY static/ ./static/

# Expose port 5000 for Flask UI
EXPOSE 5000

# Default container directories for image/label processing
ENV IMAGE_FOLDER=/data/images

# Prevent UI-related crashes in headless environments
ENV QT_QPA_PLATFORM=offscreen
ENV GLOG_minloglevel=2

# Run the Flask web application
CMD ["python", "app.py"]
