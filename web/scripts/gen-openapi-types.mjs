import { spawnSync } from "node:child_process";

const source = process.env.VITE_API_BASE_URL || "http://localhost:8000";
const schemaUrl = `${source}/openapi.json`;

const run = spawnSync(
  "openapi-typescript",
  [schemaUrl, "--output", "src/api/types.ts"],
  {
    stdio: "inherit",
    shell: true,
  },
);

if (run.status !== 0) {
  if (run.status === 127) {
    console.warn(
      "[gen:types] openapi-typescript not found in PATH. Install web dependencies before generating types.",
    );
    process.exit(0);
  }
  process.exit(run.status ?? 1);
}

const normalize = spawnSync("node", ["scripts/normalize-openapi-types.mjs"], {
  stdio: "inherit",
  shell: true,
});

process.exit(normalize.status ?? 1);
