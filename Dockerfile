FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 9090

CMD ["gunicorn", "--bind", "0.0.0.0:9090", "--workers", "2", "--worker-class", "gevent", "app:app"]
