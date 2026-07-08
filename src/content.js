(() => {
  const MESSAGE_TYPE = "twitch-local-exporter";
  let lastUrl = location.href;

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (!message || message.type !== MESSAGE_TYPE) {
      return false;
    }

    if (message.action === "getPageInfo") {
      sendResponse({ ok: true, page: getPageInfo() });
      return true;
    }

    return false;
  });

  window.setInterval(() => {
    if (location.href === lastUrl) {
      return;
    }
    lastUrl = location.href;
    try {
      chrome.runtime.sendMessage({
        type: MESSAGE_TYPE,
        action: "pageUpdated",
        page: getPageInfo()
      });
    } catch {
      // The popup/background may be asleep; the next popup open will query again.
    }
  }, 1000);

  function getPageInfo() {
    const url = new URL(location.href);
    const vodId = getVodId(url);
    const title = getVideoTitle();

    return {
      url: normalizeVodUrl(url, vodId),
      rawUrl: location.href,
      videoId: vodId,
      vodId,
      title,
      supported: Boolean(vodId),
      host: url.hostname,
      pageType: getPageType(url)
    };
  }

  function getVodId(url) {
    if (!url.hostname.toLowerCase().endsWith("twitch.tv")) {
      return "";
    }
    const parts = url.pathname.split("/").filter(Boolean);
    if (parts[0] !== "videos") {
      return "";
    }
    return cleanVodId(parts[1]);
  }

  function cleanVodId(value) {
    const text = String(value || "").trim();
    return /^\d{4,20}$/.test(text) ? text : "";
  }

  function normalizeVodUrl(url, vodId) {
    if (!vodId) {
      return location.href;
    }
    return `https://www.twitch.tv/videos/${vodId}`;
  }

  function getPageType(url) {
    return getVodId(url) ? "vod" : "other";
  }

  function getVideoTitle() {
    const selectors = [
      "h1[data-a-target='stream-title']",
      "[data-a-target='video-title']",
      "h1",
      "title"
    ];

    for (const selector of selectors) {
      const element = document.querySelector(selector);
      const text = element?.textContent?.trim();
      if (text) {
        return text.replace(/\s+-\s+Twitch$/, "").trim();
      }
    }

    return document.title.replace(/\s+-\s+Twitch$/, "").trim();
  }
})();
