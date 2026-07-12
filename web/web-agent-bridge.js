(function () {
  "use strict";

  const currentScript = document.currentScript;
  const defaultBase = currentScript ? new URL(currentScript.src).origin : "http://127.0.0.1:8766";
  const bridgeBase =
    (currentScript && currentScript.dataset.bridgeBase) ||
    window.WEB_AGENT_BRIDGE_BASE ||
    defaultBase;
  const sessionId =
    (currentScript && currentScript.dataset.sessionId) ||
    window.WEB_AGENT_SESSION_ID ||
    new URLSearchParams(location.search).get("session_id") ||
    "default";

  async function post(path, payload) {
    const response = await fetch(`${bridgeBase}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionId,
        page: location.href,
        title: document.title,
        ...payload,
      }),
    });
    if (!response.ok) {
      throw new Error(`Bridge request failed: ${response.status}`);
    }
    return response.json();
  }

  function readForm(form) {
    const data = {};
    for (const [key, value] of new FormData(form).entries()) {
      if (Object.prototype.hasOwnProperty.call(data, key)) {
        data[key] = Array.isArray(data[key]) ? data[key].concat(value) : [data[key], value];
      } else {
        data[key] = value;
      }
    }
    return data;
  }

  async function pollLatestCommand(options) {
    const intervalMs = (options && options.intervalMs) || 2500;
    const onCommand = (options && options.onCommand) || function () {};
    let lastId = "";
    async function tick() {
      try {
        const response = await fetch(
          `${bridgeBase}/api/agent-command/latest?session_id=${encodeURIComponent(sessionId)}`,
        );
        if (response.ok) {
          const command = await response.json();
          if (command.id && command.id !== lastId) {
            lastId = command.id;
            onCommand(command);
            window.dispatchEvent(new CustomEvent("web-agent-command", { detail: command }));
          }
        }
      } catch (error) {
        // Polling must never break the host page.
      } finally {
        setTimeout(tick, intervalMs);
      }
    }
    tick();
  }

  window.SoundaoAgentBridge = {
    base: bridgeBase,
    sessionId,
    event(type, payload) {
      return post("/api/events", { type, payload: payload || {} });
    },
    result(payload) {
      return post("/api/result", payload || {});
    },
    pollLatestCommand,
  };

  document.addEventListener("click", (event) => {
    const target = event.target.closest("[data-agent-action]");
    if (!target) return;
    window.SoundaoAgentBridge.event("click", {
      action: target.dataset.agentAction,
      text: target.innerText || target.value || "",
    }).catch(() => {});
  });

  document.addEventListener("submit", (event) => {
    const form = event.target.closest("form[data-agent-result]");
    if (!form) return;
    event.preventDefault();
    window.SoundaoAgentBridge
      .result({
        status: form.dataset.agentStatus || "submitted",
        step: form.dataset.agentResult || "form_submit",
        payload: readForm(form),
      })
      .then((response) => {
        form.dispatchEvent(new CustomEvent("web-agent-saved", { detail: response }));
      })
      .catch((error) => {
        form.dispatchEvent(new CustomEvent("web-agent-error", { detail: error }));
      });
  });

  window.SoundaoAgentBridge.event("page_load", {
    referrer: document.referrer,
    viewport: { width: window.innerWidth, height: window.innerHeight },
  }).catch(() => {});
})();
