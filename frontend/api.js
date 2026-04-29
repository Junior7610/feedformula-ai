(function (global) {
  "use strict";

  const DEFAULT_TIMEOUT_MS = 90000;

  function getBaseUrl() {
    const candidates = [
      global.FEEDFORMULA_API_BASE_URL,
      global.__FEEDFORMULA_API_BASE_URL__,
      "",
    ];
    for (const value of candidates) {
      if (typeof value === "string" && value.trim()) {
        return value.trim().replace(/\/$/, "");
      }
    }
    return "";
  }

  function buildUrl(path, query) {
    const base = getBaseUrl();
    const cleanPath = String(path || "").startsWith("/")
      ? String(path || "")
      : `/${path || ""}`;
    const url = `${base}${cleanPath}`;
    if (!query || typeof query !== "object") return url;

    const params = new URLSearchParams();
    Object.entries(query).forEach(([key, value]) => {
      if (value === undefined || value === null || value === "") return;
      params.append(key, String(value));
    });

    const qs = params.toString();
    return qs ? `${url}?${qs}` : url;
  }

  async function request(path, options = {}) {
    const {
      method = "GET",
      headers = {},
      body = undefined,
      query = undefined,
      timeoutMs = DEFAULT_TIMEOUT_MS,
      responseType = "json",
      signal = undefined,
    } = options;

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    if (signal) {
      if (signal.aborted) controller.abort();
      else
        signal.addEventListener("abort", () => controller.abort(), {
          once: true,
        });
    }

    const init = {
      method,
      headers: { ...headers },
      signal: controller.signal,
    };

    if (body !== undefined) {
      if (
        body instanceof FormData ||
        body instanceof Blob ||
        body instanceof ArrayBuffer ||
        body instanceof URLSearchParams
      ) {
        init.body = body;
      } else if (typeof body === "string") {
        init.body = body;
      } else {
        init.body = JSON.stringify(body);
        if (!init.headers["Content-Type"]) {
          init.headers["Content-Type"] = "application/json";
        }
      }
    }

    try {
      const resp = await fetch(buildUrl(path, query), init);
      const contentType = (
        resp.headers.get("content-type") || ""
      ).toLowerCase();

      let data;
      if (responseType === "blob") {
        data = await resp.blob();
      } else if (responseType === "text") {
        data = await resp.text();
      } else if (contentType.includes("application/json")) {
        data = await resp.json();
      } else {
        data = await resp.text();
      }

      if (!resp.ok) {
        const detail =
          data && typeof data === "object" && "detail" in data
            ? data.detail
            : typeof data === "string"
              ? data
              : `HTTP ${resp.status}`;
        const error = new Error(detail || `HTTP ${resp.status}`);
        error.status = resp.status;
        error.payload = data;
        throw error;
      }

      return data;
    } finally {
      clearTimeout(timer);
    }
  }

  function get(path, options = {}) {
    return request(path, { ...options, method: "GET" });
  }

  function post(path, body, options = {}) {
    return request(path, { ...options, method: "POST", body });
  }

  function put(path, body, options = {}) {
    return request(path, { ...options, method: "PUT", body });
  }

  function del(path, options = {}) {
    return request(path, { ...options, method: "DELETE" });
  }

  function postMultipart(path, formData, options = {}) {
    const headers = { ...(options.headers || {}) };
    delete headers["Content-Type"];
    return request(path, {
      ...options,
      method: "POST",
      body: formData,
      headers,
    });
  }

  function setAuthToken(token) {
    if (!token) {
      delete global.FEEDFORMULA_AUTH_TOKEN;
      return;
    }
    global.FEEDFORMULA_AUTH_TOKEN = String(token).trim();
  }

  function getAuthHeaders(extra = {}) {
    const headers = { ...extra };
    if (global.FEEDFORMULA_AUTH_TOKEN) {
      headers.Authorization = `Bearer ${global.FEEDFORMULA_AUTH_TOKEN}`;
    }
    return headers;
  }

  const api = {
    getBaseUrl,
    buildUrl,
    request,
    get,
    post,
    put,
    delete: del,
    postMultipart,
    setAuthToken,
    getAuthHeaders,

    sante() {
      return get("/sante");
    },

    langues() {
      return get("/langues");
    },

    genererRation(payload) {
      return post("/generer-ration", payload);
    },

    syntheseAudio(payload) {
      return post("/audio/synthese", payload);
    },

    transcriptionAudio(formData) {
      return postMultipart("/audio/transcription", formData);
    },

    auth: {
      inscription(payload) {
        return post("/auth/inscription", payload);
      },
      connexion(payload) {
        return post("/auth/connexion", payload);
      },
      verifierOtp(payload) {
        return post("/auth/verifier-otp", payload);
      },
      profil() {
        return get("/auth/profil", {
          headers: getAuthHeaders(),
        });
      },
    },

    gamification: {
      action(payload) {
        return post("/gamification/action", payload);
      },
      profil(userId) {
        return get(`/gamification/profil/${encodeURIComponent(userId)}`);
      },
      classement() {
        return get("/gamification/classement");
      },
      classementRegion(region) {
        return get(`/gamification/classement/${encodeURIComponent(region)}`);
      },
      defiCompleter(payload) {
        return post("/gamification/defi/completer", payload);
      },
      defisDuJour() {
        return get("/gamification/defis-du-jour");
      },
    },

    vetscan: {
      diagnostiquer(payload) {
        return post("/vetscan/diagnostiquer", payload);
      },
      analyserPhoto(formData) {
        return postMultipart("/vetscan/analyser-photo", formData);
      },
      veterinaireProches(latitude, longitude) {
        return get("/vetscan/veterinaires-proches", {
          query: { latitude, longitude },
        });
      },
    },

    reprotrack: {
      evenement(payload) {
        return post("/reprotrack/evenement", payload);
      },
      calendrier(userId) {
        return get(`/reprotrack/calendrier/${encodeURIComponent(userId)}`);
      },
      alertes(userId) {
        return get(`/reprotrack/alertes/${encodeURIComponent(userId)}`);
      },
      stats(userId) {
        return get(`/reprotrack/stats/${encodeURIComponent(userId)}`);
      },
    },

    academy: {
      formations() {
        return get("/academy/formations");
      },
      lecon(payload) {
        return post("/academy/lecon", payload);
      },
      quiz(payload) {
        return post("/academy/quiz", payload);
      },
    },

    paiement: {
      creer(payload) {
        return post("/paiement/creer", payload);
      },
      webhook(payload) {
        return post("/paiement/webhook", payload);
      },
      statut(transactionId) {
        return get(`/paiement/statut/${encodeURIComponent(transactionId)}`);
      },
      offres() {
        return get("/paiement/offres");
      },
    },

    marche: {
      prix() {
        return get("/marche/prix");
      },
      prixIngredient(ingredient) {
        return get(`/marche/prix/${encodeURIComponent(ingredient)}`);
      },
    },
  };

  global.FeedFormulaAPI = api;
})(typeof window !== "undefined" ? window : globalThis);
