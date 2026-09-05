FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Prevent Python from writing pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies (needed for compiling certain python packages like asyncpg if wheels aren't available)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc python3-dev && \
    rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create a non-root user and switch to it for better security in production
RUN useradd -m appuser && chown -R appuser /app
USER appuser

# Expose the application port
EXPOSE 8000

# Run uvicorn with proxy headers enabled (for running behind Nginx/ALB/Render)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]

#Run uvicorn with n workers and proxy headers enabled (for running behind Nginx/ALB/Render)
#CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--workers", "n"]