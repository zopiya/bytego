# ByteGo - Lightweight Binary Asset Manager

ByteGo is a simple, secure, and efficient file upload service built on **Cloudflare Workers** and **R2 Storage**. It provides a clean web interface for uploading files and getting direct CDN links.

## Features

- **Serverless**: Runs entirely on Cloudflare Workers.
- **Cost-Effective**: Uses Cloudflare R2 (zero egress fees).
- **Secure**: Token-based authentication and CORS protection.
- **Customizable**: Easy to configure domains and path formats.
- **User-Friendly**: Drag-and-drop interface with clipboard integration.

## Prerequisites

- Node.js & npm
- Cloudflare Account (Workers & R2 enabled)
- Wrangler CLI (`npm install -g wrangler`)

## Quick Start

1.  **Clone the repository**

    ```bash
    git clone https://github.com/yourusername/bytego.git
    cd bytego
    ```

2.  **Configure `wrangler.toml`**
    Edit `wrangler.toml` to match your setup:

    - `routes`: Set your Worker's domain (e.g., `bytego.yourdomain.com`).
    - `PUBLIC_DOMAIN`: Set your R2 custom domain (e.g., `https://cdn.yourdomain.com`).
    - `CORS_ORIGINS`: Add your Worker's domain here.
    - `APP_TITLE`: Customize the page title.

3.  **Initialize Project**
    Run the initialization script to set up R2 bucket, CORS, and deploy for the first time:

    ```bash
    npm run init
    ```

    _Follow the interactive prompts if your configuration is missing._

4.  **Set Authentication Key**
    Set a secure secret for uploading:

    ```bash
    wrangler secret put AUTH_KEY
    # Enter your secret when prompted
    ```

5.  **Update & Redeploy**
    For future code updates or configuration changes:
    ```bash
    npm run deploy
    ```

## Configuration

### Path Format

You can customize how file paths are generated in `wrangler.toml`:

```toml
UPLOAD_PATH_FORMAT = "{year}/{month}/{day}/{randomkey16}{ext}"
```

Supported variables: `{year}`, `{month}`, `{day}`, `{date}`, `{time}`, `{timestamp}`, `{randomkey8}`, `{randomkey16}`, `{uuid}`, `{originname}`, `{ext}`.

### CORS

To allow usage from other websites (e.g., your blog), add them to `CORS_ORIGINS` in `wrangler.toml`.

## License

MIT
