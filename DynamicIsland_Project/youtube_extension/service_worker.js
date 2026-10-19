const BRIDGE_URL = "http://127.0.0.1:47863/tick";
const DIAGNOSTIC_URL = "http://127.0.0.1:47863/log";
const HEALTH_URL = "http://127.0.0.1:47863/health";
const EXTENSION_BUILD = "1.0.6";
const CONNECTION_ALARM = "dynamic-island-connection-check";
let connectionCheckPromise = null;
const diagnosticLastSentAt = new Map();

async function reportDiagnostic(event, details = {}, throttleMs = 0) {
  const throttleKey = `${event}:${details.status || ""}:${details.errorType || ""}`;
  const now = Date.now();
  if (throttleMs && now - (diagnosticLastSentAt.get(throttleKey) || 0) < throttleMs) return;
  diagnosticLastSentAt.set(throttleKey, now);

  try {
    const response = await fetch(DIAGNOSTIC_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Dynamic-Island-Client": "youtube-extension"
      },
      cache: "no-store",
      targetAddressSpace: "loopback",
      body: JSON.stringify({ source: "service_worker", event, ...details })
    });
    return response.ok;
  } catch {
    // Logging must never interrupt ad detection or skip handling.
    return false;
  }
}

async function updateToolbarConnection(connected, checking = false) {
  const badgeText = checking ? "..." : connected ? "ON" : "!";
  const badgeColor = checking ? "#71717a" : connected ? "#059669" : "#dc2626";
  const title = checking
    ? "Dynamic Island — memeriksa koneksi"
    : connected
      ? "Dynamic Island — terhubung"
      : "Dynamic Island — aplikasi tidak terhubung";

  await Promise.allSettled([
    chrome.action.setBadgeText({ text: badgeText }),
    chrome.action.setBadgeBackgroundColor({ color: badgeColor }),
    chrome.action.setTitle({ title })
  ]);
}

function checkDynamicIslandConnection() {
  if (connectionCheckPromise) return connectionCheckPromise;

  connectionCheckPromise = (async () => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 2500);
    let connected = false;

    try {
      const response = await fetch(HEALTH_URL, {
        cache: "no-store",
        targetAddressSpace: "loopback",
        signal: controller.signal
      });
      const health = response.ok ? await response.json() : null;
      connected = health?.ready === true;
    } catch (error) {
      console.debug("Dynamic Island belum dapat dijangkau:", error);
    } finally {
      clearTimeout(timeout);
    }

    await updateToolbarConnection(connected);
    return {
      connected,
      message: connected
        ? "Aplikasi siap. Buka YouTube untuk menggunakan Skip iklan."
        : "Pastikan aplikasi Dynamic Island aktif dan izinkan akses lokal jika diminta."
    };
  })().finally(() => {
    connectionCheckPromise = null;
  });

  return connectionCheckPromise;
}

async function postAdTick(payload) {
  const response = await fetch(BRIDGE_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Dynamic-Island-Client": "youtube-extension"
    },
    cache: "no-store",
    targetAddressSpace: "loopback",
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    await reportDiagnostic("bridge_tick_http_error", { status: response.status }, 10000);
    return null;
  }
  return response.json();
}

function scheduleConnectionChecks() {
  chrome.alarms.create(CONNECTION_ALARM, {
    delayInMinutes: 0.1,
    periodInMinutes: 0.5
  });
  void checkDynamicIslandConnection();
}

chrome.runtime.onInstalled.addListener(scheduleConnectionChecks);
chrome.runtime.onStartup.addListener(scheduleConnectionChecks);
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === CONNECTION_ALARM) {
    void checkDynamicIslandConnection();
  }
});

// Refresh the icon whenever the worker wakes, including after an extension reload.
void checkDynamicIslandConnection();

function isYouTubeUrl(value) {
  try {
    const host = new URL(value).hostname;
    return host === "youtube.com" || host === "www.youtube.com";
  } catch {
    return false;
  }
}

async function ensureActiveYouTubeContentScript() {
  let tab;
  try {
    const [activeTab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
    tab = activeTab;
  } catch {
    return { youtubeTab: false, contentScriptReady: false, recovered: false };
  }

  if (!Number.isInteger(tab?.id) || !isYouTubeUrl(tab.url || tab.pendingUrl)) {
    return { youtubeTab: false, contentScriptReady: false, recovered: false };
  }

  try {
    const response = await chrome.tabs.sendMessage(
      tab.id,
      { type: "youtube_ping" },
      { frameId: 0 }
    );
    if (response?.ready === true) {
      return { youtubeTab: true, contentScriptReady: true, recovered: false };
    }
  } catch {
    // A missing receiver is expected after Chrome invalidates a content-script
    // context during an extension reload. Recover it below for this tab only.
  }

  try {
    await chrome.scripting.executeScript({
      target: { tabId: tab.id, frameIds: [0] },
      files: ["content.js"]
    });
    await reportDiagnostic("content_script_reinjected", { tabId: tab.id });
    return { youtubeTab: true, contentScriptReady: true, recovered: true };
  } catch (error) {
    await reportDiagnostic("content_script_reinject_failed", {
      tabId: tab.id,
      errorType: error?.name || "Error"
    });
    return { youtubeTab: true, contentScriptReady: false, recovered: false };
  }
}

async function dispatchDebuggerClick(tabId, x, y, commandId) {
  const target = { tabId };
  let attached = false;
  let pressed = false;

  await reportDiagnostic("skip_cdp_click_dispatched", { commandId, tabId });
  try {
    await chrome.debugger.attach(target, "1.3");
    attached = true;
    await chrome.debugger.sendCommand(target, "Input.dispatchMouseEvent", {
      type: "mousePressed",
      x,
      y,
      button: "left",
      clickCount: 1
    });
    pressed = true;
    await chrome.debugger.sendCommand(target, "Input.dispatchMouseEvent", {
      type: "mouseReleased",
      x,
      y,
      button: "left",
      clickCount: 1
    });
    pressed = false;
    await reportDiagnostic("skip_cdp_click_result", {
      commandId,
      tabId,
      clicked: true
    });
    return true;
  } catch (error) {
    if (attached && pressed) {
      try {
        await chrome.debugger.sendCommand(target, "Input.dispatchMouseEvent", {
          type: "mouseReleased",
          x,
          y,
          button: "left",
          clickCount: 1
        });
      } catch {
        // Detaching below also releases the temporary debugger session.
      }
    }
    await reportDiagnostic("skip_cdp_click_failed", {
      commandId,
      tabId,
      errorType: error?.name || "Error"
    });
    return false;
  } finally {
    if (attached) {
      try {
        await chrome.debugger.detach(target);
      } catch {
        // The tab may have closed or Chrome may already have detached us.
      }
    }
  }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "youtube_skip_effect_check") {
    const tabId = sender.tab?.id;
    if (
      sender.frameId === 0 &&
      Number.isInteger(tabId) &&
      isYouTubeUrl(sender.url || sender.tab?.url) &&
      Number.isInteger(message.commandId)
    ) {
      reportDiagnostic("skip_effect_check", {
        commandId: message.commandId,
        tabId,
        adStillShowing: message.adStillShowing === true,
        canSkip: message.canSkip === true
      }).then(async () => {
        if (
          message.adStillShowing === true &&
          message.canSkip === true &&
          Number.isFinite(message.x) &&
          Number.isFinite(message.y)
        ) {
          await dispatchDebuggerClick(tabId, message.x, message.y, message.commandId);
        }
        sendResponse({ received: true });
      });
      return true;
    }
    sendResponse({ received: true });
    return;
  }

  if (message?.type === "check_dynamic_island_connection") {
    checkDynamicIslandConnection()
      .then(async (connection) => {
        if (!connection.connected) return connection;
        const contentScript = await ensureActiveYouTubeContentScript();
        return { ...connection, ...contentScript };
      })
      .then(sendResponse)
      .catch(() => {
        sendResponse({
          connected: false,
          message: "Koneksi gagal. Pastikan aplikasi Dynamic Island aktif."
        });
      });
    return true;
  }

  if (message?.type !== "youtube_ad_tick") return;

  const tabId = sender.tab?.id;
  if (
    sender.frameId !== 0 ||
    !Number.isInteger(tabId) ||
    !isYouTubeUrl(sender.url || sender.tab?.url)
  ) {
    sendResponse({ skip: false });
    return;
  }

  const visible = message.visible === true;
  const payload = {
    tabId,
    // A minimized Chrome window can have a hidden document while the YouTube
    // tab remains selected. Keep that tab as the command target; visibility
    // only describes whether the page is currently on screen.
    active: sender.tab.active === true,
    visible,
    isAd: message.isAd === true,
    canSkip: message.canSkip === true,
    clientBuild: EXTENSION_BUILD
  };

  postAdTick(payload)
    .then(async (result) => {
      if (!result?.skip || !Number.isInteger(result.commandId)) {
        sendResponse({ skip: false });
        return;
      }

      let clickResult;
      await reportDiagnostic("skip_dispatch_to_tab", { commandId: result.commandId, tabId });
      try {
        clickResult = await chrome.tabs.sendMessage(
          tabId,
          { type: "youtube_skip_ad", commandId: result.commandId },
          { frameId: 0 }
        );
      } catch (error) {
        await reportDiagnostic("skip_tab_message_failed", {
          commandId: result.commandId,
          tabId,
          errorType: error?.name || "Error"
        });
        console.warn("Tab YouTube tidak menerima perintah Skip:", error);
      }

      await reportDiagnostic("skip_click_result", {
        commandId: result.commandId,
        tabId,
        clicked: clickResult?.clicked === true,
        duplicate: clickResult?.duplicate === true,
        reason: clickResult?.reason || "none",
        buttonSelector: clickResult?.buttonSelector || "none"
      });

      if (clickResult?.clicked === true) {
        try {
          const ackResult = await postAdTick({ ...payload, skipAckCommandId: result.commandId });
          if (!ackResult) throw new Error("bridge_ack_http_error");
          await reportDiagnostic("skip_ack_sent", { commandId: result.commandId, tabId });
        } catch (error) {
          await reportDiagnostic("skip_ack_failed", {
            commandId: result.commandId,
            tabId,
            errorType: error?.name || "Error"
          });
          console.warn("ACK Skip YouTube gagal dikirim ke aplikasi:", error);
        }
      }

      sendResponse({ skip: false, dispatched: clickResult?.clicked === true });
    })
    .catch(async (error) => {
      await reportDiagnostic("bridge_tick_fetch_failed", { errorType: error?.name || "Error" }, 10000);
      sendResponse({ skip: false });
    });

  return true;
});
