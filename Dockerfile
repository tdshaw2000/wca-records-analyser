FROM python:3.12-slim

WORKDIR /app

# Install dependencies and the application package.
COPY pyproject.toml ./
COPY wca_records_analyser ./wca_records_analyser
RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "wca_records_analyser.web:app", "--host", "0.0.0.0", "--port", "8000"]
