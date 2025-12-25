# ByteGo 📦

**ByteGo** 是一个极简的自托管二进制资产管理器，旨在将内容（Markdown）与资源（图片、PDF、附件）解耦。支持通过粘贴、拖拽或点击上传文件，并立即获得永久的 CDN 链接，方便嵌入到博客、Wiki 或笔记中。

## ✨ 特性

- 🎯 **极简上传**: 支持粘贴 (Ctrl+V)、拖拽或点击上传，一次最多支持 10 个文件。
- 🚀 **高性能**: 前端串行上传 + 后端流式传输，极低内存占用，轻松处理大文件。
- 🔐 **安全设计**: 基于 Access Key 的鉴权，配合 IP 速率限制（3 次失败封禁 1 小时）。
- 🗂️ **智能命名**: 自动基于 MD5 去重，支持自定义路径模板。
- 📂 **有序存储**: 基于日期的 S3 路径 (`YYYY/MM/DD/filename-hash.ext`)。
- 🔗 **多格式导出**: 一键复制原始 URL、Markdown 或 HTML 格式。
- 📜 **持久化历史**: 本地存储最近 10 条上传记录。
- 📝 **日志管理**: 支持日志持久化与自动分割（Log Rotation）。
- 🐳 **Docker 优先**: 单镜像部署，内置健康检查。

## 🏗️ 架构

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│   Browser   │─────▶│   ByteGo    │─────▶│   S3/CDN    │
│  (Vanilla)  │      │  (Flask)    │      │  (Storage)  │
└─────────────┘      └─────────────┘      └─────────────┘
```

- **前端**: 单文件 HTML (无框架)，100% 原生 JavaScript。
- **后端**: Flask + Boto3，支持所有兼容 S3 的存储（AWS S3, Cloudflare R2, MinIO, 腾讯云 COS, 阿里云 OSS 等）。
- **存储**: 任意兼容 S3 的对象存储。

## 🚀 快速开始

### 前置要求

- Docker & Docker Compose
- 兼容 S3 的对象存储服务
- 用于鉴权的 Access Key (可通过 `openssl rand -hex 32` 生成)

### 1. 克隆仓库

```bash
git clone https://github.com/yourusername/bytego.git
cd bytego
```

### 2. 配置环境

复制示例配置文件并填入你的信息：

```bash
cp .env.example .env
nano .env  # 编辑填入你的配置
```

**核心配置项:**

```env
S3_ENDPOINT=https://cos.ap-beijing.myqcloud.com
S3_ACCESS_KEY=your_access_key
S3_SECRET_KEY=your_secret_key
S3_BUCKET=your-bucket-name
PUBLIC_DOMAIN=https://cdn.example.com
AUTH_KEY=sk_live_your_secret_key
```

### 3. 启动服务

```bash
docker-compose up -d
```

服务将在 `http://localhost:8000` 启动。

### 4. 开始使用

打开浏览器访问 `http://localhost:8000`。首次访问需输入 `AUTH_KEY`。

## 📖 使用指南

### 上传文件

1. **粘贴**: 截图或复制文件后，在页面按 `Ctrl+V`。
2. **拖拽**: 将文件拖入上传区域。
3. **点击**: 点击上传区域选择文件。

### 获取链接

上传成功后，点击右侧按钮：

- **Link**: 原始 CDN 链接
- **MD**: Markdown 格式 (`![](...)`)
- **HTML**: HTML 标签 (`<img src="..." />`)

### 批量上传

支持一次上传 10 个文件。前端会自动串行处理，上传完成后自动将所有成功链接复制到剪贴板。

## 🔧 配置说明

### 环境变量

| 变量名          | 必填 | 默认值      | 说明                          |
| :-------------- | :--- | :---------- | :---------------------------- |
| `S3_ENDPOINT`   | ✅   | -           | S3 API 端点                   |
| `S3_ACCESS_KEY` | ✅   | -           | S3 Access Key ID              |
| `S3_SECRET_KEY` | ✅   | -           | S3 Secret Access Key          |
| `S3_BUCKET`     | ✅   | -           | 存储桶名称                    |
| `AUTH_KEY`      | ✅   | -           | 访问密码 (建议 64 位随机字符) |
| `PUBLIC_DOMAIN` | ❌   | S3_ENDPOINT | 公网访问域名 (CDN)            |
| `LOG_TO_FILE`   | ❌   | false       | 是否开启日志持久化            |
| `LOG_DIR`       | ❌   | logs        | 日志存储目录                  |

## 📄 许可证

MIT License
