import fs from "node:fs";
import path from "node:path";

const root = process.cwd();

function readJson(file) {
  return JSON.parse(fs.readFileSync(path.join(root, file), "utf8"));
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

const manifest = readJson("manifest.json");
assert(manifest.manifest_version === 3, "manifest_version must be 3");
assert(manifest.permissions.includes("nativeMessaging"), "manifest must request nativeMessaging");
assert(
  manifest.host_permissions.every((value) => value.includes("twitch.tv")),
  "host permissions must stay limited to Twitch domains"
);

for (const file of [
  "src/background.js",
  "src/content.js",
  "popup/popup.html",
  "popup/popup.js",
  "popup/popup.css",
  "options/options.html",
  "options/options.js",
  "options/options.css"
]) {
  assert(fs.existsSync(path.join(root, file)), `${file} is missing`);
}

const localeRoot = path.join(root, "_locales");
const localeNames = fs.readdirSync(localeRoot).filter((name) => {
  return fs.statSync(path.join(localeRoot, name)).isDirectory();
});
assert(localeNames.includes("en"), "en locale is required");

const enKeys = Object.keys(readJson("_locales/en/messages.json")).sort();
for (const locale of localeNames) {
  const messages = readJson(`_locales/${locale}/messages.json`);
  const keys = Object.keys(messages).sort();
  assert(JSON.stringify(keys) === JSON.stringify(enKeys), `${locale} locale key set differs from en`);
  for (const [key, value] of Object.entries(messages)) {
    assert(value && typeof value.message === "string" && value.message.length > 0, `${locale}.${key} has no message`);
  }
}

const popupHtml = fs.readFileSync(path.join(root, "popup/popup.html"), "utf8");
for (const id of ["video-quality", "audio-format", "subtitle-language", "subtitle-format", "subtitle-chinese-script", "chat-format", "output-dir", "export"]) {
  assert(popupHtml.includes(`id="${id}"`), `popup DOM missing #${id}`);
}

const optionsHtml = fs.readFileSync(path.join(root, "options/options.html"), "utf8");
for (const id of ["output-dir", "default-mode", "video-quality", "audio-format", "subtitle-format", "subtitle-chinese-script", "chat-format", "check-host"]) {
  assert(optionsHtml.includes(`id="${id}"`), `options DOM missing #${id}`);
}

console.log("Smoke checks passed.");
