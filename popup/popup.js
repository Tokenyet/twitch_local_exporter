const MESSAGE_TYPE = "twitch-local-exporter";
const HOST_NAME = "com.dowen.twitch_local_exporter";

const state = {
  mode: "video",
  settings: null,
  page: null,
  probe: null,
  activeJobId: "",
  activeOutputPath: ""
};

const elements = {};
let jobPollTimer = 0;

document.addEventListener("DOMContentLoaded", init);

async function init() {
  collectElements();
  localizeDocument();
  wireEvents();
  await refreshAll();
  await restoreLatestJob();

  chrome.runtime.onMessage.addListener((message) => {
    if (message?.type === MESSAGE_TYPE && message.action === "jobEvent") {
      renderJobEvent(message.event);
      if (message.event?.jobId === state.activeJobId && !isTerminalJobEvent(message.event.event)) {
        scheduleJobPoll();
      }
    }
  });
}

function collectElements() {
  for (const id of [
    "video-title", "open-options", "notice", "host-status", "probe-status",
    "video-quality", "audio-format", "audio-bitrate", "subtitle-language",
    "subtitle-format", "subtitle-chinese-script", "subtitle-source", "chat-format", "embed-chat-images", "output-dir", "job-card",
    "choose-output", "ask-output-dir", "job-label", "job-percent", "job-bar", "job-detail", "open-output",
    "cancel-job", "refresh", "export"
  ]) {
    elements[id] = document.getElementById(id);
  }
}

function wireEvents() {
  document.querySelector(".segment").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-mode]");
    if (!button) {
      return;
    }
    setMode(button.dataset.mode);
  });

  elements["open-options"].addEventListener("click", () => sendMessage({ action: "openOptions" }));
  elements["choose-output"].addEventListener("click", () => chooseOutputFolder().catch(showError));
  elements["ask-output-dir"].addEventListener("change", () => savePopupOutputSettings().catch(showError));
  elements["output-dir"].addEventListener("change", () => savePopupOutputSettings().catch(showError));
  elements["subtitle-language"].addEventListener("change", () => savePopupOutputSettings().catch(showError));
  elements["subtitle-format"].addEventListener("change", () => savePopupOutputSettings().catch(showError));
  elements["subtitle-chinese-script"].addEventListener("change", () => savePopupOutputSettings().catch(showError));
  elements["subtitle-source"].addEventListener("change", () => savePopupOutputSettings().catch(showError));
  elements["chat-format"].addEventListener("change", () => savePopupOutputSettings().catch(showError));
  elements["embed-chat-images"].addEventListener("change", () => savePopupOutputSettings().catch(showError));
  elements.refresh.addEventListener("click", refreshAll);
  elements.export.addEventListener("click", startExport);
  elements["cancel-job"].addEventListener("click", cancelJob);
  elements["open-output"].addEventListener("click", openOutput);
}

async function refreshAll() {
  setBusy(true);
  setNotice("");
  try {
    const [{ settings }, { page }] = await Promise.all([
      sendMessage({ action: "getSettings" }),
      sendMessage({ action: "getPageInfo" })
    ]);

    state.settings = settings;
    state.page = page;
    state.mode = settings.defaultMode || "video";
    renderSettings(settings);
    renderPage(page);
    setMode(state.mode);
    await pingHost();

    if (page.supported) {
      await probeCurrentPage();
    } else {
      setChip(elements["probe-status"], "warn", getMessage("unsupportedPage", "Open a Twitch VOD."));
    }
  } catch (error) {
    setNotice(error.message || String(error));
  } finally {
    setBusy(false);
  }
}

async function pingHost() {
  try {
    const { response } = await sendMessage({ action: "ping" });
    const missing = Object.values(response.tools || {}).filter((tool) => !tool.available);
    setChip(
      elements["host-status"],
      missing.length ? "warn" : "ok",
      missing.length ? getMessage("hostMissingTools", "Host missing tools") : getMessage("hostReady", "Host ready")
    );
  } catch {
    setChip(elements["host-status"], "error", getMessage("hostNotInstalled", "Host not installed"));
  }
}

async function probeCurrentPage() {
  setChip(elements["probe-status"], "idle", getMessage("probing", "Probing..."));
  try {
    const { response } = await sendMessage({ action: "probe", url: state.page.url });
    state.probe = response.probe;
    renderProbe(response.probe);
    setChip(elements["probe-status"], "ok", getMessage("probeReady", "Formats ready"));
  } catch (error) {
    state.probe = null;
    renderProbe(null);
    setChip(elements["probe-status"], "error", getMessage("probeFailed", "Probe failed"));
    setNotice(error.message || String(error));
  }
}

function renderSettings(settings) {
  elements["output-dir"].value = settings.outputDir || "";
  elements["ask-output-dir"].checked = settings.askOutputDirOnExport !== false;
  elements["audio-format"].value = settings.defaultAudioFormat || "m4a";
  elements["subtitle-format"].value = settings.defaultSubtitleFormat || "srt";
  elements["subtitle-chinese-script"].value = settings.subtitleChineseScript || "traditional_tw";
  elements["subtitle-source"].value = settings.subtitleSource || "auto";
  elements["chat-format"].value = settings.defaultChatFormat || "json";
  elements["embed-chat-images"].checked = Boolean(settings.embedChatImages);
}

function renderPage(page) {
  elements["video-title"].textContent = page.supported ?
    (page.title || page.vodId || page.videoId || getMessage("twitchVod", "Twitch VOD")) :
    getMessage("unsupportedPage", "Open a Twitch VOD.");
  elements.export.disabled = !page.supported;
}

function renderProbe(probe) {
  renderVideoQualities(probe?.videoQualities || []);
  renderAudioBitrates(probe?.audioBitrates || []);
  renderSubtitleLanguages(probe?.subtitles || []);
}

function renderVideoQualities(qualities) {
  elements["video-quality"].textContent = "";
  appendOption(elements["video-quality"], "best", getMessage("bestAvailable", "Best available"));

  for (const quality of qualities) {
    appendOption(elements["video-quality"], String(quality.height), `${quality.height}p`);
  }

  elements["video-quality"].value = state.settings?.defaultVideoQuality || "best";
}

function renderAudioBitrates(bitrates) {
  elements["audio-bitrate"].textContent = "";
  appendOption(elements["audio-bitrate"], "best", getMessage("bestAvailable", "Best available"));
  for (const bitrate of bitrates) {
    appendOption(elements["audio-bitrate"], String(bitrate), `${bitrate} kbps`);
  }
}

function renderSubtitleLanguages(subtitles) {
  const seen = new Set();
  const appendLanguageOption = (value, label) => {
    seen.add(value);
    appendOption(elements["subtitle-language"], value, label);
  };

  elements["subtitle-language"].textContent = "";
  appendLanguageOption("auto", getMessage("autoLanguage", "Auto"));
  appendLanguageOption("zh", getMessage("languageChinese", "Chinese"));
  appendLanguageOption("ja", getMessage("languageJapanese", "Japanese"));
  appendLanguageOption("en", getMessage("languageEnglish", "English"));

  for (const subtitle of subtitles) {
    if (!subtitle.lang || seen.has(subtitle.lang)) {
      continue;
    }
    seen.add(subtitle.lang);
    const label = subtitle.name ? `${subtitle.lang} - ${subtitle.name}` : subtitle.lang;
    appendOption(elements["subtitle-language"], subtitle.lang, `${label} (${subtitle.type})`);
  }

  elements["subtitle-language"].value = state.settings?.defaultSubtitleLanguage || "auto";
}

function setMode(mode) {
  state.mode = mode;
  for (const button of document.querySelectorAll(".segment button")) {
    button.classList.toggle("is-active", button.dataset.mode === mode);
  }
  for (const panel of document.querySelectorAll("[data-panel]")) {
    panel.hidden = panel.dataset.panel !== mode;
  }
}

async function startExport() {
  if (!state.page?.supported) {
    setNotice(getMessage("unsupportedPage", "Open a Twitch VOD."));
    return;
  }

  setBusy(true);
  setNotice("");
  try {
    const shouldContinue = await maybeChooseOutputFolderBeforeExport();
    if (!shouldContinue) {
      return;
    }
    const request = buildExportRequest();
    const { response } = await sendMessage({ action: "export", request });
    state.activeJobId = response.jobId;
    elements["job-card"].hidden = false;
    renderJobEvent({ jobId: response.jobId, event: "queued", percent: 0, detail: getMessage("jobQueued", "Queued") });
    scheduleJobPoll();
  } catch (error) {
    setNotice(error.message || String(error));
  } finally {
    setBusy(false);
  }
}

function buildExportRequest() {
  const subtitleSource = elements["subtitle-source"].value;
  return {
    kind: state.mode,
    url: state.page.url,
    title: state.page.title,
    videoId: state.page.videoId,
    vodId: state.page.vodId || state.page.videoId,
    quality: elements["video-quality"].value || "best",
    audioFormat: elements["audio-format"].value || "m4a",
    audioBitrate: elements["audio-bitrate"].value || "best",
    outputDir: elements["output-dir"].value.trim(),
    probe: state.probe || null,
    whisperModel: state.settings?.whisperModel || "small",
    subtitles: {
      language: elements["subtitle-language"].value || "auto",
      format: elements["subtitle-format"].value || "srt",
      chineseScript: elements["subtitle-chinese-script"].value || "traditional_tw",
      source: subtitleSource,
      forceWhisper: subtitleSource === "whisper"
    },
    chat: {
      format: elements["chat-format"].value || "json",
      embedImages: elements["embed-chat-images"].checked
    }
  };
}

async function maybeChooseOutputFolderBeforeExport() {
  const shouldAsk = elements["ask-output-dir"].checked || !elements["output-dir"].value.trim();
  if (!shouldAsk) {
    return true;
  }

  const path = await chooseOutputFolder();
  if (!path) {
    setNotice(getMessage("exportCancelled", "Export cancelled."));
    return false;
  }
  return true;
}

async function chooseOutputFolder() {
  const button = elements["choose-output"];
  const previousText = button.textContent;
  button.disabled = true;
  button.textContent = getMessage("openingFolderPicker", "Opening...");
  setNotice(getMessage("openingFolderPickerDetail", "Choose an output folder in the Windows dialog."));
  try {
    const response = await sendNativeMessage({
      action: "chooseOutputFolder",
      initialDir: elements["output-dir"].value.trim()
    });
    if (response.cancelled || !response.path) {
      setNotice(getMessage("folderPickerCancelled", "Folder selection cancelled."));
      return "";
    }
    elements["output-dir"].value = response.path;
    await savePopupOutputSettings();
    setNotice("");
    return response.path;
  } finally {
    button.disabled = false;
    button.textContent = previousText;
  }
}

async function savePopupOutputSettings() {
  const settings = {
    ...(state.settings || {}),
    outputDir: elements["output-dir"].value.trim(),
    askOutputDirOnExport: elements["ask-output-dir"].checked,
    defaultSubtitleLanguage: elements["subtitle-language"].value,
    defaultSubtitleFormat: elements["subtitle-format"].value,
    subtitleChineseScript: elements["subtitle-chinese-script"].value,
    subtitleSource: elements["subtitle-source"].value,
    defaultChatFormat: elements["chat-format"].value,
    embedChatImages: elements["embed-chat-images"].checked
  };
  const response = await sendMessage({ action: "saveSettings", settings });
  state.settings = response.settings;
}

function renderJobEvent(event) {
  if (!event?.jobId) {
    return;
  }

  state.activeJobId = event.jobId;
  if (event.outputPath) {
    state.activeOutputPath = event.outputPath;
  }

  elements["job-card"].hidden = false;
  const percent = Math.max(0, Math.min(100, Number(event.percent) || 0));
  elements["job-percent"].textContent = `${Math.round(percent)}%`;
  elements["job-bar"].style.width = `${percent}%`;
  elements["job-label"].textContent = formatJobLabel(event.event);
  elements["job-detail"].textContent = event.detail || event.outputPath || "";
  elements["cancel-job"].disabled = ["done", "error", "cancelled"].includes(event.event);
  elements["open-output"].disabled = !event.outputPath && !state.activeOutputPath;

  if (event.event === "error") {
    setNotice(event.error || event.detail || getMessage("jobFailed", "Export failed"));
  }

  if (isTerminalJobEvent(event.event)) {
    stopJobPoll();
  }
}

async function restoreLatestJob() {
  try {
    const response = await sendMessage({ action: "getRecentJobs", limit: 1 });
    const job = response.jobs?.[0];
    if (!job) {
      return;
    }
    state.activeJobId = job.jobId;
    if (job.outputPath) {
      state.activeOutputPath = job.outputPath;
    }
    renderJobEvent({
      ...job,
      detail: buildRestoredJobDetail(job)
    });
    if (!isTerminalJobEvent(job.event)) {
      scheduleJobPoll();
    }
  } catch {
    // Job history is a convenience; popup should still load if it is unavailable.
  }
}

function buildRestoredJobDetail(job) {
  const title = job.request?.title || job.detail || "";
  const prefix = getMessage("restoredJob", "Last job");
  return title ? `${prefix}: ${title}` : prefix;
}

function scheduleJobPoll() {
  stopJobPoll();
  if (!state.activeJobId) {
    return;
  }
  jobPollTimer = window.setTimeout(pollActiveJob, 2500);
}

function stopJobPoll() {
  if (jobPollTimer) {
    window.clearTimeout(jobPollTimer);
    jobPollTimer = 0;
  }
}

async function pollActiveJob() {
  if (!state.activeJobId) {
    return;
  }
  try {
    const { response } = await sendMessage({ action: "jobStatus", jobId: state.activeJobId });
    if (response.job) {
      renderJobEvent(response.job);
      if (!isTerminalJobEvent(response.job.event)) {
        scheduleJobPoll();
      }
    }
  } catch (error) {
    setNotice(`${getMessage("jobStatusUnavailable", "Last job status is unavailable")}: ${error.message || error}`);
    scheduleJobPoll();
  }
}

function isTerminalJobEvent(eventName) {
  return ["done", "error", "cancelled"].includes(eventName);
}

function formatJobLabel(eventName) {
  const labels = {
    queued: getMessage("jobQueued", "Queued"),
    progress: getMessage("jobProgress", "Exporting"),
    postprocess: getMessage("jobPostprocess", "Post-processing"),
    done: getMessage("jobDone", "Done"),
    error: getMessage("jobFailed", "Failed"),
    cancelled: getMessage("jobCancelled", "Cancelled")
  };
  return labels[eventName] || eventName || "";
}

async function cancelJob() {
  if (!state.activeJobId) {
    return;
  }
  const { response } = await sendMessage({ action: "cancelJob", jobId: state.activeJobId });
  if (response.job) {
    renderJobEvent(response.job);
  }
}

async function openOutput() {
  const path = state.activeOutputPath;
  if (!path) {
    return;
  }
  await sendMessage({ action: "openOutputFolder", path });
}

function appendOption(select, value, label) {
  const option = document.createElement("option");
  option.value = value;
  option.textContent = label;
  select.appendChild(option);
}

function setBusy(busy) {
  elements.refresh.disabled = busy;
  elements.export.disabled = busy || !state.page?.supported;
}

function setChip(element, stateName, text) {
  element.dataset.state = stateName;
  element.textContent = text;
}

function setNotice(text) {
  elements.notice.hidden = !text;
  elements.notice.textContent = text || "";
}

function showError(error) {
  setNotice(error.message || String(error));
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
    const message = getMessage(element.dataset.i18n, element.textContent);
    if (element.tagName === "OPTION") {
      element.textContent = message;
    } else {
      element.textContent = message;
    }
  }
}

function getMessage(key, fallback) {
  try {
    return chrome.i18n.getMessage(key) || fallback;
  } catch {
    return fallback;
  }
}
