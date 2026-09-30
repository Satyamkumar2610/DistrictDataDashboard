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
- Health: `GET /api/meta` (the image's HEALTHCHECK). Every response's `meta` names the pipeline
  version and config hash of the release it serves.
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
/api/harmonize` processes uploads in memory and stores nothing; cap request bodies at the proxy
to match `harmonize.max_request_rows`.
