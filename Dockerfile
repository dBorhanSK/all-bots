FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["sh", "-c", "gunicorn --workers 1 --threads 12 --worker-class gthread --timeout 120 --bind 0.0.0.0:${PORT:-8000} wsgi:application"]
