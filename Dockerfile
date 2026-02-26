# SCADA Simulator - Python Runtime
FROM python:3.10-slim

LABEL maintainer="SCADA SIM Team"
LABEL description="Industrial SCADA Simulator with Modbus TCP & IEC 104"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create logs directory
RUN mkdir -p logs

# Expose ports
# Modbus TCP
EXPOSE 502
# IEC 104
EXPOSE 2404
# HTTP API (if added later)
EXPOSE 8080

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV SCADA_MODE=simulator

# Run simulator by default
CMD ["python3", "simulator.py"]
