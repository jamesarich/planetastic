FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY planetastic.py db.py web.py utils.py ./

# Environment variables for defaults
ENV DUMP1090_HOST=localhost
ENV DUMP1090_PORT=30003

# Expose the dashboard port
EXPOSE 8080

# Run the script
ENTRYPOINT ["python", "planetastic.py"]
CMD ["--config", "config.yaml"]
