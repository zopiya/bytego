# ByteGo - Lightweight Binary Asset Manager

[简体中文](README.zh-CN.md)

ByteGo is a small self-hosted upload service built on Cloudflare Workers and Cloudflare R2. It provides a clean browser UI for uploading files and copying public CDN links, while keeping the runtime shape intentionally simple: one Worker, one R2 bucket, no database, and no frontend build system.

ByteGo is not trying to be a full file-management backend. The Worker handles authentication, object-key validation, R2 writes, optional configured delete behavior, and URL generation. The browser keeps recent upload history locally in IndexedDB.

## Features

- Cloudflare-native Worker + R2 deployment.
- Bearer-token protected upload API.
- Drag, drop, paste, batch upload, and clipboard copy UI.
- Copy as direct link, Markdown image, or HTML image tag.
- Configurable object-key format and optional upload root prefix.
- Local browser upload history with no server-side listing/index.
- Optional `Delete` action controlled by `DELETE_MODE`.
- Simple Wrangler-based deployment with npm wrappers for checks, secrets, dry-run, and deploy.

## Project Shape

- Worker entrypoint: `src/index.ts`
- Path and URL helpers: `src/utils.ts`
- Browser UI: `src/index.html`
- Worker/R2 config template: `wrangler.toml.example`
- R2 CORS config: `cors.json`

## Quick Start

1. Install dependencies.

   ```bash
   npm install
   ```

2. Create your local Wrangler config.

   ```bash
   cp wrangler.toml.example wrangler.toml
   ```

3. Edit `wrangler.toml`.

   Set the Worker route, R2 public domain, CORS origins, bucket name, and any optional path/delete settings.

4. Prepare Cloudflare resources with Wrangler or the Cloudflare dashboard.

   Create the R2 bucket from `wrangler.toml`, apply `cors.json` to the bucket, and bind the R2 public/custom domain used by `PUBLIC_DOMAIN`.

   ```bash
   npm run r2:list
   npx wrangler r2 bucket create bytego
   npx wrangler r2 bucket cors set bytego --file cors.json
   npx wrangler r2 bucket domain add bytego --domain cdn.yourdomain.com --zone-id your-zone-id
   ```

5. Set the upload secret.

   ```bash
   npm run secret:put
   ```

6. Validate and deploy.

   ```bash
   npm run deploy:dry-run
   npm run deploy
   ```

`npm run deploy` is intentionally only `wrangler deploy`. It does not create the R2 bucket, set R2 CORS, bind the R2 public domain, or set secrets. Use Wrangler directly for those one-time resource operations.

For normal local validation, use `npm run typecheck` and `npm test`. Do not use `npm run deploy` as a routine check; it deploys to Cloudflare.

## Configuration

Copy `wrangler.toml.example` to `wrangler.toml`, then edit the local file before deploying.

`wrangler.toml` is ignored by Git because it contains deployment-specific routes, domains, bucket names, and app settings. Keep reusable defaults in `wrangler.toml.example`.

For local authenticated upload testing, create an ignored `.dev.vars` file with `AUTH_KEY=...`. This file is optional and must not be committed.

### Existing Deployment

If the Cloudflare Worker, R2 bucket, and R2 public domain already exist, reuse them instead of recreating resources:

```bash
npm run cf:whoami
npm run r2:list
npm run r2:domains
npm run secret:list
npm run deploy:dry-run
```

`secret:list` only reports secret names. If `AUTH_KEY` is missing, set it once:

```bash
npm run secret:put
```

Then deploy:

```bash
npm run deploy
```

This checkout keeps the real `wrangler.toml` local and ignored by Git. The committed `wrangler.toml.example` stays reusable for other deployments.

```toml
routes = [
  { pattern = "bytego.yourdomain.com", custom_domain = true }
]

[vars]
PUBLIC_DOMAIN = "https://cdn.yourdomain.com"
APP_TITLE = "ByteGo"
CORS_ORIGINS = "https://bytego.yourdomain.com,http://localhost:8787"
UPLOAD_PATH_FORMAT = "{year}/{month}/{day}/{randomkey16}{ext}"
# UPLOAD_ROOT_PREFIX = "uploads"
# DELETE_MODE = "soft"

[[r2_buckets]]
binding = "BUCKET"
bucket_name = "bytego"
```

### Domains

ByteGo uses two domain concepts:

- Worker domain: serves the UI and upload/delete API, for example `https://bytego.yourdomain.com`.
- R2 public domain: serves uploaded objects, for example `https://cdn.yourdomain.com`.

`PUBLIC_DOMAIN` must point to the R2 public/custom domain. If it is missing, uploads fail instead of returning a misleading relative URL.

`npm run deploy` can publish the Worker route from `wrangler.toml`, but it does not create or bind the R2 public domain. Use the Cloudflare dashboard or Wrangler's R2 domain command for that one-time setup:

```bash
npx wrangler r2 bucket domain add bytego --domain cdn.yourdomain.com --zone-id your-zone-id
```

### Authentication

Set `AUTH_KEY` as a Wrangler secret:

```bash
npm run secret:put
```

API clients should send it as a Bearer token:

```http
Authorization: Bearer your-secret-key
```

The browser UI can save the access key in `localStorage` for convenience. Treat that as a personal-device feature; avoid it on shared machines.

### Upload Path Format

Default:

```toml
UPLOAD_PATH_FORMAT = "{year}/{month}/{day}/{randomkey16}{ext}"
```

Supported variables:

- `{year}`, `{month}`, `{day}`
- `{date}` as `YYYYMMDD`
- `{time}` as `YYYYMMDDHHmmss`
- `{timestamp}`
- `{timestamp_nano}` as a JavaScript timestamp-derived value, not true nanosecond precision
- `{randomkey8}`, `{randomkey16}`
- `{uuid}`
- `{originname}`
- `{originname_without_ext}`
- `{ext}`

Filenames are sanitized before filename variables are expanded. The final object key is also validated. Empty keys, unsafe path segments, control characters, `?`, and `#` are rejected.

### Upload Root Prefix

Use `UPLOAD_ROOT_PREFIX` when you want every object key under one root:

```toml
UPLOAD_ROOT_PREFIX = "uploads"
```

This keeps all uploaded objects under paths like `uploads/2026/05/21/...`.

### Delete Mode

Deletion is disabled by default. When enabled, the UI still shows one user-facing action: `Delete`. The config decides what that button does.

```toml
# Default: no Delete button and no R2 delete API
# DELETE_MODE = "none"

# Delete removes only the local browser history record
DELETE_MODE = "soft"

# Delete removes the R2 object and then the local history record
DELETE_MODE = "hard"
```

Modes:

- `none`: default. The UI shows upload history and copy actions only. The Worker rejects `DELETE /object`.
- `soft`: shows `Delete`; it removes the record from local IndexedDB history and never touches R2.
- `hard`: shows the same `Delete`; after confirmation, the Worker deletes the R2 object by key and then removes the local record.

### CORS

There are two CORS layers:

- `CORS_ORIGINS` in `wrangler.toml` controls which browser origins may call the Worker upload/delete API.
- `cors.json` controls browser reads from the public R2 bucket/domain.

The default R2 CORS allows public `GET`/`HEAD` reads because uploaded URLs are intended to be public assets.

## Local History

ByteGo stores upload history in browser IndexedDB. This keeps the app simple and avoids Cloudflare D1/KV setup, migrations, cross-device sync rules, and a larger permission model.

Important implications:

- Upload history is local to the browser profile.
- Clearing site data removes the local history.
- The Worker does not provide a server-side list API.
- If local history is gone, use the Cloudflare dashboard or Wrangler to inspect/delete objects manually.

ByteGo allows any file type by default. If your use case needs MIME or extension restrictions, add that as a small configuration layer rather than turning the project into a full file management system.

## Commands

```bash
npm install
npm run typecheck
npm test
npm run deploy:dry-run
npm run dev
```

Live Cloudflare operations:

```bash
npm run deploy
```

`npm run deploy:dry-run` validates the Worker bundle and bindings without deploying. `npm run deploy` is a thin wrapper around `wrangler deploy`.

Resource and secret helpers:

```bash
npm run cf:whoami
npm run r2:list
npm run r2:domains
npm run secret:list
npm run secret:put
```

Use Wrangler directly for one-time Cloudflare resource setup when the resource does not already exist:

```bash
npx wrangler r2 bucket create bytego
npx wrangler r2 bucket cors set bytego --file cors.json
npx wrangler r2 bucket domain add bytego --domain cdn.yourdomain.com --zone-id your-zone-id
```

Local development:

```bash
npm run dev
```

If you need to test authenticated uploads locally, create `.dev.vars` manually:

```bash
AUTH_KEY=replace-with-a-local-dev-key
```

## API

### `POST /upload`

Multipart form upload.

Headers:

```http
Authorization: Bearer your-secret-key
```

Fields:

- `file`: required `File`
- `customPath`: optional object key

Response:

```json
{
  "msg": "success",
  "key": "uploads/2026/05/21/abc123.png",
  "url": "https://cdn.example.com/uploads/2026/05/21/abc123.png",
  "filename": "image.png",
  "size": 12345,
  "contentType": "image/png",
  "uploadedAt": "2026-05-21T03:04:05.000Z"
}
```

### `DELETE /object`

Deletes an R2 object by key only when `DELETE_MODE = "hard"`. ByteGo does not maintain a server-side recycle bin.

Headers:

```http
Authorization: Bearer your-secret-key
Content-Type: application/json
```

Body:

```json
{ "key": "uploads/2026/05/21/abc123.png" }
```

## Troubleshooting

- `401 Unauthorized`: check the `Authorization: Bearer ...` header and the `AUTH_KEY` Wrangler secret.
- `AUTH_KEY not set`: for production, run `npm run secret:put`; for local development, check `.dev.vars`.
- `PUBLIC_DOMAIN not set`: configure the R2 public/custom domain in `wrangler.toml`.
- Uploaded URL does not open: confirm the R2 public/custom domain is bound to the same bucket.
- CORS errors when uploading: add the Worker UI origin to `CORS_ORIGINS`.
- CORS errors when reading files: check the R2 bucket CORS in `cors.json`.
- Type-check command fails in a fresh checkout: run `npm install` first.
- Delete button is missing: set `DELETE_MODE` to `soft` or `hard` and redeploy.

## License

MIT
