import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "../../");
const srcData = path.resolve(repoRoot, "data/output");
const targetData = path.resolve(__dirname, "../public/data");

function copyRecursive(src, dest) {
  if (!fs.existsSync(src)) return;
  const stat = fs.statSync(src);
  if (stat.isDirectory()) {
    fs.mkdirSync(dest, { recursive: true });
    for (const item of fs.readdirSync(src)) {
      copyRecursive(path.join(src, item), path.join(dest, item));
    }
  } else {
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    fs.copyFileSync(src, dest);
  }
}

console.log(`Syncing static scientific data from ${srcData} to ${targetData}...`);

// Sync candidates.json
const candidatesSrc = path.join(srcData, "candidates.json");
const candidatesDest = path.join(targetData, "candidates.json");
if (fs.existsSync(candidatesSrc)) {
  fs.mkdirSync(targetData, { recursive: true });
  fs.copyFileSync(candidatesSrc, candidatesDest);
  console.log("  ✓ Synced candidates.json");
} else {
  console.warn("  ⚠ candidates.json not found in data/output");
}

// Sync cutouts
const cutoutsSrc = path.join(srcData, "cutouts");
const cutoutsDest = path.join(targetData, "cutouts");
if (fs.existsSync(cutoutsSrc)) {
  copyRecursive(cutoutsSrc, cutoutsDest);
  console.log("  ✓ Synced cutouts directory");
}

// Sync spectra
const spectraSrc = path.join(srcData, "spectra");
const spectraDest = path.join(targetData, "spectra");
if (fs.existsSync(spectraSrc)) {
  copyRecursive(spectraSrc, spectraDest);
  console.log("  ✓ Synced spectra directory");
}

console.log("Data sync complete.");
