import { Hono } from "hono";
import type { Context } from "hono";
import { cors } from "hono/cors";
import htmlContent from "./index.html";
import {
  buildPublicUrl,
  normalizeObjectKey,
  ObjectKeyError,
  parsePath,
} from "./utils";

type Bindings = {
  BUCKET: R2Bucket;
  AUTH_KEY?: string;
  PUBLIC_DOMAIN?: string;
  UPLOAD_PATH_FORMAT?: string;
  CORS_ORIGINS?: string;
  APP_TITLE?: string;
  UPLOAD_ROOT_PREFIX?: string;
  DELETE_MODE?: string;
};

const app = new Hono<{ Bindings: Bindings }>();

app.use("/*", async (c, next) => {
  const corsMiddleware = cors({
    origin: (origin) => {
      const allowedOrigins = parseAllowedOrigins(c.env.CORS_ORIGINS);
      if (!origin) {
        return allowedOrigins[0] || "";
      }
      return allowedOrigins.includes(origin) ? origin : "";
    },
    allowMethods:
      getDeleteMode(c.env.DELETE_MODE) === "hard"
        ? ["POST", "DELETE", "GET", "OPTIONS"]
        : ["POST", "GET", "OPTIONS"],
    allowHeaders: ["Content-Type", "Authorization"],
    exposeHeaders: ["Content-Length"],
    maxAge: 600,
  });
  return corsMiddleware(c, next);
});

// Home route, returns HTML interface
app.get("/", (c) => {
  const title = escapeHtml(c.env.APP_TITLE || "ByteGo");
  const deleteMode = getDeleteMode(c.env.DELETE_MODE);
  setHtmlSecurityHeaders(c);
  return c.html(
    htmlContent
      .replaceAll("{{APP_TITLE}}", title)
      .replaceAll("{{DELETE_MODE}}", deleteMode),
  );
});

// Upload endpoint
app.post("/upload", async (c) => {
  const authError = checkAuth(c.req.header("Authorization"), c.env.AUTH_KEY);
  if (authError) {
    return c.json({ msg: authError.message }, authError.status);
  }

  const publicDomain = c.env.PUBLIC_DOMAIN?.trim();
  if (!publicDomain) {
    return c.json({ msg: "Server configuration error: PUBLIC_DOMAIN not set" }, 500);
  }

  try {
    const body = await c.req.parseBody();
    const file = body["file"];
    const customPath = body["customPath"];

    if (!file || !(file instanceof File)) {
      return c.json({ msg: "No file uploaded" }, 400);
    }

    if (file.size > 100 * 1024 * 1024) {
      return c.json({ msg: "File too large. Max size is 100MB" }, 413);
    }

    const format =
      c.env.UPLOAD_PATH_FORMAT || "{year}/{month}/{day}/{randomkey16}{ext}";
    const rawPath =
      typeof customPath === "string" && customPath.trim() !== ""
        ? customPath
        : parsePath(file.name, format);
    const key = normalizeObjectKey(rawPath, {
      rootPrefix: c.env.UPLOAD_ROOT_PREFIX,
    });
    const uploadedAt = new Date().toISOString();
    const contentType = file.type || "application/octet-stream";

    await c.env.BUCKET.put(key, file.stream(), {
      httpMetadata: {
        contentType,
      },
      customMetadata: {
        originalName: file.name,
        uploadedAt,
        uploaderIp: c.req.header("CF-Connecting-IP") || "unknown",
      },
    });

    const url = buildPublicUrl(publicDomain, key);

    return c.json({
      msg: "success",
      key,
      url,
      filename: file.name,
      size: file.size,
      contentType,
      uploadedAt,
    });
  } catch (e) {
    console.error("Upload error:", e);
    if (e instanceof ObjectKeyError) {
      return c.json({ msg: e.message }, 400);
    }
    return c.json({ msg: "Upload failed" }, 500);
  }
});

app.delete("/object", async (c) => {
  if (getDeleteMode(c.env.DELETE_MODE) !== "hard") {
    return c.json({ msg: "R2 delete is disabled" }, 403);
  }

  const authError = checkAuth(c.req.header("Authorization"), c.env.AUTH_KEY);
  if (authError) {
    return c.json({ msg: authError.message }, authError.status);
  }

  try {
    const body = (await c.req.json().catch(() => null)) as { key?: unknown } | null;
    if (!body || typeof body.key !== "string") {
      return c.json({ msg: "Object key is required" }, 400);
    }

    const key = normalizeObjectKey(body.key, {
      rootPrefix: c.env.UPLOAD_ROOT_PREFIX,
    });

    await c.env.BUCKET.delete(key);
    return c.json({
      msg: "success",
      key,
      deletedAt: new Date().toISOString(),
    });
  } catch (e) {
    console.error("Delete error:", e);
    if (e instanceof ObjectKeyError) {
      return c.json({ msg: e.message }, 400);
    }
    return c.json({ msg: "Delete failed" }, 500);
  }
});

function parseAllowedOrigins(origins: string | undefined): string[] {
  return (origins || "")
    .split(",")
    .map((origin) => origin.trim())
    .filter(Boolean);
}

function checkAuth(
  authorization: string | undefined,
  expected: string | undefined,
): { message: string; status: 401 | 500 } | null {
  if (!expected) {
    return { message: "Server configuration error: AUTH_KEY not set", status: 500 };
  }

  const token = authorization?.startsWith("Bearer ")
    ? authorization.slice("Bearer ".length).trim()
    : authorization;

  if (!token || token !== expected) {
    return { message: "Unauthorized", status: 401 };
  }

  return null;
}

function getDeleteMode(mode: string | undefined): "none" | "soft" | "hard" {
  if (mode === "soft" || mode === "hard") {
    return mode;
  }
  return "none";
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (char) => {
    switch (char) {
      case "&":
        return "&amp;";
      case "<":
        return "&lt;";
      case ">":
        return "&gt;";
      case '"':
        return "&quot;";
      case "'":
        return "&#39;";
      default:
        return char;
    }
  });
}

function setHtmlSecurityHeaders(c: Context<{ Bindings: Bindings }>): void {
  c.header("X-Content-Type-Options", "nosniff");
  c.header("Referrer-Policy", "no-referrer");
  c.header("Permissions-Policy", "camera=(), microphone=(), geolocation=()");
  c.header(
    "Content-Security-Policy",
    [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline'",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: blob: https:",
      "connect-src 'self'",
      "object-src 'none'",
      "base-uri 'none'",
      "frame-ancestors 'none'",
      "form-action 'none'",
    ].join("; "),
  );
}

export default app;
