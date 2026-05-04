/* eslint-disable no-restricted-globals */
/**
 * FeedFormula AI — Service Worker
 *
 * Objectifs :
 * - Mettre en cache les pages et ressources principales
 * - Permettre une navigation de secours hors ligne
 * - Cacher les 5 dernières réponses de ration
 * - Accélérer le chargement des ressources statiques
 */

const CACHE_VERSION = 'feedformula-ai-v2';
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const RUNTIME_CACHE = `${CACHE_VERSION}-runtime`;
const RATION_CACHE = `${CACHE_VERSION}-ration`;
const OFFLINE_FALLBACK = './offline.html';
const MAX_RATIONS = 5;

const CORE_ASSETS = [
  './',
  './index.html',
  './vetscan.html',
  './reprotrack.html',
  './profil.html',
  './classement.html',
  './farmacademy.html',
  './modules.html',
  './nutricore.html',
  './farmcommunity.html',
  './farmcast.html',
  './pasturemap.html',
  './abonnement.html',
  './offline.html',
  './style.min.css',
  './script.min.js',
  './api.js',
  './api_bindings.js',
  './gamification_live.js',
  './service_worker.js',
  '../assets/logo_feedformula_minimal.png',
  '../assets/aya_joie.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => cache.addAll(CORE_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.map((key) => {
          if (key !== STATIC_CACHE && key !== RUNTIME_CACHE && key !== RATION_CACHE) {
            return caches.delete(key);
          }
          return Promise.resolve();
        })
      )
    )
  );
  self.clients.claim();
});

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;

  try {
    const response = await fetch(request);
    if (response && response.ok) {
      const cache = await caches.open(RUNTIME_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    const offline = await caches.match(OFFLINE_FALLBACK);
    return offline || caches.match('./index.html');
  }
}

async function networkFirst(request) {
  try {
    const response = await fetch(request);
    if (response && response.ok) {
      const cache = await caches.open(RUNTIME_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    const cached = await caches.match(request);
    if (cached) return cached;
    return caches.match(OFFLINE_FALLBACK);
  }
}

async function cacheRationResponse(request, response) {
  if (!response || !response.ok) return response;
  const cache = await caches.open(RATION_CACHE);
  const key = `ration:${Date.now()}:${Math.random().toString(36).slice(2)}`;
  await cache.put(key, response.clone());
  const keys = await cache.keys();
  if (keys.length > MAX_RATIONS) {
    const toDelete = keys.slice(0, keys.length - MAX_RATIONS);
    await Promise.all(toDelete.map((req) => cache.delete(req)));
  }
  return response;
}

self.addEventListener('fetch', (event) => {
  const { request } = event;

  if (request.method === 'POST' && new URL(request.url).pathname.endsWith('/generer-ration')) {
    event.respondWith(
      fetch(request)
        .then((response) => cacheRationResponse(request, response))
        .catch(async () => {
          const cached = await caches.match(OFFLINE_FALLBACK);
          return cached || new Response(JSON.stringify({ detail: 'hors_ligne' }), {
            headers: { 'Content-Type': 'application/json' },
            status: 503,
          });
        })
    );
    return;
  }

  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === 'navigate') {
    event.respondWith(networkFirst(request));
    return;
  }

  if (
    request.destination === 'style' ||
    request.destination === 'script' ||
    request.destination === 'image' ||
    request.destination === 'font'
  ) {
    event.respondWith(cacheFirst(request));
    return;
  }

  event.respondWith(networkFirst(request));
});

self.addEventListener('message', (event) => {
  if (!event.data || typeof event.data !== 'object') return;

  if (event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }

  if (event.data.type === 'CACHE_RATION' && event.data.payload) {
    event.waitUntil(
      caches.open(RATION_CACHE).then((cache) => {
        const key = `ration:${Date.now()}`;
        return cache.put(
          key,
          new Response(JSON.stringify(event.data.payload), {
            headers: { 'Content-Type': 'application/json' },
          })
        );
      })
    );
  }

  if (event.data.type === 'CLEAR_CACHE') {
    event.waitUntil(
      caches.keys().then((keys) =>
        Promise.all(keys.map((key) => caches.delete(key)))
      )
    );
  }
});
