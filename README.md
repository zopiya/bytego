# ByteGo 📦

[中文文档](README_zh.md)

**ByteGo** is a minimalist, self-hosted binary asset manager designed to decouple content (Markdown) from resources (images, PDFs, attachments). Upload files via paste, drag-drop, or click, and instantly get permanent CDN links for embedding in your blog, wiki, or notes.

## ✨ Features

- 🎯 **Ultra-Simple Upload**: Paste (Ctrl+V), drag-drop, or click to upload up to 10 files simultaneously.
- 🚀 **High Performance**: Serial frontend uploads + Streaming backend transfer for minimal memory usage.
- 🔐 **Secure by Design**: Access key authentication with IP-based rate limiting (3 attempts, 1-hour ban).
- 🗂️ **Smart File Naming**: Automatic MD5-based deduplication and custom path templates.
- 📂 **Organized Storage**: Date-based S3 paths (`YYYY/MM/DD/filename-hash.ext`).
- 🔗 **Multi-Format Export**: Copy links as raw URL, Markdown, or HTML with one click.
- 📜 **Persistent History**: Last 10 uploads saved locally.
- 📝 **Advanced Logging**: Configurable log persistence with automatic rotation.
- 🐳 **Docker-First**: Single-image deployment with health checks.

## 🏗️ Architecture

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│   Browser   │─────▶│   ByteGo    │─────▶│   S3/CDN    │
│  (Vanilla)  │      │  (Flask)    │      │  (Storage)  │
└─────────────┘      └─────────────┘      └─────────────┘
```

- **Frontend**: Single HTML file (no frameworks), 100% vanilla JavaScript.
- **Backend**: Flask + Boto3 for S3-compatible storage (AWS S3, Cloudflare R2, MinIO, Tencent COS, etc.).
- **Storage**: Any S3-compatible object storage with optional CDN.

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- S3-compatible storage (AWS S3, Cloudflare R2, etc.)
- Access key for authentication (generate with `openssl rand -hex 32`)

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/bytego.git
cd bytego
```

### 2. Configure Environment

Copy the example environment file and fill in your values:

```bash
cp .env.example .env
nano .env  # Edit with your credentials
```

**Required variables:**

```env
S3_ENDPOINT=https://s3.amazonaws.com
S3_ACCESS_KEY=your_access_key_here
S3_SECRET_KEY=your_secret_key_here
S3_BUCKET=your-bucket-name
PUBLIC_DOMAIN=https://cdn.example.com
AUTH_KEY=sk_live_your_secret_key_here
```

### 3. Run with Docker Compose

```bash
docker-compose up -d
```

The service will be available at `http://localhost:8000`.

### 4. Access ByteGo

Open your browser and navigate to `http://localhost:8000`. Enter your `AUTH_KEY` when prompted.

## 📖 Usage

### Uploading Files

1. **Paste**: Copy an image to clipboard, press `Ctrl+V` on the ByteGo page.
2. **Drag-Drop**: Drag files into the upload zone.
3. **Click**: Click the upload zone to select files.

### Getting Links

After upload, click one of the three buttons:

- **Link**: Raw CDN URL (`https://cdn.example.com/2024/12/25/file-a1b2c3d4.png`)
- **MD**: Markdown format (`![](https://...)`)
- **HTML**: HTML tag (`<img src="https://..." />`)

### Batch Upload

Upload up to 10 files at once. The frontend processes files serially to ensure stability. All successful URLs are automatically copied to clipboard (newline-separated).

## 🔧 Configuration

### Environment Variables

| Variable        | Required | Default     | Description            |
| :-------------- | :------- | :---------- | :--------------------- |
| `S3_ENDPOINT`   | ✅       | -           | S3 API Endpoint        |
| `S3_ACCESS_KEY` | ✅       | -           | S3 Access Key ID       |
| `S3_SECRET_KEY` | ✅       | -           | S3 Secret Access Key   |
| `S3_BUCKET`     | ✅       | -           | Bucket Name            |
| `AUTH_KEY`      | ✅       | -           | Access Password        |
| `PUBLIC_DOMAIN` | ❌       | S3_ENDPOINT | Public CDN Domain      |
| `LOG_TO_FILE`   | ❌       | false       | Enable log persistence |
| `LOG_DIR`       | ❌       | logs        | Log directory          |

## 📄 License

MIT License
| ------------------ | -------- | ------------- | ---------------------- |
| `S3_ENDPOINT` | ✅ | - | S3 endpoint URL |
| `S3_ACCESS_KEY` | ✅ | - | S3 access key |
| `S3_SECRET_KEY` | ✅ | - | S3 secret key |
| `S3_BUCKET` | ✅ | - | S3 bucket name |
| `S3_ACL` | ❌ | `public-read` | S3 object ACL |
| `PUBLIC_DOMAIN` | ⚠️ | `S3_ENDPOINT` | Public CDN URL prefix |
| `AUTH_KEY` | ✅ | - | Access key for uploads |
| `MAX_FILE_SIZE_MB` | ❌ | `100` | Max file size in MB |
| `FLASK_DEBUG` | ❌ | `false` | Enable debug mode |
| `PORT` | ❌ | `8000` | Server port |
| `GUNICORN_WORKERS` | ❌ | `auto` | Number of workers |
| `LOG_LEVEL` | ❌ | `info` | Log level |

### S3 Provider Examples

#### AWS S3

```env
S3_ENDPOINT=https://s3.amazonaws.com
S3_BUCKET=my-bytego-bucket
PUBLIC_DOMAIN=https://my-bytego-bucket.s3.amazonaws.com
```

#### Cloudflare R2

```env
S3_ENDPOINT=https://<account-id>.r2.cloudflarestorage.com
S3_BUCKET=bytego
PUBLIC_DOMAIN=https://cdn.example.com  # Custom domain
```

#### MinIO (Self-Hosted)

```env
S3_ENDPOINT=https://minio.example.com
S3_BUCKET=bytego
PUBLIC_DOMAIN=https://minio.example.com/bytego
```

## 🛡️ Security Features

### Authentication

- Access key required for all uploads (stored in LocalStorage)
- Constant-time comparison to prevent timing attacks

### IP-Based Rate Limiting

- 3 failed authentication attempts → 1-hour ban
- Supports `X-Forwarded-For` for reverse proxy deployments

### File Validation

- Configurable file size limit (default 100MB)
- MD5-based deduplication prevents storage waste

### Production Best Practices

- Non-root container user (`bytego:1000`)
- No exposed credentials in logs
- Health check endpoint for orchestration

## 📊 API Reference

### `POST /upload`

Upload a file to S3 storage.

**Headers:**

```
Authorization: sk_live_your_secret_key_here
```

**Body:**

```
Content-Type: multipart/form-data
file: <binary data>
```

**Response (Success):**

```json
{
  "msg": "success",
  "url": "https://cdn.example.com/2024/12/25/photo-a1b2c3d4.jpg"
}
```

**Response (Error):**

```json
{
  "msg": "Invalid Access Key"
}
```

**Status Codes:**

- `200`: Success
- `400`: Bad request (no file, file too large)
- `401`: Unauthorized (missing/invalid key)
- `403`: Forbidden (IP banned)
- `500`: Server error

### `GET /health`

Health check endpoint for load balancers.

**Response (Healthy):**

```json
{
  "status": "healthy",
  "s3": "connected"
}
```

**Response (Unhealthy):**

```json
{
  "status": "unhealthy",
  "error": "S3 connection failed"
}
```

## 🐳 Deployment

### Docker Compose (Recommended)

```yaml
services:
  bytego:
    image: ghcr.io/yourusername/bytego:latest
    ports:
      - "8000:8000"
    env_file:
      - .env
    restart: unless-stopped
```

### Docker Build

```bash
docker build -t bytego:latest .
docker run -d -p 8000:8000 --env-file .env bytego:latest
```

### Reverse Proxy (Nginx)

```nginx
server {
    listen 443 ssl http2;
    server_name bytego.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    client_max_body_size 100M;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bytego
spec:
  replicas: 2
  template:
    spec:
      containers:
        - name: bytego
          image: ghcr.io/yourusername/bytego:latest
          ports:
            - containerPort: 8000
          envFrom:
            - secretRef:
                name: bytego-secrets
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 30
```

## 🔍 Troubleshooting

### Files Not Uploading

1. **Check S3 credentials**: Verify `S3_ACCESS_KEY` and `S3_SECRET_KEY`
2. **Bucket permissions**: Ensure the bucket allows PutObject
3. **CORS settings**: If frontend is separate, configure S3 CORS
4. **File size**: Check if file exceeds `MAX_FILE_SIZE_MB`

### "Banned" Error

- Wait 1 hour or restart the service (in-memory ban storage)
- Check if `AUTH_KEY` is correct in LocalStorage
- For production, consider Redis-backed ban storage (see Roadmap)

### Health Check Failing

```bash
docker logs bytego
# Check S3 connection
curl http://localhost:8000/health
```

### Behind Cloudflare/Nginx

Ensure `X-Forwarded-For` header is passed:

```nginx
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
```

## 🛣️ Roadmap

- [ ] Redis-based ban storage for distributed deployments
- [ ] Optional image thumbnail generation
- [ ] File type restrictions via whitelist
- [ ] Upload progress bars for large files
- [ ] Admin dashboard with upload stats
- [ ] Webhook notifications on upload
- [ ] Multi-user support with per-key quotas

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 🙏 Contributing

Contributions welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) first.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 💬 Support

- 📧 Email: support@example.com
- 🐛 Issues: [GitHub Issues](https://github.com/yourusername/bytego/issues)
- 💬 Discussions: [GitHub Discussions](https://github.com/yourusername/bytego/discussions)

---

**Made with ❤️ for content creators who value simplicity**
