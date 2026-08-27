/**
 * Hannah — Travel Intake Chat Widget
 * -----------------------------------
 * Drop-in embed for the travel intake chatbot. Self-contained: injects its
 * own DOM + styles inside a Shadow Root so it never collides with the host
 * site's CSS, generates/persists a session_id per visitor, and talks to
 * POST {apiBase}/api/chat.
 *
 * Usage:
 *   <script
 *     src="https://your-cdn.com/widget.js"
 *     data-api-base="https://your-api.com"
 *     data-agency-name="Your Agency"
 *   ></script>
 */
(function () {
  "use strict";

  const SCRIPT_TAG = document.currentScript;
  const API_BASE = (SCRIPT_TAG && SCRIPT_TAG.dataset.apiBase) || "";
  const AGENCY_NAME = (SCRIPT_TAG && SCRIPT_TAG.dataset.agencyName) || "your travel specialist";
  const STORAGE_KEY = "hannah_session_id";
  const WELCOME_MESSAGE =
    "Hi, I'm Hannah \u2014 I'll help get your trip details over to " +
    AGENCY_NAME +
    ". What's your name?";

  if (!API_BASE) {
    console.error(
      "[Hannah widget] Missing data-api-base attribute on the script tag \u2014 the widget can't reach the backend."
    );
    return;
  }

  function getSessionId() {
    try {
      let id = localStorage.getItem(STORAGE_KEY);
      if (!id) {
        id = (crypto.randomUUID && crypto.randomUUID()) || String(Date.now()) + Math.random().toString(16).slice(2);
        localStorage.setItem(STORAGE_KEY, id);
      }
      return id;
    } catch (e) {
      // localStorage unavailable (private mode, etc.) — fall back to an
      // in-memory id for this page load only.
      return "session-" + Math.random().toString(16).slice(2);
    }
  }

  const sessionId = getSessionId();

  // --- Host element + Shadow DOM -------------------------------------------
  const host = document.createElement("div");
  host.id = "hannah-widget-host";
  document.body.appendChild(host);
  const root = host.attachShadow({ mode: "open" });

  const STYLES = `
    :host, * { box-sizing: border-box; }
    :host {
      --teal-950: #0B2A28;
      --teal-800: #123F3B;
      --teal-700: #175750;
      --ivory: #FBF8F2;
      --gold: #B08D3E;
      --gold-light: #D9BE7E;
      --coral: #E2673F;
      --ink: #1C2422;
      --ink-soft: #5B6B67;
      --line: #E4DDCC;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    @media (prefers-reduced-motion: reduce) {
      * { animation-duration: 0.001ms !important; transition-duration: 0.001ms !important; }
    }

    .launcher {
      position: fixed;
      bottom: 22px;
      right: 22px;
      width: 60px;
      height: 60px;
      border-radius: 50%;
      background: var(--teal-950);
      border: none;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 8px 24px rgba(11, 42, 40, 0.35);
      z-index: 2147483000;
      transition: transform 0.18s ease;
    }
    .launcher:hover { transform: scale(1.05); }
    .launcher:focus-visible { outline: 3px solid var(--gold-light); outline-offset: 3px; }
    .launcher svg { width: 26px; height: 26px; }

    .ripple {
      position: absolute;
      inset: 0;
      border-radius: 50%;
      border: 1.5px solid var(--gold-light);
      opacity: 0;
      animation: ripple 2.8s ease-out infinite;
    }
    .ripple.d2 { animation-delay: 0.9s; }
    @keyframes ripple {
      0% { transform: scale(0.8); opacity: 0.55; }
      100% { transform: scale(1.9); opacity: 0; }
    }

    .panel {
      position: fixed;
      bottom: 96px;
      right: 22px;
      width: 380px;
      max-width: calc(100vw - 32px);
      height: 600px;
      max-height: calc(100vh - 140px);
      background: var(--ivory);
      border-radius: 18px;
      box-shadow: 0 20px 60px rgba(11, 42, 40, 0.28);
      display: flex;
      flex-direction: column;
      overflow: hidden;
      z-index: 2147483000;
      opacity: 0;
      transform: translateY(12px) scale(0.98);
      pointer-events: none;
      transition: opacity 0.2s ease, transform 0.2s ease;
    }
    .panel.open { opacity: 1; transform: translateY(0) scale(1); pointer-events: auto; }

    .header {
      background: var(--teal-950);
      color: var(--ivory);
      padding: 18px 18px 16px;
      display: flex;
      align-items: center;
      gap: 12px;
      flex-shrink: 0;
    }
    .avatar {
      width: 38px; height: 38px; border-radius: 50%;
      background: linear-gradient(160deg, var(--gold-light), var(--gold));
      display: flex; align-items: center; justify-content: center;
      font: 600 15px/1 Georgia, "Iowan Old Style", serif;
      color: var(--teal-950);
      flex-shrink: 0;
    }
    .header-text h1 {
      font: 600 16px/1.2 Georgia, "Iowan Old Style", serif;
      margin: 0 0 2px;
      letter-spacing: 0.2px;
    }
    .header-text p { font: 400 12px/1.3 inherit; margin: 0; color: #C9DAD6; }
    .close-btn {
      margin-left: auto;
      background: none; border: none; color: var(--ivory);
      cursor: pointer; opacity: 0.75; padding: 6px; border-radius: 8px;
    }
    .close-btn:hover { opacity: 1; }
    .close-btn:focus-visible { outline: 2px solid var(--gold-light); outline-offset: 2px; }

    .messages {
      flex: 1;
      overflow-y: auto;
      padding: 18px 16px;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    .msg { max-width: 82%; padding: 10px 13px; border-radius: 14px; font-size: 13.5px; line-height: 1.45; }
    .msg.bot {
      background: #fff;
      border: 1px solid var(--line);
      color: var(--ink);
      align-self: flex-start;
      border-bottom-left-radius: 4px;
    }
    .msg.user {
      background: var(--teal-800);
      color: var(--ivory);
      align-self: flex-end;
      border-bottom-right-radius: 4px;
    }
    .msg.error {
      background: #FCEDE7; color: #8A3A22; border: 1px solid #EFC9B8;
      align-self: flex-start;
    }

    .typing { align-self: flex-start; display: flex; gap: 4px; padding: 10px 13px; }
    .typing span {
      width: 6px; height: 6px; border-radius: 50%; background: var(--ink-soft);
      animation: bounce 1.1s infinite ease-in-out;
    }
    .typing span:nth-child(2) { animation-delay: 0.15s; }
    .typing span:nth-child(3) { animation-delay: 0.3s; }
    @keyframes bounce { 0%, 60%, 100% { transform: translateY(0); opacity: 0.5; } 30% { transform: translateY(-4px); opacity: 1; } }

    .composer {
      display: flex;
      gap: 8px;
      padding: 12px;
      border-top: 1px solid var(--line);
      background: #fff;
      flex-shrink: 0;
    }
    .composer input {
      flex: 1;
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 10px 12px;
      font-size: 13.5px;
      color: var(--ink);
      background: var(--ivory);
    }
    .composer input:focus-visible { outline: 2px solid var(--gold); outline-offset: 1px; }
    .composer button {
      background: var(--gold);
      border: none;
      border-radius: 10px;
      width: 40px;
      display: flex; align-items: center; justify-content: center;
      cursor: pointer;
      flex-shrink: 0;
    }
    .composer button:hover { background: var(--gold-light); }
    .composer button:disabled { opacity: 0.5; cursor: default; }
    .composer button:focus-visible { outline: 2px solid var(--teal-800); outline-offset: 2px; }

    .complete-banner {
      margin: 0 16px 12px;
      padding: 10px 12px;
      background: #EFF6EE;
      border: 1px solid #C9E0C4;
      color: #2F5A2A;
      border-radius: 10px;
      font-size: 12.5px;
      text-align: center;
    }

    @media (max-width: 420px) {
      .panel { right: 16px; left: 16px; width: auto; bottom: 88px; }
      .launcher { right: 16px; bottom: 16px; }
    }
  `;

  root.innerHTML = `
    <style>${STYLES}</style>
    <button class="launcher" aria-label="Open chat with Hannah, travel specialist">
      <span class="ripple" aria-hidden="true"></span>
      <span class="ripple d2" aria-hidden="true"></span>
      <svg viewBox="0 0 24 24" fill="none" stroke="#FBF8F2" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/>
      </svg>
    </button>

    <section class="panel" role="dialog" aria-label="Chat with Hannah" aria-hidden="true">
      <header class="header">
        <div class="avatar" aria-hidden="true">H</div>
        <div class="header-text">
          <h1>Hannah</h1>
          <p>${AGENCY_NAME} \u2014 travel specialist</p>
        </div>
        <button class="close-btn" aria-label="Close chat">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>
        </button>
      </header>
      <div class="messages" role="log" aria-live="polite"></div>
      <div class="composer">
        <input type="text" placeholder="Type your reply\u2026" aria-label="Message" />
        <button type="button" aria-label="Send message">
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#0B2A28" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 2 11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>
        </button>
      </div>
    </section>
  `;

  const launcher = root.querySelector(".launcher");
  const panel = root.querySelector(".panel");
  const closeBtn = root.querySelector(".close-btn");
  const messagesEl = root.querySelector(".messages");
  const input = root.querySelector(".composer input");
  const sendBtn = root.querySelector(".composer button");

  let isOpen = false;
  let isSending = false;
  let hasGreeted = false;
  let intakeComplete = false;

  function scrollToBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function addMessage(text, role) {
    const div = document.createElement("div");
    div.className = "msg " + role;
    div.textContent = text;
    messagesEl.appendChild(div);
    scrollToBottom();
  }

  function showTyping() {
    const div = document.createElement("div");
    div.className = "typing";
    div.setAttribute("data-typing-indicator", "true");
    div.innerHTML = "<span></span><span></span><span></span>";
    messagesEl.appendChild(div);
    scrollToBottom();
    return div;
  }

  function showCompleteBanner() {
    if (root.querySelector(".complete-banner")) return;
    const div = document.createElement("div");
    div.className = "complete-banner";
    div.textContent = "All set \u2014 a human travel specialist will follow up shortly.";
    messagesEl.after(div);
  }

  function openPanel() {
    isOpen = true;
    panel.classList.add("open");
    panel.setAttribute("aria-hidden", "false");
    input.focus();
    if (!hasGreeted) {
      hasGreeted = true;
      addMessage(WELCOME_MESSAGE, "bot");
    }
  }

  function closePanel() {
    isOpen = false;
    panel.classList.remove("open");
    panel.setAttribute("aria-hidden", "true");
    launcher.focus();
  }

  launcher.addEventListener("click", () => (isOpen ? closePanel() : openPanel()));
  closeBtn.addEventListener("click", closePanel);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && isOpen) closePanel();
  });

  async function sendMessage() {
    const text = input.value.trim();
    if (!text || isSending || intakeComplete) return;

    addMessage(text, "user");
    input.value = "";
    isSending = true;
    sendBtn.disabled = true;
    const typingEl = showTyping();

    try {
      const res = await fetch(API_BASE.replace(/\/$/, "") + "/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message: text }),
      });

      typingEl.remove();

      if (!res.ok) {
        addMessage("Sorry, something went wrong on our end. Please try again in a moment.", "error");
        return;
      }

      const data = await res.json();
      addMessage(data.reply, "bot");

      if (data.intake_complete) {
        intakeComplete = true;
        input.disabled = true;
        sendBtn.disabled = true;
        input.placeholder = "Conversation complete";
        showCompleteBanner();
      }
    } catch (e) {
      typingEl.remove();
      addMessage("Couldn't reach the server \u2014 please check your connection and try again.", "error");
    } finally {
      isSending = false;
      if (!intakeComplete) sendBtn.disabled = false;
      scrollToBottom();
    }
  }

  sendBtn.addEventListener("click", sendMessage);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendMessage();
  });
})();
