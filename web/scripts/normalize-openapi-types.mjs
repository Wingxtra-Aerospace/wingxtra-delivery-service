import { readFileSync, writeFileSync } from "node:fs";

const filePath = new URL("../src/api/types.ts", import.meta.url);
const raw = readFileSync(filePath, "utf8");
const normalized = raw.replace(/^ \* Source: .*$/m, " * Source: <openapi-schema>");

if (normalized !== raw) {
  writeFileSync(filePath, normalized, "utf8");
}
