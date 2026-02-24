FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Set the PYTHONPATH environment variable
ENV PYTHONPATH=/app
# Force unbuffered output so logs appear immediately
ENV PYTHONUNBUFFERED=1

CMD ["python", "-u", "-m", "core.worker.runner"]
