ByteGo - Requirements, Product & Design (RPD)

1. 项目背景与目标 (Context & Goals)

1.1 背景

个人知识库（Blog, Wiki, Notes）中的二进制文件（图片、PDF、附件）目前分散存储在本地或各个仓库中。
痛点：

迁移困难：更换操作系统或笔记软件时，本地相对路径容易失效。

管理混乱：文件命名随意，缺乏统一归档。

同步繁琐：多端编辑时需要同步庞大的 assets 文件夹。

1.2 目标

构建 ByteGo，一个私有化、极简的二进制文件上传与管理中心。

核心价值：实现“内容（Markdown）”与“资源（Binaries）”的完全解耦。

最终效果：上传文件 -> 自动重命名/归档 -> 上传至对象存储 (S3) -> 返回永久 CDN 链接。

2. 功能需求 (Functional Requirements)

2.1 前端 (Frontend)

架构：单文件 HTML5 (No Framework, Vanilla JS)，追求极致加载速度与易部署性。

鉴权交互：

首次访问弹出模态窗 (Modal) 要求输入 Access Key (64-bit)。

Key 存储于 LocalStorage，后续自动填充。

提供隐藏入口用于更换 Key。

上传交互：

全屏响应：支持 Ctrl+V 粘贴上传（读取剪贴板）。

拖拽上传：支持文件拖入指定区域。

点击上传：传统文件选择器。

批量处理：单次支持最多 10 个文件并发上传。

反馈与历史：

状态反馈：上传中动画、成功/失败提示。

历史记录：显示最近 10 条上传记录。

多格式复制：针对每条记录，提供三种复制按钮：

Link: 原始 URL (https://...)

MD: Markdown 格式 (![](...))

HTML: HTML 标签 (<img src="..." />)

批量复制：多文件上传完成后，自动将所有链接（换行分隔）写入剪贴板。

2.2 后端 (Backend)

架构：Python (Flask) + Boto3。无数据库（NoSQL/SQL），利用内存做临时状态存储。

API 接口：

POST /upload: 接收 multipart/form-data，Header 携带 Authorization。

GET /: 返回前端静态页面。

核心逻辑 - 智能重命名 (Smart Rename)：

Hash 计算：计算文件内容的 MD5，截取前 8 位 用于去重。

长度限制：文件名（含后缀）总长不超过 40 字符。

截断策略：{原文件名截断}-{Hash}.{后缀}。

归档路径：/YYYY/MM/DD/{filename}。

核心逻辑 - 安全风控 (Security)：

认证：比对 Header 中的 Key 与环境变量 AUTH_KEY。

封禁策略：同一 IP 连续输错 3 次 Key，封禁该 IP 1 小时 (内存记录)。

2.3 存储层 (Storage Layer)

支持通用 S3 协议（AWS S3, Cloudflare R2, Aliyun OSS, MinIO）。

全环境变量配置，不依赖本地配置文件。

3. 非功能需求 (Non-Functional Requirements)

3.1 性能 (Performance)

启动速度：容器启动时间 < 3 秒。

并发：支持多线程处理上传请求（Gunicorn Worker）。

3.2 可维护性 (Maintainability)

部署：Docker 容器化，单镜像交付。

配置：符合 12-Factor App 原则，所有配置通过环境变量注入。

依赖管理：使用 uv 进行现代化的 Python 包管理。

3.3 界面设计 (UI/UX)

风格：ByteGo 极简风。

配色：

背景：#f0f2f5 (浅灰)

主色：#000000 (黑)

强调色：#0071e3 (蓝)

响应式：完美适配移动端（手机浏览器上传截图）和桌面端。

4. 数据结构与算法 (Data & Algorithms)

4.1 环境变量定义

S3*ENDPOINT="https://..."
S3_ACCESS_KEY="..."
S3_SECRET_KEY="..."
S3_BUCKET="..."
PUBLIC_DOMAIN="[https://cdn.example.com](https://cdn.example.com)"
AUTH_KEY="sk_live*..."

4.2 文件重命名伪代码

def rename(file):
hash = md5(file.content)[:8]
ext = file.ext
max_stem = 40 - len(ext) - 9 # 9 = len("-") + len(hash)
stem = file.stem[:max_stem]
return f"{date}/{stem}-{hash}{ext}"
