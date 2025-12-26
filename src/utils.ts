/**
 * Generate random hex string of specified length
 * @param length Length of string
 * @returns Random hex string
 */
export function generateRandomHex(length: number): string {
  const array = new Uint8Array(Math.ceil(length / 2));
  crypto.getRandomValues(array);
  return Array.from(array)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("")
    .slice(0, length);
}

/**
 * Parse and generate file path based on format string
 * @param filename Original filename
 * @param format Path format template
 * @returns Generated path
 */
export function parsePath(filename: string, format: string): string {
  const now = new Date();
  const year = now.getFullYear().toString();
  const month = (now.getMonth() + 1).toString().padStart(2, "0");
  const day = now.getDate().toString().padStart(2, "0");
  const hours = now.getHours().toString().padStart(2, "0");
  const minutes = now.getMinutes().toString().padStart(2, "0");
  const seconds = now.getSeconds().toString().padStart(2, "0");

  const dateStr = `${year}${month}${day}`;
  const timeStr = `${year}${month}${day}${hours}${minutes}${seconds}`;
  const timestamp = Math.floor(now.getTime() / 1000).toString();
  // JS lacks nanosecond precision, simulating with microseconds
  const timestampNano = (now.getTime() * 1000000).toString();

  const extIndex = filename.lastIndexOf(".");
  const ext = extIndex !== -1 ? filename.substring(extIndex) : "";

  // Sanitize filename:
  // 1. Remove path separators to prevent directory traversal
  // 2. Replace URL-unfriendly characters
  let safeFilename = filename.split("/").pop()?.split("\\").pop() || filename;
  safeFilename = safeFilename.replace(/[^a-zA-Z0-9._-]/g, "_"); // Keep only alphanumeric, dots, underscores, hyphens

  const originName = safeFilename;
  const originNameWithoutExt =
    extIndex !== -1
      ? safeFilename.substring(0, safeFilename.lastIndexOf("."))
      : safeFilename;

  let path = format;

  // Replace time variables
  path = path.replace(/{year}/g, year);
  path = path.replace(/{month}/g, month);
  path = path.replace(/{day}/g, day);
  path = path.replace(/{date}/g, dateStr);
  path = path.replace(/{time}/g, timeStr);
  path = path.replace(/{timestamp}/g, timestamp);
  path = path.replace(/{timestamp_nano}/g, timestampNano);

  // Replace filename variables
  path = path.replace(/{originname}/g, originName);
  path = path.replace(/{originname_without_ext}/g, originNameWithoutExt);
  path = path.replace(/{ext}/g, ext);

  // Replace random variables
  // Use callback to ensure unique random numbers per match
  path = path.replace(/{randomkey8}/g, () => generateRandomHex(8));
  path = path.replace(/{randomkey16}/g, () => generateRandomHex(16));

  // Support UUID
  path = path.replace(/{uuid}/g, () => crypto.randomUUID());

  return path;
}
