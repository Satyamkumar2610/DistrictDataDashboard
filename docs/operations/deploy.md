# Running the platform

The platform is the read-only API and the web app over one release (`data/release/`). It never
writes to the release; the batch pipeline is the only writer.

## Container (recommended)

```bash
docker compose up --build              # http://127.0.0.1:8000, API reference at /docs
# or
docker build -t district-evolution .
docker run --rm -p 8000:8000 --read-only --tmpfs /tmp -v "$PWD/data/release:/release:ro" district-evolution
```

- The image holds code, `config/`, the curated `data/reference/` tables and the built web app. The
  release is **mounted at run time, never copied in**: the 1951–2021 maps may not be redistributed
  (`docs/decisions/licensing.md`), so the image can be shared where the data cannot. Do not push
  an image built with data inside it.
- It runs as an unprivileged user on a read-only file system. The DuckDB spatial extension is
  installed at build time, so the container needs no network at run time.
- `requirements-platform.txt` is the run-time subset of `requirements.txt` (same pins). The
  pipeline's geometry, linkage and contract libraries are not in the image.
- Health: `GET /api/health` (the image's HEALTHCHECK): `{"status": "ok", "pipeline_version", "config_sha256"}`
  once the release is loaded and answers a query. Every JSON response's `meta` names the pipeline
  version and config hash of the release it serves.
- Responses over 1 KB are gzip-compressed for clients that accept it. Every response carries
  `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN` and `Referrer-Policy: same-origin`.
- Request bodies over `harmonize.max_request_bytes` (16 MB) are refused with 413 before they are
  parsed, whether the length is declared or the body is streamed.
- To serve another release, mount it at `/release` (or set `DISTRICT_RELEASE_DIR`).

CI builds the image, runs it read-only on the freshly built release, and runs the browser tests
against it (`PW_BASE_URL`).

## Without a container

```bash
(cd web && npm ci && npm run build)
PYTHONPATH=. .venv/bin/uvicorn district_evolution.release.api:app --host 127.0.0.1 --port 8000
```

## Behind a proxy

The app is one origin: the web app at `/`, JSON under `/api`, vector tiles under `/api/tiles`.
Tiles are rendered by DuckDB on request and cached in memory; a caching proxy in front (e.g.
nginx `proxy_cache` on `/api/tiles/`) serves repeat views without touching the API. `POST
/api/harmonize` processes uploads in memory and stores nothing. The app refuses bodies over
`harmonize.max_request_bytes` itself; a proxy limit at or below it (nginx `client_max_body_size 16m`)
refuses them earlier. Point the proxy's health check at `/api/health`.
