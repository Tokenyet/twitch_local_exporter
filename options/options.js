const MESSAGE_TYPE = "twitch-local-exporter";
const HOST_NAME = "com.dowen.twitch_local_exporter";

const fields = {
  outputDir: "output-dir",
  askOutputDirOnExport: "ask-output-dir",
  useBrowserCookies: "use-browser-cookies",
  defaultMode: "default-mode",
  defaultVideoQuality: "video-quality",
  defaultAudioFormat: "audio-format",
  defaultSubtitleFormat: "subtitle-format",
  defaultSubtitleLanguage: "subtitle-language",
  subtitleChineseScript: "subtitle-chinese-script",
  subtitleSource: "subtitle-source",
  defaultChatFormat: "chat-format",
  embedChatImages: "embed-chat-images",
  whisperModel: "whisper-model"
};

document.addEventListener("DOMContentLoaded", init);

async function init() {
  localizeDocument();
  document.getElementById("save").addEventListener("click", save);
  document.getElementById("choose-output").addEventListener("click", chooseOutputFolder);
  document.getElementById("check-host").addEventListener("click", checkHost);
  document.getElementById("update-tools").addEventListener("click", updateTools);
  await load();
  await checkHost();
}

async function load() {
  const { settings } = await sendMessage({ action: "getSettings" });
  for (const [key, id] of Object.entries(fields)) {
    const element = document.getElementById(id);
    if (element) {
      if (element.type === "checkbox") {
        element.checked = settings[key] !== false;
      } else {
        element.value = settings[key] ?? "";
      }
    }
  }
}

async function save() {
  const settings = {};
  for (const [key, id] of Object.entries(fields)) {
    const element = document.getElementById(id);
    settings[key] = element.type === "checkbox" ? element.checked : element.value.trim();
  }
  settings.forceWhisper = settings.subtitleSource === "whisper";
  await sendMessage({ action: "saveSettings", settings });
  setStatus(getMessage("optionsSaved", "Saved."));
}

async function chooseOutputFolder() {
  const output = document.getElementById("output-dir");
  const button = document.getElementById("choose-output");
  const previousText = button.textContent;
  button.disabled = true;
  button.textContent = getMessage("openingFolderPicker", "Opening...");
  setStatus(getMessage("openingFolderPickerDetail", "Choose an output folder in the Windows dialog."));
  try {
    const response = await sendNativeMessage({
      action: "chooseOutputFolder",
      initialDir: output.value.trim()
    });
    if (response.path) {
      output.value = response.path;
      await save();
    } else {
      setStatus(getMessage("folderPickerCancelled", "Folder selection cancelled."));
    }
  } catch (error) {
    setStatus(error.message || String(error));
  } finally {
    button.disabled = false;
    button.textContent = previousText;
  }
}

async function checkHost() {
  const status = document.getElementById("host-status");
  status.className = "status";
  status.textContent = getMessage("checkingHost", "Checking host...");
  try {
    const { response } = await sendMessage({ action: "ping" });
    const lines = [
      `${getMessage("hostVersion", "Host")}: ${response.version || "unknown"}`,
      `${getMessage("toolsFolder", "Tools")}: ${response.toolsDir || ""}`
    ];
    for (const [name, tool] of Object.entries(response.tools || {})) {
      lines.push(`${name}: ${tool.available ? tool.path : getMessage("missing", "missing")}`);
    }
    status.className = "status ok";
    status.textContent = lines.join("\n");
  } catch (error) {
    status.className = "status error";
    status.textContent = error.message || String(error);
  }
}

async function updateTools() {
  try {
    const { response } = await sendMessage({ action: "updateTools" });
    setStatus(`${getMessage("updateStarted", "Update started")}: ${response.jobId || ""}`);
  } catch (error) {
    setStatus(error.message || String(error));
  }
}

function setStatus(text) {
  document.getElementById("status").textContent = text;
}

function sendMessage(payload) {
  return chrome.runtime.sendMessage({ type: MESSAGE_TYPE, ...payload }).then((response) => {
    if (!response?.ok) {
      throw new Error(response?.error || getMessage("unknownError", "Unknown error"));
    }
    return response;
  });
}

function sendNativeMessage(payload) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendNativeMessage(HOST_NAME, payload, (response) => {
      const error = chrome.runtime.lastError;
      if (error) {
        reject(new Error(error.message));
        return;
      }
      if (!response?.ok) {
        reject(new Error(response?.error || getMessage("unknownError", "Unknown error")));
        return;
      }
      resolve(response);
    });
  });
}

function localizeDocument() {
  document.documentElement.lang = chrome.i18n.getUILanguage?.() || "en";
  for (const element of document.querySelectorAll("[data-i18n]")) {
    element.textContent = getMessage(element.dataset.i18n, element.textContent);
  }
}

function getMessage(key, fallback) {
  try {
    return chrome.i18n.getMessage(key) || fallback;
  } catch {
    return fallback;
  }
}
