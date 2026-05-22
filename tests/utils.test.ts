import assert from "node:assert/strict";
import test from "node:test";
import {
  buildPublicUrl,
  normalizeObjectKey,
  ObjectKeyError,
  parsePath,
  splitFilename,
} from "../src/utils";

test("parsePath replaces filename, date, random, and uuid variables", () => {
  const now = new Date(2026, 4, 21, 3, 4, 5);
  const path = parsePath(
    "demo image.png",
    "{year}/{month}/{day}/{date}/{time}/{timestamp}/{originname}/{originname_without_ext}/{randomkey8}/{randomkey16}/{uuid}{ext}",
    now,
  );

  assert.match(
    path,
    /^2026\/05\/21\/20260521\/20260521030405\/\d+\/demo_image\.png\/demo_image\/[a-f0-9]{8}\/[a-f0-9]{16}\/[0-9a-f-]{36}\.png$/,
  );
});

test("filename parts are derived from the sanitized basename", () => {
  assert.deepEqual(splitFilename("../a b/图像.final.png"), {
    originName: "__.final.png",
    originNameWithoutExt: "__.final",
    ext: ".png",
  });
});

test("normalizeObjectKey cleans safe slashes and applies a root prefix", () => {
  assert.equal(
    normalizeObjectKey(" /2026//05/demo.png ", { rootPrefix: "uploads/" }),
    "uploads/2026/05/demo.png",
  );
  assert.equal(
    normalizeObjectKey("uploads/2026/05/demo.png", { rootPrefix: "uploads" }),
    "uploads/2026/05/demo.png",
  );
});

test("normalizeObjectKey rejects dangerous object keys", () => {
  const badKeys = [
    "../demo.png",
    "a/../demo.png",
    "a/./demo.png",
    "a?version=1",
    "a#hash",
    "\u0000demo.png",
  ];

  for (const key of badKeys) {
    assert.throws(() => normalizeObjectKey(key), ObjectKeyError);
  }
});

test("buildPublicUrl trims the domain and encodes path segments", () => {
  assert.equal(
    buildPublicUrl("https://cdn.example.com/", "uploads/a b/demo safe.png"),
    "https://cdn.example.com/uploads/a%20b/demo%20safe.png",
  );
});

test("normalizeObjectKey rejects empty root prefixes and unsafe root segments", () => {
  assert.throws(
    () => normalizeObjectKey("demo.png", { rootPrefix: "../uploads" }),
    ObjectKeyError,
  );
  assert.throws(
    () => normalizeObjectKey("demo.png", { rootPrefix: " " }),
    ObjectKeyError,
  );
});

test("buildPublicUrl rejects blank public domains", () => {
  assert.throws(() => buildPublicUrl("   ", "uploads/demo.png"));
});
