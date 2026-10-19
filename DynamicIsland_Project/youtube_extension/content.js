const SKIP_SELECTORS = [
  "button.ytp-ad-skip-button",
  "button.ytp-ad-skip-button-modern",
  "button.ytp-skip-ad-button",
  ".ytp-ad-skip-button",
  ".ytp-ad-skip-button-modern",
  ".ytp-skip-ad-button"
];

function isVisible(element) {
  if (!element?.isConnected || element.getAttribute("aria-hidden") === "true") {
    return false;
  }
  const style = window.getComputedStyle(element);
  const rect = element.getBoundingClientRect();
  return (
    style.display !== "none" &&
    style.visibility !== "hidden" &&
    Number(style.opacity) !== 0 &&
    style.pointerEvents !== "none" &&
    rect.width > 0 &&
    rect.height > 0 &&
    element.getClientRects().length > 0
  );
}

function findVisibleSkipButton() {
  for (const selector of SKIP_SELECTORS) {
    const candidates = document.querySelectorAll(selector);
    for (const candidate of candidates) {
      const button = candidate.matches("button,[role='button']")
        ? candidate
        : candidate.closest("button,[role='button']");
      if (!button || button.disabled || button.getAttribute("aria-disabled") === "true") {
        continue;
      }
      if (isVisible(button)) return { button, selector };
    }
  }
  return null;
}

function readAdState() {
  const player = document.querySelector(".html5-video-player");
  const adOverlay = document.querySelector(".ytp-ad-player-overlay");
  const isAd = Boolean(
    player?.classList.contains("ad-showing") ||
    player?.classList.contains("ad-interrupting") ||
    isVisible(adOverlay)
  );
  const skipButton = isAd ? findVisibleSkipButton() : null;
  return { isAd, canSkip: Boolean(skipButton), skipButton };
}

const handledSkipCommandIds = new Set();
let extensionContextInvalidated = false;
let dynamicIslandPollTimer = null;

function stopAfterExtensionReload() {
  extensionContextInvalidated = true;
  if (dynamicIslandPollTimer !== null) {
    window.clearInterval(dynamicIslandPollTimer);
    dynamicIslandPollTimer = null;
  }
}

function isInvalidatedContextError(error) {
  return /extension context invalidated/i.test(error?.message || String(error));
}

function sendRuntimeMessageSafely(message) {
  if (extensionContextInvalidated) return Promise.resolve(null);

  try {
    return Promise.resolve(chrome.runtime.sendMessage(message)).catch((error) => {
      if (isInvalidatedContextError(error)) stopAfterExtensionReload();
      return null;
    });
  } catch (error) {
    if (isInvalidatedContextError(error)) stopAfterExtensionReload();
    return Promise.resolve(null);
  }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "youtube_ping") {
    sendResponse({ ready: !extensionContextInvalidated });
    return;
  }

  if (message?.type !== "youtube_skip_ad") return;

  const commandId = message.commandId;
  if (
    sender.id !== chrome.runtime.id ||
    !Number.isInteger(commandId) ||
    commandId < 1
  ) {
    sendResponse({ clicked: false, commandId, reason: "invalid_sender_or_command" });
    return;
  }

  if (handledSkipCommandIds.has(commandId)) {
    sendResponse({ clicked: true, commandId, duplicate: true });
    return;
  }

  const state = readAdState();
  if (!state.canSkip) {
    sendResponse({ clicked: false, commandId, reason: "skip_button_not_visible" });
    return;
  }

  try {
    state.skipButton.button.focus({ preventScroll: true });
    state.skipButton.button.click();
    handledSkipCommandIds.add(commandId);
    if (handledSkipCommandIds.size > 40) {
      handledSkipCommandIds.delete(handledSkipCommandIds.values().next().value);
    }
    sendResponse({
      clicked: true,
      commandId,
      buttonSelector: state.skipButton.selector
    });
    window.setTimeout(() => {
      const afterClick = readAdState();
      const rect = afterClick.skipButton?.button.getBoundingClientRect();
      sendRuntimeMessageSafely({
        type: "youtube_skip_effect_check",
        commandId,
        adStillShowing: afterClick.isAd,
        canSkip: afterClick.canSkip,
        x: rect ? rect.left + rect.width / 2 : null,
        y: rect ? rect.top + rect.height / 2 : null
      });
    }, 1200);
  } catch (error) {
    console.error("Gagal menekan tombol Skip YouTube:", error);
    sendResponse({ clicked: false, commandId, reason: "click_failed" });
  }
});

function pollDynamicIsland() {
  if (extensionContextInvalidated) return;

  const state = readAdState();
  sendRuntimeMessageSafely({
    type: "youtube_ad_tick",
    isAd: state.isAd,
    canSkip: state.canSkip,
    visible: document.visibilityState === "visible"
  });
}

pollDynamicIsland();
dynamicIslandPollTimer = window.setInterval(pollDynamicIsland, 400);
