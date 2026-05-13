const fs = require("fs");
const path = require("path");

const rootDir = path.resolve(__dirname, "..");
const versionFilePath = path.join(rootDir, "VERSION");

function readCurrentVersion() {
  if (!fs.existsSync(versionFilePath)) {
    return "v1.0.0";
  }

  const raw = fs.readFileSync(versionFilePath, "utf8").trim();
  return raw || "v1.0.0";
}

function bumpPatchVersion(version) {
  const match = /^v?(\d+)\.(\d+)\.(\d+)$/.exec(version);
  if (!match) {
    throw new Error(`Invalid VERSION format: ${version}`);
  }

  const [, major, minor, patch] = match;
  return `v${major}.${minor}.${Number(patch) + 1}`;
}

const currentVersion = readCurrentVersion();
const nextVersion = bumpPatchVersion(currentVersion);

fs.writeFileSync(versionFilePath, `${nextVersion}\n`, "utf8");
process.stdout.write(`[version] ${currentVersion} -> ${nextVersion}\n`);
