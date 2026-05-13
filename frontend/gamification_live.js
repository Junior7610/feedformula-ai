(function () {
  "use strict";

  function qs(selector, root = document) {
    return root.querySelector(selector);
  }

  function ensureStyle() {
    if (document.getElementById("ff-live-style")) return;
    const style = document.createElement("style");
    style.id = "ff-live-style";
    style.textContent = `
      .ff-live-toast,
      .ff-live-modal,
      .ff-live-level-overlay,
      .ff-live-challenge-toast {
        position: fixed;
        z-index: 9999;
        font-family: inherit;
      }
      .ff-live-toast {
        right: 20px;
        bottom: 20px;
        min-width: 280px;
        max-width: min(92vw, 420px);
        padding: 14px 18px;
        border-radius: 18px;
        background: rgba(14, 34, 19, 0.96);
        color: #fff;
        box-shadow: 0 18px 40px rgba(0, 0, 0, 0.28);
        transform: translateX(120%);
        opacity: 0;
        transition: transform 0.35s ease, opacity 0.35s ease;
      }
      .ff-live-toast.is-visible { transform: translateX(0); opacity: 1; }
      .ff-live-toast--level { background: linear-gradient(135deg, #0f3d19, #1b5e20); }
      .ff-live-toast--trophy { background: linear-gradient(135deg, #7f5a00, #f9a825); color: #17331c; }
      .ff-live-toast--system { background: rgba(38, 50, 56, 0.96); }
      .ff-live-toast--challenge { background: linear-gradient(135deg, #b71c1c, #ff7043); }
      .ff-live-toast--ranking { background: linear-gradient(135deg, #1a237e, #3949ab); }
      .ff-live-toast--streak { background: linear-gradient(135deg, #d84315, #ffb300); }
      .ff-live-topbar {
        position: fixed;
        inset: 0;
        pointer-events: none;
        overflow: hidden;
        z-index: 9998;
      }
      .ff-live-confetti {
        position: absolute;
        top: -12px;
        width: 10px;
        height: 18px;
        border-radius: 2px;
        animation: ff-confetti-fall 2.8s linear forwards;
      }
      .ff-live-level-overlay {
        inset: 0;
        display: grid;
        place-items: center;
        background: rgba(4, 44, 11, 0.94);
        color: #fff;
        opacity: 0;
        transition: opacity 0.25s ease;
      }
      .ff-live-level-overlay.is-visible { opacity: 1; }
      .ff-live-level-card {
        width: min(92vw, 680px);
        border-radius: 32px;
        padding: 28px;
        background: linear-gradient(180deg, rgba(8, 48, 16, 0.96), rgba(18, 72, 28, 0.96));
        box-shadow: 0 24px 60px rgba(0, 0, 0, 0.35);
        text-align: center;
        border: 1px solid rgba(249, 168, 37, 0.35);
      }
      .ff-live-level-card img {
        width: 120px;
        height: 120px;
        object-fit: contain;
        animation: ff-logo-pulse 1s ease-in-out infinite;
      }
      .ff-live-level-title {
        margin: 16px 0 8px;
        color: #f9a825;
        font-size: clamp(1.5rem, 4vw, 3rem);
        font-weight: 900;
        letter-spacing: 0.06em;
      }
      .ff-live-level-name {
        font-size: clamp(1.8rem, 5vw, 3.8rem);
        font-weight: 800;
        line-height: 1.1;
      }
      .ff-live-level-aya {
        margin: 18px auto 0;
        width: 140px;
        height: 140px;
        border-radius: 50%;
        object-fit: cover;
        border: 4px solid rgba(249, 168, 37, 0.8);
        box-shadow: 0 0 0 10px rgba(249, 168, 37, 0.12);
      }
      .ff-live-level-button {
        margin-top: 22px;
        border: 0;
        border-radius: 999px;
        padding: 14px 22px;
        font-weight: 800;
        background: #f9a825;
        color: #17331c;
        cursor: pointer;
      }
      .ff-live-modal {
        inset: 0;
        background: rgba(7, 22, 10, 0.76);
        display: grid;
        place-items: center;
        padding: 24px;
      }
      .ff-live-modal__box {
        width: min(94vw, 560px);
        border-radius: 28px;
        background: #fff;
        color: #17331c;
        padding: 24px;
        box-shadow: 0 24px 60px rgba(0, 0, 0, 0.3);
        text-align: center;
      }
      .ff-live-modal__box h3 {
        margin: 8px 0 12px;
        font-size: clamp(1.4rem, 4vw, 2.5rem);
      }
      .ff-live-modal__box .aya {
        width: 130px;
        height: 130px;
        object-fit: cover;
        border-radius: 50%;
        border: 4px solid #1b5e20;
      }
      .ff-live-flame {
        display: inline-block;
        animation: ff-flame 0.9s ease-in-out infinite;
      }
      @keyframes ff-confetti-fall {
        0% { transform: translateY(0) rotate(0deg); opacity: 1; }
        100% { transform: translateY(110vh) rotate(720deg); opacity: 0; }
      }
      @keyframes ff-logo-pulse {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.08); }
      }
      @keyframes ff-flame {
        0%, 100% { transform: scale(1) rotate(-2deg); }
        50% { transform: scale(1.12) rotate(2deg); }
      }
      body.ff-level-up {
        overflow: hidden;
        background: radial-gradient(circle at top, #184d22 0%, #07210d 100%) !important;
      }
      body.ff-level-up * { filter: saturate(1.05); }
      body.ff-level-up .ff-level-pulse {
        animation: ff-logo-pulse 1s ease-in-out infinite;
        transform-origin: center;
      }
    `;
    document.head.appendChild(style);
  }

  function createToast(message, type) {
    ensureStyle();
    const toast = document.createElement("div");
    toast.className = `ff-live-toast ff-live-toast--${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add("is-visible"));
    setTimeout(() => toast.classList.remove("is-visible"), 2800);
    setTimeout(() => toast.remove(), 3400);
  }

  function createConfetti(count = 28) {
    ensureStyle();
    const colors = ["#f9a825", "#fdd835", "#e53935", "#1b5e20", "#ffffff"];
    const wrap = document.createElement("div");
    wrap.className = "ff-live-topbar";
    for (let index = 0; index < count; index += 1) {
      const piece = document.createElement("span");
      piece.className = "ff-live-confetti";
      piece.style.left = `${Math.random() * 100}%`;
      piece.style.background = colors[index % colors.length];
      piece.style.animationDuration = `${2 + Math.random() * 1.5}s`;
      piece.style.animationDelay = `${Math.random() * 0.35}s`;
      piece.style.transform = `rotate(${Math.random() * 180}deg)`;
      wrap.appendChild(piece);
    }
    document.body.appendChild(wrap);
    setTimeout(() => wrap.remove(), 4000);
  }

  function playDrumSound(durationMs = 3000) {
    try {
      const AudioContextCtor = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextCtor) return;
      const context = new AudioContextCtor();
      const start = context.currentTime;
      const beatInterval = 0.34;
      for (let beat = 0; beat < Math.ceil(durationMs / 340); beat += 1) {
        const osc = context.createOscillator();
        const gain = context.createGain();
        osc.type = "sine";
        osc.frequency.setValueAtTime(
          180 - beat * 8,
          start + beat * beatInterval,
        );
        gain.gain.setValueAtTime(0.001, start + beat * beatInterval);
        gain.gain.exponentialRampToValueAtTime(
          0.55,
          start + beat * beatInterval + 0.01,
        );
        gain.gain.exponentialRampToValueAtTime(
          0.001,
          start + beat * beatInterval + 0.28,
        );
        osc.connect(gain).connect(context.destination);
        osc.start(start + beat * beatInterval);
        osc.stop(start + beat * beatInterval + 0.3);
      }
      setTimeout(() => context.close().catch(() => {}), durationMs + 250);
    } catch (error) {
      console.warn("[FeedFormula Live] audio indisponible", error);
    }
  }

  function closeOverlay(overlay) {
    if (!overlay) return;
    overlay.remove();
    document.body.classList.remove("ff-level-up");
  }

  function showLevelUpCelebration(level, levelName) {
    ensureStyle();
    document.body.classList.add("ff-level-up");
    createConfetti(42);
    playDrumSound(3000);

    const existing = document.querySelector(".ff-live-level-overlay");
    if (existing) existing.remove();

    const overlay = document.createElement("div");
    overlay.className = "ff-live-level-overlay";
    overlay.innerHTML = `
      <div class="ff-live-level-card">
        <img class="ff-level-pulse" src="/assets/branding/logo_principal_hd.png" alt="FeedFormula AI" />
        <div class="ff-live-level-title">NIVEAU ${level} ATTEINT !</div>
        <div class="ff-live-level-name">${levelName || "Progression exceptionnelle"}</div>
        <img class="ff-live-level-aya" src="/assets/aya_celebration.png" alt="Aya en célébration" />
        <p style="margin:16px 0 0;font-size:1.02rem;opacity:.92">Aya célèbre ta montée en niveau avec toi.</p>
        <button class="ff-live-level-button" type="button">Continuer</button>
      </div>
    `;
    document.body.appendChild(overlay);
    requestAnimationFrame(() => overlay.classList.add("is-visible"));

    const button = overlay.querySelector("button");
    const cleanup = () => closeOverlay(overlay);
    if (button) button.addEventListener("click", cleanup, { once: true });
    setTimeout(cleanup, 4000);
  }

  function animatePoints(points) {
    const bubble = qs("[data-aya-points]");
    if (!bubble) return;
    bubble.textContent = `+${points} 🌟`;
    bubble.classList.remove("pulse");
    void bubble.offsetWidth;
    bubble.classList.add("pulse");
    setTimeout(() => bubble.classList.remove("pulse"), 900);
  }

  function animateLevelUp(level) {
    showLevelUpCelebration(level || 1, `Niveau ${level || 1}`);
  }

  function showTrophy(trophy) {
    const title =
      trophy && (trophy.nom || trophy.trophee_code || "Nouveau trophée");
    createToast(`${title} débloqué !`, "trophy");
  }

  function refreshRanking() {
    const event = new CustomEvent("ff-ranking-refresh");
    window.dispatchEvent(event);
    createToast("Classement mis à jour", "ranking");
  }

  function showRankingToast(message) {
    createToast(message, "ranking");
  }

  function showStreakToast(days) {
    if (days >= 30) {
      ensureStyle();
      const modal = document.createElement("div");
      modal.className = "ff-live-modal";
      modal.innerHTML = `
        <div class="ff-live-modal__box">
          <img class="aya" src="/assets/aya_celebration.png" alt="Aya" />
          <h3>🔥 ${days} jours d'affilée !</h3>
          <p>Aya célèbre ta régularité. Tu construis une habitude puissante.</p>
          <button class="ff-live-level-button" type="button">Continuer</button>
        </div>
      `;
      document.body.appendChild(modal);
      const button = modal.querySelector("button");
      const close = () => modal.remove();
      if (button) button.addEventListener("click", close, { once: true });
      setTimeout(close, 4500);
      return;
    }
    createToast(`🔥 ${days} jours d'affilée ! Continue !`, "streak");
  }

  function showChallengeCompletion(points = 30) {
    createToast(`Défi complété ! +${points} 🌟`, "challenge");
    const target = document.querySelector(
      ".xp-fill, .level-fill, .progress-fill",
    );
    if (target) {
      const badge = document.createElement("span");
      badge.textContent = "+30 🌟";
      badge.style.position = "fixed";
      badge.style.right = "24px";
      badge.style.bottom = "96px";
      badge.style.color = "#f9a825";
      badge.style.fontWeight = "900";
      badge.style.pointerEvents = "none";
      badge.style.transition = "transform 1s ease, opacity 1s ease";
      document.body.appendChild(badge);
      requestAnimationFrame(() => {
        badge.style.transform = "translateY(-140px) scale(1.1)";
        badge.style.opacity = "0";
      });
      setTimeout(() => badge.remove(), 1200);
    }
  }

  function applyMessage(message) {
    if (!message || typeof message !== "object") return;
    const type = String(message.type || "").toLowerCase();
    const payload = message.payload || {};

    if (type === "points_update") {
      const points = Number(payload.points_gagnes || 0);
      if (points > 0) animatePoints(points);
    }

    if (type === "level_up") {
      const level = Number(
        payload.niveau?.niveau_actuel || payload.niveau?.level || 0,
      );
      const levelName =
        payload.niveau?.nom || payload.niveau?.label || `Niveau ${level || 1}`;
      animateLevelUp(level || 1, levelName);
    }

    if (type === "trophy_unlocked") {
      showTrophy(payload || {});
    }

    if (type === "ranking_refresh") {
      refreshRanking();
    }

    if (type === "new_challenge" || type === "challenge_completed") {
      showChallengeCompletion(Number(payload.points_gagnes || 30));
    }

    if (type === "streak") {
      showStreakToast(Number(payload.days || payload.streak || 0));
    }

    if (type === "ranking_overtake") {
      showRankingToast(
        `🏆 Tu as dépassé ${payload.adversaire || "un membre"} dans la ligue !`,
      );
    }
  }

  function connectWebSocket() {
    const body = document.body;
    const userId = body && body.dataset ? body.dataset.userId : "";
    if (!userId || !("WebSocket" in window)) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${window.location.host}/ws/gamification/${encodeURIComponent(userId)}`;
    let socket;

    try {
      socket = new WebSocket(url);
    } catch (error) {
      console.warn("[FeedFormula Live] WebSocket indisponible", error);
      return;
    }

    socket.addEventListener("open", () => {
      createToast("Gamification en direct connectée", "system");
      setInterval(() => {
        if (socket.readyState === WebSocket.OPEN) socket.send("ping");
      }, 7000);
    });

    socket.addEventListener("message", (event) => {
      try {
        const payload = JSON.parse(event.data);
        applyMessage(payload);
      } catch (error) {
        console.warn("[FeedFormula Live] message invalide", error);
      }
    });

    socket.addEventListener("close", () => {
      createToast("Connexion live interrompue", "system");
    });

    socket.addEventListener("error", () => {
      console.warn("[FeedFormula Live] erreur websocket");
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", connectWebSocket, {
      once: true,
    });
  } else {
    connectWebSocket();
  }

  window.FeedFormulaLive = {
    animatePoints,
    animateLevelUp,
    showTrophy,
    refreshRanking,
    showStreakToast,
    showChallengeCompletion,
  };
})();
