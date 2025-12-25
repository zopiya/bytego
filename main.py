import logging
import logging.handlers
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
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from flask import Flask, g, jsonify, request, send_file
from werkzeug.utils import secure_filename

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
S3_ENDPOINT = os.getenv("S3_ENDPOINT")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY")
S3_BUCKET = os.getenv("S3_BUCKET")
# Default path template
S3_PATH_TEMPLATE = os.getenv(
    "S3_PATH_TEMPLATE",
    "{year}/{month}/{day}/{originname_without_ext}-{randomkey8}{ext}",
)
PUBLIC_DOMAIN = os.getenv("PUBLIC_DOMAIN", "").rstrip("/")
AUTH_KEY = os.getenv("AUTH_KEY")

# Validate required environment variables
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

# --- Flask Initialization ---
app = Flask(__name__, static_folder=None)

# File upload size limit (default 100MB)
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE_MB", "100")) * 1024 * 1024
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE

# S3 ACL Configuration
S3_ACL = os.getenv("S3_ACL", "public-read")
# S3 Addressing Style (auto, virtual, path)
S3_ADDRESSING_STYLE = os.getenv("S3_ADDRESSING_STYLE", "auto")

# --- Logging Configuration ---
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
log_to_file = os.getenv("LOG_TO_FILE", "false").lower() == "true"
log_dir = os.getenv("LOG_DIR", "logs")
log_max_bytes = int(os.getenv("LOG_MAX_BYTES", "10485760"))  # Default 10MB
log_backup_count = int(os.getenv("LOG_BACKUP_COUNT", "5"))

# Configure handlers
handlers = [logging.StreamHandler()]  # Always log to stdout

if log_to_file:
    # Ensure log directory exists
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    # Add RotatingFileHandler
    file_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(log_dir, "bytego.log"),
        maxBytes=log_max_bytes,
        backupCount=log_backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    handlers.append(file_handler)

# Apply configuration
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=handlers,
    force=True,  # Overwrite any existing config
)
logger = app.logger

# Check PUBLIC_DOMAIN
if not PUBLIC_DOMAIN:
    logger.warning(
        "PUBLIC_DOMAIN not set. URLs will use S3_ENDPOINT which may not be optimal."
    )
    PUBLIC_DOMAIN = S3_ENDPOINT

# --- In-Memory Storage ---
# Ban pool: {ip: {'attempts': 0, 'ban_until': timestamp}}
security_store = defaultdict(lambda: {"attempts": 0, "ban_until": 0})

# --- S3 Client Initialization ---
# Global client for connection reuse
s3_client = None


def get_s3_client() -> BaseClient:
    """Get or create global S3 client instance (Singleton).

    Returns:
        boto3.client: Configured S3 client instance
    """
    global s3_client
    if s3_client is None:
        s3_client = boto3.client(
            "s3",
            endpoint_url=S3_ENDPOINT,
            aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY,
            config=boto3.session.Config(s3={"addressing_style": S3_ADDRESSING_STYLE}),
        )
    return s3_client


# --- Core Helper Functions ---


@app.before_request
def before_request():
    """Generate unique ID for each request for log tracking."""
    g.request_id = str(uuid.uuid4())[:8]
    logger.info(
        f"[{g.request_id}] {request.method} {request.path} from {request.remote_addr}"
    )


@app.after_request
def after_request(response):
    """Log response status."""
    if hasattr(g, "request_id"):
        logger.info(f"[{g.request_id}] Response: {response.status_code}")
    response.headers["X-Request-ID"] = getattr(g, "request_id", "unknown")
    return response


@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle file too large error."""
    max_size_mb = MAX_FILE_SIZE / (1024 * 1024)
    return jsonify({"msg": f"File too large. Maximum size: {max_size_mb}MB"}), 413


@app.errorhandler(500)
def internal_error(error):
    """Handle internal server error."""
    logger.error(f"Internal server error: {str(error)}", exc_info=True)
    return jsonify({"msg": "Internal server error"}), 500


def generate_s3_key(filename: str, template: str) -> str:
    """
    Generates a unique S3 object key based on the provided template and filename.

    This function handles:
    1. Filename sanitization (removing unsafe characters).
    2. Variable substitution (timestamp, random keys, date components).
    3. Path normalization.

    Supported variables:
    - {randomkey16}, {randomkey8}: Random hex strings for uniqueness.
    - {timestamp}, {timestamp_nano}: Unix timestamps.
    - {originname}: Original filename (sanitized).
    - {originname_without_ext}: Original filename without extension (sanitized).
    - {ext}: File extension (including dot).
    - {date}, {datetime}, {year}, {month}, {day}: Date components.

    Args:
        filename (str): The original filename uploaded by the user.
        template (str): The path template string.

    Returns:
        str: The generated S3 object key (path).
    """
    now = datetime.now()
    original_name = os.path.basename(filename)
    name_stem, ext = os.path.splitext(original_name)
    safe_stem = secure_filename(name_stem)
    if not safe_stem:
        safe_stem = "file"

    replacements = {
        "{randomkey16}": lambda: secrets.token_hex(8),
        "{randomkey8}": lambda: secrets.token_hex(4),
        "{timestamp}": lambda: str(int(time.time())),
        "{timestamp_nano}": lambda: str(time.time_ns()),
        "{originname}": lambda: secure_filename(original_name),
        "{originname_without_ext}": lambda: safe_stem,
        "{ext}": lambda: ext,
        "{date}": lambda: now.strftime("%Y%m%d"),
        "{datetime}": lambda: now.strftime("%Y%m%d%H%M%S"),
        "{year}": lambda: now.strftime("%Y"),
        "{month}": lambda: now.strftime("%m"),
        "{day}": lambda: now.strftime("%d"),
    }

    result = template
    for key, func in replacements.items():
        if key in result:
            result = result.replace(key, func())

    # Clean up path: remove leading/trailing slashes and duplicate slashes
    return result.strip("/")


def verify_auth(client_ip: str, provided_key: Optional[str]) -> Tuple[bool, str]:
    """
    Verifies the client's access key and enforces IP-based rate limiting.

    Security Policy:
    - 3 consecutive failed attempts result in a 1-hour ban for the IP.
    - Uses constant-time comparison (secrets.compare_digest) to prevent timing attacks.
    - Clears the failure record immediately upon successful verification.
    - Occasionally cleans up expired ban records to prevent memory leaks.

    Args:
        client_ip (str): The IP address of the client.
        provided_key (Optional[str]): The access key provided in the request header.

    Returns:
        Tuple[bool, str]: A tuple containing:
            - bool: True if authentication is successful, False otherwise.
            - str: A message describing the result (e.g., "OK", "Invalid Access Key", "Banned...").
    """
    now = time.time()

    # Periodic cleanup (1% chance) to prevent memory leaks
    if secrets.randbelow(100) == 0:
        expired_ips = [
            ip
            for ip, data in security_store.items()
            if data["ban_until"] < now and data["attempts"] == 0
        ]
        for ip in expired_ips:
            del security_store[ip]

    record = security_store[client_ip]

    # 1. Check ban status
    if now < record["ban_until"]:
        remaining = int((record["ban_until"] - now) / 60)
        return False, f"Too many attempts. Banned for {remaining} mins."

    # 2. Verify Key
    # Use constant-time comparison to protect against timing attacks
    if provided_key and AUTH_KEY and secrets.compare_digest(provided_key, AUTH_KEY):
        # Clear error record on success to reset the counter
        if client_ip in security_store:
            del security_store[client_ip]
        return True, "OK"

    # 3. Handle Failure
    record["attempts"] += 1
    if record["attempts"] >= 3:
        record["ban_until"] = int(now + 3600)  # Ban for 1 hour
        record["attempts"] = 0  # Reset attempts
        logger.warning(f"IP {client_ip} banned due to invalid key attempts.")
        return False, "Too many attempts. Banned for 1 hour."

    return False, "Invalid Access Key"


# --- Routes ---


@app.route("/")
def index():
    # Serve index.html directly
    return send_file("index.html")


@app.route("/health")
def health_check():
    """Health check endpoint for orchestration."""
    try:
        # Verify S3 connection
        s3 = get_s3_client()
        # Use list_objects_v2 for better compatibility than head_bucket
        s3.list_objects_v2(Bucket=S3_BUCKET, MaxKeys=1)
        return jsonify({"status": "healthy", "s3": "connected"}), 200
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({"status": "unhealthy", "error": "S3 connection failed"}), 503


@app.route("/upload", methods=["POST"])
def upload_file():
    # 1. Get IP and Key
    # Support reverse proxy (Nginx/Cloudflare)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()
    else:
        client_ip = request.remote_addr or "unknown"

    key = request.headers.get("Authorization")

    # Check Authorization header
    if not key:
        return jsonify({"msg": "Authorization header required"}), 401

    if not AUTH_KEY:
        return jsonify({"msg": "Server Error: AUTH_KEY not configured"}), 500

    # 2. Security Check
    is_valid, msg = verify_auth(client_ip, key)
    if not is_valid:
        # Return 403 for banned, 401 for invalid key
        status_code = 403 if "Banned" in msg else 401
        return jsonify({"msg": msg}), status_code

    # 3. File Check
    if "file" not in request.files:
        return jsonify({"msg": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "" or not file.filename:
        return jsonify({"msg": "No selected file"}), 400

    try:
        # 4. Generate S3 Path
        s3_path = generate_s3_key(file.filename, S3_PATH_TEMPLATE)

        # Get file size for logging and S3 Content-Length header
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)  # Reset pointer to beginning

        # 5. Upload to S3
        # Use put_object with file object for streaming upload.
        # This avoids loading the entire file into memory (unlike Body=file.read())
        # and avoids "MissingContentLength" issues with upload_fileobj on some S3 providers.
        s3 = get_s3_client()

        upload_args = {
            "Bucket": S3_BUCKET,
            "Key": s3_path,
            "Body": file,
            "ContentLength": file_size,
            "ContentType": file.content_type or "application/octet-stream",
        }

        # Only add ACL if explicitly configured (some providers don't support it)
        if S3_ACL:
            upload_args["ACL"] = S3_ACL

        s3.put_object(**upload_args)

        # 6. Return Result
        final_url = f"{PUBLIC_DOMAIN}/{s3_path}"

        request_id = getattr(g, "request_id", "unknown")
        logger.info(
            f"[{request_id}] Upload success: {s3_path} ({file_size} bytes) by {client_ip}"
        )
        return jsonify({"msg": "success", "url": final_url})

    except ClientError as e:
        request_id = getattr(g, "request_id", "unknown")
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = e.response.get("Error", {}).get("Message", str(e))
        logger.error(
            f"[{request_id}] S3 Upload failed for {client_ip}: {error_code} - {error_msg}",
            exc_info=True,
        )
        return jsonify({"msg": f"Storage Error: {error_msg}"}), 502

    except Exception as e:
        # Log detailed error but return generic message to client
        request_id = getattr(g, "request_id", "unknown")
        logger.error(
            f"[{request_id}] Upload failed for {client_ip}: {str(e)}", exc_info=True
        )
        return jsonify({"msg": "Upload failed. Please try again."}), 500


if __name__ == "__main__":
    # Run in development mode
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
