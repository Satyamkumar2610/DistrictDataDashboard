# Hosting the platform

For a **private** instance — one only you can open. That is the only mode this runbook covers,
deliberately: see *Why private* below.

## Why private

The platform serves the release, and the release carries simplified polygons for all nine maps. The
1951–2021 layers are ML InfoMap data licensed to Stanford affiliates, *"not to be reproduced or used
for any purpose without permission"* (`docs/decisions/licensing.md`, which also notes that the API
and explorer serve those polygons). A public address redistributes them, and a public address is hard
to take back: it can be crawled, cached and mirrored within hours.

So two rules hold for any host:

1. **The password is set before the app is reachable.** With `DISTRICT_AUTH_PASSWORD` unset the app
   serves everything to anyone — correct for localhost, wrong for an address. It prints a warning at
   startup when the password is missing; `fly.toml` carries no password, so a first deploy without
   `fly secrets set` is open. Set the secret first.
2. **The release is never baked into the image.** The `Dockerfile` copies code, config and the
   curated reference tables only. The data arrives on a mounted volume, by hand. An image can go to a
   registry; the data cannot.

What the password protects: the web app, the vector tiles, every JSON endpoint and
`/api/download/*.parquet` — which hands over the full tables. Only `/api/health` is open, so the
platform can health-check a machine that holds no credentials; it returns the version and config hash
and nothing else.

## Fly.io

```bash
# once
brew install flyctl && fly auth login
fly launch --no-deploy                      # take the app name it suggests, put it in fly.toml
fly volumes create release --size 2 --region bom
fly secrets set DISTRICT_AUTH_PASSWORD="$(openssl rand -base64 24)"   # prints nothing; read it back below
fly secrets list                            # confirms it is set (values are never shown again)

# deploy the code
fly deploy

# fill the volume: the one manual step, and the one that must never be automated into the image
fly ssh console -C "mkdir -p /release"
tar czf - -C data/release . | fly ssh console -C "tar xzf - -C /release"
fly ssh console -C "ls /release"            # expect: MANIFEST.csv, tables/, geometry/, load.sql, ...

fly apps restart                            # pick up the now-populated volume
fly open                                    # the browser asks for user "district" and your password
```

Generate the password somewhere you can read it (a password manager), since `fly secrets set` will
not show it again:

```bash
openssl rand -base64 24                     # copy this, then pass it to fly secrets set
```

**After a code change:** `fly deploy` again. The volume is untouched, so the release stays.
**After a pipeline rebuild:** re-upload the release with the `tar` line above, then
`fly apps restart`.

## Render or Railway

Same shape, different words. Both build the `Dockerfile` directly:

- **Disk**: attach a persistent disk mounted at `/release` (2 GB). Upload the release through the
  provider's shell, as in the `tar` line above.
- **Environment**: `DISTRICT_RELEASE_DIR=/release`, and `DISTRICT_AUTH_PASSWORD` as a *secret*, not a
  plain env var.
- **Health check path**: `/api/health`.
- **Port**: 8000.

Neither gives a volume on the free tier at the time of writing, so a release has to live on a paid
disk — or the instance has to be rebuilt from scratch on each deploy, which means re-uploading 62 MB.
Fly's volume is the cheaper fit for a private instance that mostly sleeps.

## A VPS you already have

`compose.yaml` already describes this: the release is a read-only bind mount, the container runs
unprivileged on a read-only filesystem. Add the password and put it behind TLS:

```bash
DISTRICT_AUTH_PASSWORD="…" docker compose up -d --build
```

Then terminate TLS at nginx or Caddy in front, and set `client_max_body_size 16m` to match
`harmonize.max_request_bytes`.

## Checking it is actually private

From a machine that is not logged in, and before you share the address with anyone:

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://<your-app>/                               # 401
curl -s -o /dev/null -w '%{http_code}\n' https://<your-app>/api/download/ck_registry.parquet  # 401
curl -s -o /dev/null -w '%{http_code}\n' https://<your-app>/api/tiles/2025/4/11/6.pbf      # 401
curl -s -o /dev/null -w '%{http_code}\n' https://<your-app>/api/health                     # 200
curl -s -o /dev/null -w '%{http_code}\n' -u district:<password> https://<your-app>/        # 200
```

Four 401s, one 200, then 200 with the password. Anything else and the instance is open: take it down
(`fly apps destroy`, or stop the container) before fixing it.

`tests/test_release.py` holds the same checks against the middleware, so a change that opens the app
by accident fails the build.

## If you later want it public

That needs a licensing decision first, not a configuration change. The options are in
`docs/decisions/licensing.md`: permission from ML InfoMap, or publishing only what the sources allow
(code, methods, the Wikidata evidence) with the restricted geometry held back. Hosting publicly
before then is the one step this project has consistently avoided.
