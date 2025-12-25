import hashlib
import logging
import os
import secrets
import time
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Optional, Tuple

# Third-party imports
import boto3
from botocore.client import BaseClient
from flask import Flask, g, jsonify, request, send_file
from werkzeug.utils import secure_filename

# --- 配置加载 (环境变量) ---
# 建议在 .env 文件中配置，或者通过 docker -e 注入
S3_ENDPOINT = os.getenv("S3_ENDPOINT")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY")
S3_BUCKET = os.getenv("S3_BUCKET")
# 如果没有配置 public domain，默认回退到 endpoint/bucket (不推荐)
PUBLIC_DOMAIN = os.getenv("PUBLIC_DOMAIN", "").rstrip("/")
AUTH_KEY = os.getenv("AUTH_KEY")  # 你的 64位 Key

# 验证必需的环境变量
REQUIRED_ENV_VARS = {
    "S3_ENDPOINT": S3_ENDPOINT,
    "S3_ACCESS_KEY": S3_ACCESS_KEY,
    "S3_SECRET_KEY": S3_SECRET_KEY,
    "S3_BUCKET": S3_BUCKET,
    "AUTH_KEY": AUTH_KEY,
}
missing_vars = [name for name, value in REQUIRED_ENV_VARS.items() if not value]
if missing_vars:
    raise RuntimeError(
        f"Missing required environment variables: {', '.join(missing_vars)}. "
        "Please set them before starting the application."
    )

# --- 初始化 Flask ---
app = Flask(__name__, static_folder=None)

# 配置文件上传大小限制 (默认 100MB)
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE_MB", "100")) * 1024 * 1024
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE

# S3 ACL 配置
S3_ACL = os.getenv("S3_ACL", "public-read")

# 设置日志
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = app.logger

# 检查 PUBLIC_DOMAIN 配置
if not PUBLIC_DOMAIN:
    logger.warning(
        "PUBLIC_DOMAIN not set. URLs will use S3_ENDPOINT which may not be optimal."
    )
    PUBLIC_DOMAIN = S3_ENDPOINT

# --- 内存存储 (简易数据库) ---
# 封禁池: {ip: {'attempts': 0, 'ban_until': timestamp}}
security_store = defaultdict(lambda: {"attempts": 0, "ban_until": 0})

# --- S3 客户端初始化 ---
# 使用全局客户端以便复用连接
s3_client = None


def get_s3_client() -> BaseClient:
    """获取或创建全局 S3 客户端实例（单例模式）

    Returns:
        boto3.client: 配置好的 S3 客户端实例
    """
    global s3_client
    if s3_client is None:
        s3_client = boto3.client(
            "s3",
            endpoint_url=S3_ENDPOINT,
            aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY,
        )
    return s3_client


# --- 核心辅助函数 ---


@app.before_request
def before_request():
    """为每个请求生成唯一 ID，便于日志追踪"""
    g.request_id = str(uuid.uuid4())[:8]
    logger.info(
        f"[{g.request_id}] {request.method} {request.path} from {request.remote_addr}"
    )


@app.after_request
def after_request(response):
    """记录响应状态"""
    if hasattr(g, "request_id"):
        logger.info(f"[{g.request_id}] Response: {response.status_code}")
    response.headers["X-Request-ID"] = getattr(g, "request_id", "unknown")
    return response


@app.errorhandler(413)
def request_entity_too_large(error):
    """处理文件过大错误"""
    max_size_mb = MAX_FILE_SIZE / (1024 * 1024)
    return jsonify({"msg": f"File too large. Maximum size: {max_size_mb}MB"}), 413


@app.errorhandler(500)
def internal_error(error):
    """处理内部服务器错误"""
    logger.error(f"Internal server error: {str(error)}", exc_info=True)
    return jsonify({"msg": "Internal server error"}), 500


def smart_rename(filename: str, content_bytes: bytes) -> str:
    """
    智能重命名文件，确保唯一性和长度限制

    算法：
    1. 计算文件内容的 MD5 哈希（取前8位）用于去重
    2. 保留原始文件扩展名
    3. 截断文件名使总长度不超过 40 字符
    4. 格式：/YYYY/MM/DD/filename-hash.ext

    Args:
        filename: 原始文件名
        content_bytes: 文件内容字节

    Returns:
        str: S3 存储路径，格式为 YYYY/MM/DD/filename-hash.ext

    Example:
        >>> smart_rename("my_photo.png", b"...")
        '2024/12/25/my_photo-a1b2c3d4.png'
    """
    # 1. 基础拆分
    original_name = os.path.basename(filename)
    name_stem, ext = os.path.splitext(original_name)

    # 2. 计算 Hash (取前8位)
    file_hash = hashlib.md5(content_bytes).hexdigest()[:8]

    # 3. 计算允许的文件名主体长度
    # Formula: 40 - len(ext) - 8(hash) - 1(连字符)
    # 比如 .png (4 chars), hash (8), - (1) => 占用 13 chars
    # 剩余给文件名: 27 chars
    max_stem_len = 40 - len(ext) - 8 - 1

    # 如果后缀太长（极端情况），至少保留 hash
    if max_stem_len < 1:
        final_name = f"{file_hash}{ext}"
    else:
        # 安全截断，去除非法字符
        safe_stem = secure_filename(name_stem)[:max_stem_len]
        # 如果截断后为空（比如原文件名全是特殊字符），用 file 补位
        if not safe_stem:
            safe_stem = "file"
        final_name = f"{safe_stem}-{file_hash}{ext}"

    # 4. 构建时间路径
    date_path = datetime.now().strftime("%Y/%m/%d")
    full_path = f"{date_path}/{final_name}"

    return full_path


def verify_auth(client_ip: str, provided_key: Optional[str]) -> Tuple[bool, str]:
    """
    验证客户端的访问密钥并管理 IP 封禁

    安全策略：
    - 同一 IP 连续 3 次密钥错误将被封禁 1 小时
    - 使用恒定时间比较防止时序攻击
    - 验证成功后清除该 IP 的失败记录

    Args:
        client_ip: 客户端 IP 地址
        provided_key: 客户端提供的访问密钥

    Returns:
        Tuple[bool, str]: (验证是否通过, 消息)
            - (True, "OK") 表示验证通过
            - (False, "错误消息") 表示验证失败或被封禁

    Example:
        >>> verify_auth("192.168.1.1", "correct_key")
        (True, "OK")
        >>> verify_auth("192.168.1.1", "wrong_key")
        (False, "Invalid Access Key")
    """
    now = time.time()
    record = security_store[client_ip]

    # 1. 检查封禁状态
    if now < record["ban_until"]:
        remaining = int((record["ban_until"] - now) / 60)
        return False, f"Too many attempts. Banned for {remaining} mins."

    # 2. 校验 Key
    # 使用恒定时间比较防止时序攻击
    if provided_key and AUTH_KEY and secrets.compare_digest(provided_key, AUTH_KEY):
        # 验证成功，清除该 IP 的错误记录
        if client_ip in security_store:
            del security_store[client_ip]
        return True, "OK"

    # 3. 失败处理
    record["attempts"] += 1
    if record["attempts"] >= 3:
        record["ban_until"] = int(now + 3600)  # 封禁 1 小时 (3600秒)
        record["attempts"] = 0  # 重置计数，进入封禁期
        logger.warning(f"IP {client_ip} banned due to invalid key attempts.")
        return False, "Too many attempts. Banned for 1 hour."

    return False, "Invalid Access Key"


# --- 路由定义 ---


@app.route("/")
def index():
    # 直接读取当前目录下的 index.html
    return send_file("index.html")


@app.route("/health")
def health_check():
    """健康检查端点，用于容器编排和负载均衡器"""
    try:
        # 验证 S3 连接
        s3 = get_s3_client()
        s3.head_bucket(Bucket=S3_BUCKET)
        return jsonify({"status": "healthy", "s3": "connected"}), 200
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({"status": "unhealthy", "error": "S3 connection failed"}), 503


@app.route("/upload", methods=["POST"])
def upload_file():
    # 1. 获取 IP 和 Key
    # 支持反向代理(Nginx/Cloudflare)后获取真实 IP
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For 可能包含多个 IP，取第一个
        client_ip = forwarded_for.split(",")[0].strip()
    else:
        client_ip = request.remote_addr or "unknown"

    key = request.headers.get("Authorization")

    # 校验 Authorization header 是否存在
    if not key:
        return jsonify({"msg": "Authorization header required"}), 401

    if not AUTH_KEY:
        return jsonify({"msg": "Server Error: AUTH_KEY not configured"}), 500

    # 2. 安全检查
    is_valid, msg = verify_auth(client_ip, key)
    if not is_valid:
        # 如果是封禁状态返回 403，密钥错误返回 401
        status_code = 403 if "Banned" in msg else 401
        return jsonify({"msg": msg}), status_code

    # 3. 文件检查
    if "file" not in request.files:
        return jsonify({"msg": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "" or not file.filename:
        return jsonify({"msg": "No selected file"}), 400

    try:
        # 读取文件内容
        content = file.read()

        # 4. 生成新路径
        s3_path = smart_rename(file.filename, content)

        # 5. 上传 S3
        s3 = get_s3_client()
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=s3_path,
            Body=content,
            ContentType=file.content_type or "application/octet-stream",
            ACL=S3_ACL,
        )

        # 6. 返回结果
        final_url = f"{PUBLIC_DOMAIN}/{s3_path}"

        request_id = getattr(g, "request_id", "unknown")
        logger.info(
            f"[{request_id}] Upload success: {s3_path} ({len(content)} bytes) by {client_ip}"
        )
        return jsonify({"msg": "success", "url": final_url})

    except Exception as e:
        # 记录详细错误但不暴露给客户端
        request_id = getattr(g, "request_id", "unknown")
        logger.error(
            f"[{request_id}] Upload failed for {client_ip}: {str(e)}", exc_info=True
        )
        return jsonify({"msg": "Upload failed. Please try again."}), 500


if __name__ == "__main__":
    # 开发模式运行
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
