import { Hono } from "hono";
import { cors } from "hono/cors";
import htmlContent from "./index.html";
import { parsePath } from "./utils";

type Bindings = {
  BUCKET: R2Bucket;
  AUTH_KEY: string;
  PUBLIC_DOMAIN: string;
  UPLOAD_PATH_FORMAT: string;
  CORS_ORIGINS: string;
  APP_TITLE: string;
};

const app = new Hono<{ Bindings: Bindings }>();

// Enable CORS
app.use("/*", async (c, next) => {
  const corsMiddleware = cors({
    origin: (origin) => {
      const allowedOrigins = (c.env.CORS_ORIGINS || "").split(",");
      return allowedOrigins.includes(origin) ? origin : allowedOrigins[0];
    },
    allowMethods: ["POST", "GET", "OPTIONS"],
    allowHeaders: ["Content-Type", "Authorization"],
    exposeHeaders: ["Content-Length"],
    maxAge: 600,
    credentials: true,
  });
  return corsMiddleware(c, next);
});

// Home route, returns HTML interface
app.get("/", (c) => {
  const title = c.env.APP_TITLE || "ByteGo";
  return c.html(htmlContent.replace("{{APP_TITLE}}", title));
});

// Upload endpoint
app.post("/upload", async (c) => {
  const authKey = c.req.header("Authorization");

  // Check server configuration
  if (!c.env.AUTH_KEY) {
    return c.json({ msg: "Server configuration error: AUTH_KEY not set" }, 500);
  }

  // Auth check
  if (authKey !== c.env.AUTH_KEY) {
    return c.json({ msg: "Unauthorized: Invalid AUTH_KEY" }, 401);
  }

  try {
    const body = await c.req.parseBody();
    const file = body["file"];
    const customPath = body["customPath"]; // Allow client to specify custom path

    // Check if file exists
    if (!file || !(file instanceof File)) {
      return c.json({ msg: "No file uploaded" }, 400);
    }

    // Check file size (Worker limit ~100MB)
    if (file.size > 100 * 1024 * 1024) {
      return c.json({ msg: "File too large. Max size is 100MB" }, 413);
    }

    let path: string;
    if (typeof customPath === "string" && customPath.trim() !== "") {
      // Use custom path if provided
      // Simple sanitization to prevent absolute paths
      path = customPath.trim().replace(/^\/+/, "");
    } else {
      // Otherwise use default format
      const format =
        c.env.UPLOAD_PATH_FORMAT || "{year}/{month}/{day}/{randomkey16}{ext}";
      path = parsePath(file.name, format);
    }

    // Ensure path doesn't start with /
    if (path.startsWith("/")) {
      path = path.substring(1);
    }

    // Upload to R2
    await c.env.BUCKET.put(path, file.stream(), {
      httpMetadata: {
        contentType: file.type || "application/octet-stream", // Ensure Content-Type is present
      },
      customMetadata: {
        originalName: file.name,
        uploadedAt: new Date().toISOString(),
        uploaderIp: c.req.header("CF-Connecting-IP") || "unknown",
      },
    });

    // Build return URL
    // Prefer env var domain
    const publicDomain = (c.env.PUBLIC_DOMAIN || "").replace(/\/$/, "");
    const url = `${publicDomain}/${path}`;

    return c.json({
      msg: "success",
      url: url,
    });
  } catch (e) {
    console.error("Upload error:", e);
    return c.json({ msg: "Upload failed", error: String(e) }, 500);
  }
});

export default app;
