import fs from "fs";
import path from "path";
import { compileFromFile } from "json-schema-to-typescript";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const schemaPath = path.resolve(__dirname, "../../docs/schema.json");
const outputPath = path.resolve(__dirname, "../src/types/candidates.ts");

async function generate() {
  console.log(`Compiling TypeScript types from schema: ${schemaPath}`);
  const ts = await compileFromFile(schemaPath, {
    bannerComment:
      "/* tslint:disable */\n/**\n * Auto-generated from docs/schema.json via `npm run gen:types`.\n * DO NOT EDIT DIRECTLY.\n */",
  });
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, ts, "utf-8");
  console.log(`Generated typed contract at: ${outputPath}`);
}

generate().catch((err) => {
  console.error("Type generation failed:", err);
  process.exit(1);
});
