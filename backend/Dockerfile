FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV FLASK_APP=wsgi.py

EXPOSE 5000

CMD flask db upgrade && gunicorn --bind 0.0.0.0:${PORT:-5000} --workers 4 --worker-class gthread --threads 2 --access-logfile - --error-logfile - wsgi:app