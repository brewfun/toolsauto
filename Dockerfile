# Use an official Python runtime as a parent image
FROM python:3.12-slim-bookworm

# Set the working directory in the container
WORKDIR /app

# Set Python path to include the app directory
ENV PYTHONPATH=/app

# Copy the backend requirements file and install dependencies
COPY ./backend/requirements/base.txt .
RUN pip install --no-cache-dir -r base.txt

# Copy the entire application code
COPY . .

# Set environment variables
ENV FLASK_APP=backend/main.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=5000

# Expose the port the app runs on
EXPOSE 5000

# Run the application
CMD ["flask", "run"]