
FROM python:3.12-slim
WORKDIR /app
COPY . /app/rest_api_server
RUN pip install --no-cache-dir /app/rest_api_server && useradd --create-home appuser
USER appuser
EXPOSE 8000
CMD ["uvicorn", "rest_api_server.main:app", "--host", "0.0.0.0", "--port", "8000"]
