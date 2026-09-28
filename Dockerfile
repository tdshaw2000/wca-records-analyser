FROM python:3.12-slim

LABEL org.opencontainers.image.source=https://github.com/tdshaw2000/wca-records-analyser

WORKDIR /app

# Install dependencies and both packages: the web app and the data layer it reads with.
COPY pyproject.toml LICENSE ./
COPY wca_records_analyser ./wca_records_analyser
COPY wca_data ./wca_data
RUN pip install --no-cache-dir .

# The Compose project and systemd units, so the VM can copy them out of the image
# (docs/runbook.md) instead of needing a checkout of the repository.
COPY deploy /opt/wca-records-analyser/deploy

# The same uid owns /srv/wca-data on the VM (docs/runbook.md).
USER 10001:10001

EXPOSE 8000

# The pull deploy (deploy/pull_deploy.py) waits for this before keeping a new image.
# /healthz doesn't read the database, so a schema bump isn't rolled back against the old one.
HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4)"]

# Shell form so ${PORT} expands: Render injects $PORT at runtime and routes to
# it; the 8000 fallback is what the VM (and local Docker runs) use.
CMD uvicorn wca_records_analyser.web:app --host 0.0.0.0 --port ${PORT:-8000}
