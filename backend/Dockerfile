FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Strip Windows CR characters and set executable — defensive against CRLF on Windows hosts
RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh

EXPOSE 5000

CMD ["/app/entrypoint.sh"]