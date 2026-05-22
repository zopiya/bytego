# ByteGo - 轻量二进制资源管理器

[English](README.md)

ByteGo 是一个基于 Cloudflare Workers 和 Cloudflare R2 的自部署上传服务。它提供一个简洁的浏览器界面，用来上传文件、复制公开 CDN 链接，并刻意保持很小的运行形态：一个 Worker、一个 R2 bucket、没有数据库、没有前端打包系统。

ByteGo 不是完整的网盘或文件管理后台。Worker 负责鉴权、对象 key 校验、写入 R2、可选删除行为和 URL 生成；浏览器端用 IndexedDB 保存最近上传记录。

## 功能

- Cloudflare Workers + R2 原生部署。
- Bearer token 保护上传 API。
- 支持拖拽、粘贴、批量上传和复制链接。
- 可复制直链、Markdown 图片语法或 HTML 图片标签。
- 可配置上传路径格式和统一上传根目录。
- 上传历史只保存在当前浏览器本地，不需要数据库。
- 可选 `Delete` 行为，由 `DELETE_MODE` 控制。
- 部署流程保持简单：npm 提供检查、secret、dry-run 和 deploy 的薄封装。

## 项目结构

- Worker 入口：`src/index.ts`
- 路径和 URL 工具：`src/utils.ts`
- 浏览器 UI：`src/index.html`
- Worker/R2 配置模板：`wrangler.toml.example`
- R2 CORS 配置：`cors.json`

## 快速开始

1. 安装依赖。

   ```bash
   npm install
   ```

2. 创建本地 Wrangler 配置。

   ```bash
   cp wrangler.toml.example wrangler.toml
   ```

3. 编辑 `wrangler.toml`。

   填好 Worker route、R2 public domain、CORS origins、bucket name，以及可选的路径和删除配置。

4. 用 Wrangler 或 Cloudflare Dashboard 准备一次性资源。

   创建 R2 bucket，应用 `cors.json`，并绑定 `PUBLIC_DOMAIN` 使用的 R2 public/custom domain。

   ```bash
   npm run r2:list
   npx wrangler r2 bucket create bytego
   npx wrangler r2 bucket cors set bytego --file cors.json
   npx wrangler r2 bucket domain add bytego --domain cdn.yourdomain.com --zone-id your-zone-id
   ```

5. 设置上传密钥。

   ```bash
   npm run secret:put
   ```

6. 校验并部署 Worker。

   ```bash
   npm run deploy:dry-run
   npm run deploy
   ```

`npm run deploy` 只是 `wrangler deploy` 的薄封装。它不会创建 R2 bucket、设置 R2 CORS、绑定 R2 public domain，也不会设置 secret。这些一次性资源操作直接用 Wrangler 更清楚。

日常本地校验用 `npm run typecheck` 和 `npm test`。不要把 `npm run deploy` 当作普通检查命令，因为它会部署到 Cloudflare。

## 配置

先复制模板，再编辑本地配置：

```bash
cp wrangler.toml.example wrangler.toml
```

`wrangler.toml` 已加入 `.gitignore`，因为它包含部署者自己的 route、domain、bucket name 和应用设置。仓库里只提交可复用的 `wrangler.toml.example`。

如果需要在本地测试带鉴权的上传，可以手动创建被忽略的 `.dev.vars`，写入 `AUTH_KEY=...`。这个文件是可选的，不要提交。

### 复用已有部署

如果 Cloudflare Worker、R2 bucket 和 R2 public domain 已经存在，不需要重新创建资源，先核对现状：

```bash
npm run cf:whoami
npm run r2:list
npm run r2:domains
npm run secret:list
npm run deploy:dry-run
```

`secret:list` 只会显示 secret 名称，不会显示 secret 值。如果缺少 `AUTH_KEY`，执行一次：

```bash
npm run secret:put
```

然后部署：

```bash
npm run deploy
```

当前 checkout 的真实 `wrangler.toml` 保持为本地文件，并已被 Git 忽略；仓库只提交可复用的 `wrangler.toml.example`。

核心配置示例：

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

### 域名

ByteGo 有两个域名概念：

- Worker 域名：访问 UI 和上传/删除 API，例如 `https://bytego.yourdomain.com`。
- R2 public domain：访问上传后的公开文件，例如 `https://cdn.yourdomain.com`。

`PUBLIC_DOMAIN` 必须指向 R2 public/custom domain。它不是 Worker 域名。如果没有配置，上传接口会返回服务端配置错误，避免生成错误的相对 URL。

`npm run deploy` 可以根据 `wrangler.toml` 发布 Worker route，但不会创建或绑定 R2 public domain。R2 域名绑定用 Cloudflare Dashboard 或 Wrangler：

```bash
npx wrangler r2 bucket domain add bytego --domain cdn.yourdomain.com --zone-id your-zone-id
```

### 鉴权

线上上传密钥使用 Wrangler secret：

```bash
npm run secret:put
```

API 客户端通过 Bearer token 传入：

```http
Authorization: Bearer your-secret-key
```

浏览器 UI 可以把 access key 保存在 `localStorage`，方便个人设备使用。不要在共享设备上保存。

### 上传路径格式

默认格式：

```toml
UPLOAD_PATH_FORMAT = "{year}/{month}/{day}/{randomkey16}{ext}"
```

支持变量：

- `{year}`、`{month}`、`{day}`
- `{date}`，格式为 `YYYYMMDD`
- `{time}`，格式为 `YYYYMMDDHHmmss`
- `{timestamp}`
- `{timestamp_nano}`，基于 JavaScript timestamp 计算，不是真正的纳秒精度
- `{randomkey8}`、`{randomkey16}`
- `{uuid}`
- `{originname}`
- `{originname_without_ext}`
- `{ext}`

文件名会先被清洗，再展开到路径变量里。最终 object key 也会校验：空 key、不安全路径段、控制字符、`?` 和 `#` 都会被拒绝。

### 上传根目录

如果希望所有文件都放在统一前缀下，可以设置：

```toml
UPLOAD_ROOT_PREFIX = "uploads"
```

生成路径会变成类似 `uploads/2026/05/21/...`。

### 删除模式

默认不启用删除。启用后，UI 仍然只展示一个 `Delete` 操作，具体行为由配置决定。

```toml
# 默认：不显示 Delete，也不允许 R2 删除 API
# DELETE_MODE = "none"

# 只删除浏览器本地历史记录
DELETE_MODE = "soft"

# 删除 R2 对象，然后删除本地历史记录
DELETE_MODE = "hard"
```

模式说明：

- `none`：默认。UI 只展示历史和复制操作，Worker 拒绝 `DELETE /object`。
- `soft`：显示 `Delete`，只把记录从本地 IndexedDB 历史里移除，不碰 R2。
- `hard`：显示同一个 `Delete`，确认后由 Worker 删除 R2 object，再移除本地记录。

### CORS

这里有两层 CORS：

- `wrangler.toml` 里的 `CORS_ORIGINS`：控制哪些浏览器 origin 可以调用 Worker 上传/删除 API。
- `cors.json`：控制浏览器能否从 R2 public bucket/domain 读取文件。

默认的 R2 CORS 允许公开 `GET`/`HEAD` 读取，因为上传后的 URL 设计上就是公开资源链接。

## 本地开发

```bash
npm run dev
```

如果需要本地测试上传鉴权，手动创建 `.dev.vars`：

```bash
AUTH_KEY=replace-with-a-local-dev-key
```

本地开发仍然需要 `wrangler.toml`，并且需要一个可用的 R2 binding。若只想改 UI 或工具函数，可以先跑：

```bash
npm run typecheck
npm test
```

## 本地上传历史

ByteGo 把上传历史存到浏览器 IndexedDB。这让项目不需要 Cloudflare D1/KV、迁移、跨设备同步和复杂权限模型。

需要注意：

- 上传历史只存在当前浏览器配置里。
- 清理站点数据会删除本地历史。
- Worker 不提供服务端列表 API。
- 如果本地历史丢失，需要通过 Cloudflare Dashboard 或 Wrangler 查看和删除 R2 对象。

ByteGo 默认允许任何文件类型。如果你的场景需要限制 MIME 或扩展名，建议增加一个小配置层，不要把项目扩展成完整文件管理系统。

## 命令

```bash
npm install
npm run typecheck
npm test
npm run deploy:dry-run
npm run dev
```

线上部署：

```bash
npm run deploy
```

`npm run deploy:dry-run` 只校验 Worker bundle 和 bindings，不会部署。`npm run deploy` 是 `wrangler deploy` 的薄封装。

资源和 secret 辅助命令：

```bash
npm run cf:whoami
npm run r2:list
npm run r2:domains
npm run secret:list
npm run secret:put
```

如果资源还不存在，再直接用 Wrangler 做一次性 Cloudflare 资源操作：

```bash
npx wrangler r2 bucket create bytego
npx wrangler r2 bucket cors set bytego --file cors.json
npx wrangler r2 bucket domain add bytego --domain cdn.yourdomain.com --zone-id your-zone-id
```

## API

### `POST /upload`

Multipart form upload。

Headers:

```http
Authorization: Bearer your-secret-key
```

Fields:

- `file`：必填，上传文件。
- `customPath`：可选，自定义 object key。

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

只有 `DELETE_MODE = "hard"` 时才会删除 R2 object。ByteGo 不维护服务端回收站。

Headers:

```http
Authorization: Bearer your-secret-key
Content-Type: application/json
```

Body:

```json
{ "key": "uploads/2026/05/21/abc123.png" }
```

## 排错

- `401 Unauthorized`：检查 `Authorization: Bearer ...` 和 `AUTH_KEY`。
- `AUTH_KEY not set`：线上运行 `npm run secret:put`，本地开发则检查 `.dev.vars`。
- `PUBLIC_DOMAIN not set`：在 `wrangler.toml` 中配置 R2 public/custom domain。
- 上传后的 URL 打不开：确认 R2 public/custom domain 已绑定到同一个 bucket。
- 上传时 CORS 报错：把 Worker UI origin 加到 `CORS_ORIGINS`。
- 读取文件时 CORS 报错：检查 R2 bucket 的 `cors.json` 是否已应用。
- 新 clone 后类型检查失败：先运行 `npm install`。
- 看不到 Delete 按钮：设置 `DELETE_MODE` 为 `soft` 或 `hard` 后重新部署。

## License

MIT
