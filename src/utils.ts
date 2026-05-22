const DEFAULT_MAX_OBJECT_KEY_LENGTH = 1024;

export class ObjectKeyError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ObjectKeyError";
  }
}

export function generateRandomHex(length: number): string {
  const array = new Uint8Array(Math.ceil(length / 2));
  crypto.getRandomValues(array);
  return Array.from(array)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("")
    .slice(0, length);
}

export function sanitizeFilename(filename: string): string {
  const basename = filename.split("/").pop()?.split("\\").pop() || "file";
  const safeName = basename.replace(/[^a-zA-Z0-9._-]/g, "_");
  return safeName.replace(/^\.+$/, "_") || "file";
}

export function splitFilename(filename: string): {
  originName: string;
  originNameWithoutExt: string;
  ext: string;
} {
  const originName = sanitizeFilename(filename);
  const extIndex = originName.lastIndexOf(".");
  const hasExt = extIndex > 0 && extIndex < originName.length - 1;
  const ext = hasExt ? originName.substring(extIndex) : "";
  const originNameWithoutExt = hasExt
    ? originName.substring(0, extIndex)
    : originName;

  return { originName, originNameWithoutExt, ext };
}

export function parsePath(
  filename: string,
  format: string,
  now = new Date(),
): string {
  const year = now.getFullYear().toString();
  const month = (now.getMonth() + 1).toString().padStart(2, "0");
  const day = now.getDate().toString().padStart(2, "0");
  const hours = now.getHours().toString().padStart(2, "0");
  const minutes = now.getMinutes().toString().padStart(2, "0");
  const seconds = now.getSeconds().toString().padStart(2, "0");

  const dateStr = `${year}${month}${day}`;
  const timeStr = `${year}${month}${day}${hours}${minutes}${seconds}`;
  const timestamp = Math.floor(now.getTime() / 1000).toString();
  const timestampNano = (now.getTime() * 1000000).toString();
  const { originName, originNameWithoutExt, ext } = splitFilename(filename);

  let path = format;

  path = path.replace(/{year}/g, year);
  path = path.replace(/{month}/g, month);
  path = path.replace(/{day}/g, day);
  path = path.replace(/{date}/g, dateStr);
  path = path.replace(/{time}/g, timeStr);
  path = path.replace(/{timestamp}/g, timestamp);
  path = path.replace(/{timestamp_nano}/g, timestampNano);

  path = path.replace(/{originname}/g, originName);
  path = path.replace(/{originname_without_ext}/g, originNameWithoutExt);
  path = path.replace(/{ext}/g, ext);

  path = path.replace(/{randomkey8}/g, () => generateRandomHex(8));
  path = path.replace(/{randomkey16}/g, () => generateRandomHex(16));
  path = path.replace(/{uuid}/g, () => crypto.randomUUID());

  return path;
}

export function normalizeObjectKey(
  input: string,
  options: {
    rootPrefix?: string;
    maxLength?: number;
  } = {},
): string {
  const maxLength = options.maxLength ?? DEFAULT_MAX_OBJECT_KEY_LENGTH;
  const key = normalizePathSegments(input, "Object key");
  const rootPrefix = options.rootPrefix
    ? normalizePathSegments(options.rootPrefix, "Upload root prefix")
    : "";

  const normalized =
    rootPrefix && key !== rootPrefix && !key.startsWith(`${rootPrefix}/`)
      ? `${rootPrefix}/${key}`
      : key;

  if (normalized.length > maxLength) {
    throw new ObjectKeyError(`Object key must be ${maxLength} characters or less`);
  }

  return normalized;
}

export function buildPublicUrl(publicDomain: string, objectKey: string): string {
  const domain = publicDomain.trim().replace(/\/+$/, "");
  if (!domain) {
    throw new Error("PUBLIC_DOMAIN is not configured");
  }

  const encodedKey = objectKey
    .split("/")
    .map((segment) => encodeURIComponent(segment))
    .join("/");

  return `${domain}/${encodedKey}`;
}

function normalizePathSegments(input: string, label: string): string {
  if (typeof input !== "string") {
    throw new ObjectKeyError(`${label} must be a string`);
  }

  const trimmed = input.trim().replace(/\\/g, "/").replace(/\/+/g, "/");
  const withoutEdges = trimmed.replace(/^\/+|\/+$/g, "");

  if (!withoutEdges) {
    throw new ObjectKeyError(`${label} cannot be empty`);
  }

  if (/[\u0000-\u001f\u007f?#]/.test(withoutEdges)) {
    throw new ObjectKeyError(`${label} contains unsupported URL characters`);
  }

  const segments = withoutEdges.split("/");
  if (segments.some((segment) => segment === "." || segment === ".." || !segment)) {
    throw new ObjectKeyError(`${label} contains an unsafe path segment`);
  }

  return segments.join("/");
}
