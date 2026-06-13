FROM python:3.12-slim

WORKDIR /app

# Install dependencies and the application package.
COPY pyproject.toml ./
COPY wca_records_analyser ./wca_records_analyser
RUN pip install --no-cache-dir .

EXPOSE 8000

# Shell form so ${PORT} expands: Render injects $PORT at runtime and routes to
# it; the 8000 fallback keeps local/CI Docker runs (and EXPOSE) working unchanged.
CMD uvicorn wca_records_analyser.web:app --host 0.0.0.0 --port ${PORT:-8000}
