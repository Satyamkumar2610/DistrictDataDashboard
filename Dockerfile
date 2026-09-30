# The platform: the read-only API and the web app over a release.
#
#   docker build -t district-evolution .
#   docker run --rm -p 8000:8000 -v "$PWD/data/release:/release:ro" district-evolution
#
# The image holds code, configuration and the curated reference tables only. The release is
# mounted at run time and never copied in: the 1951-2021 maps may not be redistributed
# (docs/decisions/licensing.md), so the image can be shared where the data cannot.

FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.13-slim
RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY requirements-platform.txt ./
RUN pip install --no-cache-dir -r requirements-platform.txt
COPY config/ config/
COPY data/reference/ data/reference/
COPY district_evolution/ district_evolution/
COPY --from=web /web/dist web/dist
# core creates its output directories on import; create them here, owned by the app user
RUN python -c "import district_evolution.core" && chown -R app /app/data /app/outputs
USER app
# the spatial extension is downloaded once at build time, not by every container at start
RUN python -c "import duckdb; duckdb.connect().execute('INSTALL spatial')"
ENV PYTHONPATH=/app DISTRICT_RELEASE_DIR=/release PYTHONUNBUFFERED=1
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/meta')"
CMD ["uvicorn", "district_evolution.release.api:app", "--host", "0.0.0.0", "--port", "8000"]
