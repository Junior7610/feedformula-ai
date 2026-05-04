(function () {
  'use strict';

  function qs(selector, root = document) {
    return root.querySelector(selector);
  }

  function createToast(message, type) {
    const toast = document.createElement('div');
    toast.className = `ff-live-toast ff-live-toast--${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('is-visible'));
    setTimeout(() => toast.classList.remove('is-visible'), 2800);
    setTimeout(() => toast.remove(), 3400);
  }

  function animatePoints(points) {
    const bubble = qs('[data-aya-points]');
    if (!bubble) return;
    bubble.textContent = `+${points} 🌟`;
    bubble.classList.remove('pulse');
    void bubble.offsetWidth;
    bubble.classList.add('pulse');
    setTimeout(() => bubble.classList.remove('pulse'), 900);
  }

  function animateLevelUp(level) {
    const body = document.body;
    body.classList.add('ff-level-up');
    createToast(`Niveau ${level} débloqué !`, 'level');
    setTimeout(() => body.classList.remove('ff-level-up'), 1200);
  }

  function showTrophy(trophy) {
    const title = trophy && (trophy.nom || trophy.trophee_code || 'Nouveau trophée');
    createToast(`${title} débloqué !`, 'trophy');
  }

  function refreshRanking() {
    const event = new CustomEvent('ff-ranking-refresh');
    window.dispatchEvent(event);
    createToast('Classement mis à jour', 'ranking');
  }

  function applyMessage(message) {
    if (!message || typeof message !== 'object') return;
    const type = String(message.type || '').toLowerCase();

    if (type === 'points_update') {
      const points = Number(message.payload?.points_gagnes || 0);
      if (points > 0) animatePoints(points);
    }

    if (type === 'level_up') {
      const level = Number(message.payload?.niveau?.niveau_actuel || message.payload?.niveau?.level || 0);
      animateLevelUp(level || 1);
    }

    if (type === 'trophy_unlocked') {
      showTrophy(message.payload || {});
    }

    if (type === 'ranking_refresh') {
      refreshRanking();
    }

    if (type === 'new_challenge' || type === 'challenge_completed') {
      createToast('Nouveau défi disponible', 'challenge');
    }
  }

  function connectWebSocket() {
    const body = document.body;
    const userId = body && body.dataset ? body.dataset.userId : '';
    if (!userId || !('WebSocket' in window)) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${window.location.host}/ws/gamification/${encodeURIComponent(userId)}`;
    let socket;

    try {
      socket = new WebSocket(url);
    } catch (error) {
      console.warn('[FeedFormula Live] WebSocket indisponible', error);
      return;
    }

    socket.addEventListener('open', () => {
      createToast('Gamification en direct connectée', 'system');
      setInterval(() => {
        if (socket.readyState === WebSocket.OPEN) socket.send('ping');
      }, 7000);
    });

    socket.addEventListener('message', (event) => {
      try {
        const payload = JSON.parse(event.data);
        applyMessage(payload);
      } catch (error) {
        console.warn('[FeedFormula Live] message invalide', error);
      }
    });

    socket.addEventListener('close', () => {
      createToast('Connexion live interrompue', 'system');
    });

    socket.addEventListener('error', () => {
      console.warn('[FeedFormula Live] erreur websocket');
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', connectWebSocket, { once: true });
  } else {
    connectWebSocket();
  }

  window.FeedFormulaLive = {
    animatePoints,
    animateLevelUp,
    showTrophy,
    refreshRanking,
  };
})();
