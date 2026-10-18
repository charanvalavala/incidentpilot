FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src
COPY static ./static
COPY data ./data
ENV PYTHONPATH=/app/src
ENV INCIDENT_DB=/app/data/runtime/incidents.sqlite3
EXPOSE 8000
CMD ["uvicorn", "incidentpilot.api:app", "--host", "0.0.0.0", "--port", "8000"]
