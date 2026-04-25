/* =========================================================
   FeedFormula AI — script.js (frontend)
   Objectif:
   - Connecter l'interface au backend FastAPI
   - Générer une ration réelle via /generer-ration
   - Gérer la saisie vocale via /transcrire-audio
   - Partager via WhatsApp
   - Exporter un PDF via jsPDF
   - Mettre à jour la gamification (points, niveau, animations)
   ========================================================= */

/* ------------------------------
   Configuration API front
   ------------------------------ */
const API_BASE_URL = "http://localhost:8000";
const API_TIMEOUT_MS = 45000; // 45s pour génération IA + optimisation

/* ------------------------------
   État applicatif local
   ------------------------------ */
const appState = {
  pointsTotal: 1245,
  pointsNiveauActuel: 700,   // seuil estimé niveau 4
  pointsNiveauSuivant: 1900, // seuil estimé niveau 6 (exemple UI)
  niveauActuel: 4,
  langueDetectee: "fr",
  derniereRation: "",
  derniereReponseJson: null,
};

/* ------------------------------
   Accès DOM sécurisé
   ------------------------------ */
function getEl(id) {
  return document.getElementById(id);
}

const els = {
  btnGenerer: null,
  btnMic: null,
  loadingZone: null,
  resultatZone: null,
  resultContent: null,
  texteDemande: null,
  espece: null,
  stade: null,
  xpFill: null,
  xpValue: null,
  levelBadge: null,
  celebrationLayer: null,
  offlineBanner: null,
  countdown: null,
};

/* ------------------------------
   Utilitaires UI
   ------------------------------ */
function afficherMessageClair(message, type = "info") {
  // Crée un toast minimaliste sans dépendance externe.
  let toast = document.getElementById("toastFeedFormula");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "toastFeedFormula";
    toast.style.position = "fixed";
    toast.style.left = "50%";
    toast.style.bottom = "90px";
    toast.style.transform = "translateX(-50%)";
    toast.style.zIndex = "9999";
    toast.style.maxWidth = "92%";
    toast.style.padding = "12px 14px";
    toast.style.borderRadius = "12px";
    toast.style.fontSize = "16px";
    toast.style.fontWeight = "600";
    toast.style.boxShadow = "0 8px 24px rgba(0,0,0,0.18)";
    toast.style.transition = "opacity 180ms ease, transform 180ms ease";
    toast.style.opacity = "0";
    toast.style.pointerEvents = "none";
    document.body.appendChild(toast);
  }

  const colors = {
    info: { bg: "#1B5E20", fg: "#FFFFFF" },
    success: { bg: "#2E7D32", fg: "#FFFFFF" },
    warning: { bg: "#F9A825", fg: "#1E1E1E" },
    error: { bg: "#B3261E", fg: "#FFFFFF" },
  };

  const c = colors[type] || colors.info;
  toast.style.background = c.bg;
  toast.style.color = c.fg;
  toast.textContent = message;
  toast.style.opacity = "1";
  toast.style.transform = "translateX(-50%) translateY(0)";

  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(-50%) translateY(8px)";
  }, 2800);
}

function setLoading(isLoading) {
  if (!els.loadingZone || !els.btnGenerer) return;
  els.loadingZone.hidden = !isLoading;
  els.btnGenerer.disabled = isLoading;
  els.btnGenerer.textContent = isLoading ? "Aya travaille..." : "Générer ma ration";
}

function afficherResultat(html) {
  if (!els.resultatZone || !els.resultContent) return;
  els.resultContent.innerHTML = html;
  els.resultatZone.classList.remove("hidden");
}

function masquerResultat() {
  if (!els.resultatZone || !els.resultContent) return;
  els.resultContent.innerHTML = "";
  els.resultatZone.classList.add("hidden");
}

function updateOfflineBanner() {
  if (!els.offlineBanner) return;
  const offline = !navigator.onLine;
  els.offlineBanner.hidden = !offline;
  if (offline) {
    document.body.classList.add("offline");
  } else {
    document.body.classList.remove("offline");
  }
}

function formaterMonnaieFcfa(valeur) {
  const n = Number(valeur || 0);
  return `${new Intl.NumberFormat("fr-FR").format(Math.round(n))} FCFA`;
}

function formaterSecondes(sec) {
  const s = Number(sec || 0);
  return `${s.toFixed(2)} s`;
}

/* ------------------------------
   Parsing métier front
   ------------------------------ */
function extraireNombreAnimauxDepuisTexte(texte) {
  if (!texte) return 1;
  const normalized = texte.toLowerCase();

  // Cherche des patterns fréquents: "50 poulets", "j'ai 200..."
  const regex = /(\d{1,6})\s*(poulet|poulets|pondeuse|pondeuses|mouton|moutons|chevre|chèvre|chevres|chèvres|porc|porcs|tilapia|lapin|lapins|animal|animaux)/i;
  const m = normalized.match(regex);
  if (m) {
    const n = parseInt(m[1], 10);
    if (!Number.isNaN(n) && n > 0) return n;
  }

  // Fallback: premier nombre trouvé.
  const m2 = normalized.match(/\b(\d{1,6})\b/);
  if (m2) {
    const n = parseInt(m2[1], 10);
    if (!Number.isNaN(n) && n > 0) return n;
  }

  return 1;
}

function extraireIngredients(texte) {
  const t = (texte || "").toLowerCase();
  const detected = [];

  // Dictionnaire de mots-clés -> ingrédient backend.
  const patterns = [
    { re: /\bma[iï]s\b|\bagbado\b/g, value: "maïs" },
    { re: /\btourteau\s+de\s+soja\b|\bsoja\b|\bsoybean\b/g, value: "tourteau_soja" },
    { re: /\bfarine\s+de\s+poisson\b|\bfish\s+meal\b|\bj[ɔo]kp[ɔo]\b/g, value: "farine_poisson" },
    { re: /\bson\s+de\s+bl[eé]\b|\bwheat\s+bran\b/g, value: "son_ble" },
    { re: /\bson\s+de\s+riz\b|\brace\s+bran\b/g, value: "son_riz" },
    { re: /\bmanioc\b|\bcossette(s)?\b/g, value: "manioc" },
    { re: /\btourteau\s+de\s+coton\b/g, value: "tourteau_coton" },
    { re: /\btourteau\s+d['’]arachide\b|\barachide\b/g, value: "tourteau_arachide" },
    { re: /\bcoquille(s)?\s+d['’]hu[iî]tre\b/g, value: "coquille_huitre" },
  ];

  patterns.forEach((p) => {
    if (p.re.test(t)) detected.push(p.value);
  });

  // Fallback: séparation par virgule si rien de détecté.
  if (detected.length === 0 && t.includes(",")) {
    const split = t
      .split(",")
      .map((x) => x.trim())
      .filter(Boolean)
      .slice(0, 12);
    return split;
  }

  // Unicité.
  return [...new Set(detected)];
}

function detecterLangueLocaleSimple(texte) {
  // Heuristique front simple (le backend valide ensuite).
  const v = (texte || "").toLowerCase();
  if (!v.trim()) return "fr";
  if (/[ɖɔɛ]/.test(v) || /\bnɔ\b|\bkpo\b/.test(v)) return "fon";
  if (/[ẹọṣ]/.test(v) || /\bmo\b|\bni\b|\bati\b/.test(v)) return "yor";
  if (/\bi have\b|\bfeed\b|\bbroiler\b/.test(v)) return "en";
  return "fr";
}

/* ------------------------------
   Appels réseau robustes
   ------------------------------ */
async function fetchAvecTimeout(url, options = {}, timeoutMs = API_TIMEOUT_MS) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
    });
    return response;
  } finally {
    clearTimeout(timer);
  }
}

/* ------------------------------
   Étape B.1 — Génération ration
   ------------------------------ */
async function genererRation() {
  if (!navigator.onLine) {
    afficherMessageClair(
      "Serveur indisponible en mode hors ligne. Reconnecte-toi pour générer la ration.",
      "warning"
    );
    return;
  }

  try {
    setLoading(true);
    masquerResultat();

    const texteDemande = els.texteDemande?.value?.trim() || "";
    const espece = els.espece?.value || "";
    const stade = els.stade?.value || "";
    const ingredients = extraireIngredients(texteDemande);
    const nombreAnimaux = extraireNombreAnimauxDepuisTexte(texteDemande);
    const langue = detecterLangueLocaleSimple(texteDemande);

    if (!espece || !stade) {
      afficherMessageClair("Choisis l'espèce et le stade avant de générer.", "warning");
      return;
    }

    if (ingredients.length < 2) {
      afficherMessageClair(
        "Indique au moins 2 ingrédients dans le texte (ex: maïs, soja, farine de poisson).",
        "warning"
      );
      return;
    }

    const payload = {
      espece,
      stade,
      ingredients_disponibles: ingredients,
      nombre_animaux: nombreAnimaux,
      langue,
      objectif: "equilibre",
    };

    const response = await fetchAvecTimeout(`${API_BASE_URL}/generer-ration`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    }, API_TIMEOUT_MS);

    if (!response.ok) {
      // Gestion d’erreur backend propre.
      let detail = `Erreur serveur (${response.status})`;
      try {
        const err = await response.json();
        detail = err?.detail || detail;
      } catch (_) {
        // ignore parse error
      }
      throw new Error(detail);
    }

    const data = await response.json();
    appState.derniereReponseJson = data;
    appState.derniereRation = data?.ration || "";

    const composition = data?.composition || {};
    const compositionHtml = Object.entries(composition)
      .map(([k, v]) => `<li><strong>${k}</strong> : ${Number(v).toFixed(2)} kg / 100 kg</li>`)
      .join("");

    const rationTexte = (data?.ration || "").replace(/\n/g, "<br>");
    const html = `
      <article>
        <h3 style="margin-top:0;color:#1B5E20;">Ration générée ✅</h3>
        <div style="background:#F8FFF9;border:1px solid #D7EFD9;border-radius:12px;padding:12px;margin-bottom:12px;">
          ${rationTexte || "Aucune narration reçue."}
        </div>

        <h4 style="margin-bottom:6px;">Composition</h4>
        <ul>${compositionHtml || "<li>Composition indisponible</li>"}</ul>

        <div style="display:grid;gap:8px;margin-top:10px;">
          <p><strong>Coût estimé / kg :</strong> ${formaterMonnaieFcfa(data?.cout_fcfa_kg)}</p>
          <p><strong>Coût total 7 jours :</strong> ${formaterMonnaieFcfa(data?.cout_7_jours)}</p>
          <p><strong>Langue détectée :</strong> ${data?.langue_detectee || "fr"}</p>
          <p><strong>Temps de génération :</strong> ${formaterSecondes(data?.temps_generation_secondes)}</p>
        </div>

        <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:14px;">
          <button type="button" id="btnPartagerWhatsApp"
            style="min-height:48px;padding:0 14px;border-radius:999px;background:#25D366;color:#fff;font-weight:700;">
            Partager WhatsApp
          </button>
          <button type="button" id="btnTelechargerPDF"
            style="min-height:48px;padding:0 14px;border-radius:999px;background:#F9A825;color:#1E1E1E;font-weight:700;">
            Télécharger PDF
          </button>
        </div>
      </article>
    `;

    afficherResultat(html);
    afficherMessageClair("Ration générée avec succès.", "success");

    // Points + progression.
    const points = Number(data?.points_gagnes || 10);
    mettreAJourGamification(points);

    // Handlers des boutons post-résultat.
    const btnWa = document.getElementById("btnPartagerWhatsApp");
    const btnPdf = document.getElementById("btnTelechargerPDF");

    btnWa?.addEventListener("click", () => partagerWhatsApp(data?.ration || ""));
    btnPdf?.addEventListener("click", () => telechargerPDF(data?.ration || ""));

  } catch (error) {
    const isAbort = error?.name === "AbortError";
    if (isAbort) {
      afficherMessageClair(
        "Le serveur met trop de temps à répondre. Réessaie dans quelques instants.",
        "error"
      );
    } else if (!navigator.onLine) {
      afficherMessageClair(
        "Tu es hors ligne. Impossible de joindre le serveur.",
        "warning"
      );
    } else {
      afficherMessageClair(
        `Impossible de générer la ration: ${error?.message || "Erreur inconnue"}`,
        "error"
      );
    }
  } finally {
    setLoading(false);
  }
}

/* ------------------------------
   Étape B.2 — Saisie vocale
   ------------------------------ */
let mediaRecorder = null;
let chunksAudio = [];
let enregistrementEnCours = false;

async function enregistrerVoix() {
  // Si déjà en cours, on stoppe.
  if (enregistrementEnCours && mediaRecorder) {
    mediaRecorder.stop();
    return;
  }

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    afficherMessageClair("Le microphone n'est pas supporté sur cet appareil.", "error");
    return;
  }

  if (!navigator.onLine) {
    afficherMessageClair("Mode hors ligne: transcription indisponible.", "warning");
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

    chunksAudio = [];
    const options = { mimeType: "audio/webm" };
    mediaRecorder = new MediaRecorder(stream, options);

    mediaRecorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) chunksAudio.push(event.data);
    };

    mediaRecorder.onstart = () => {
      enregistrementEnCours = true;
      if (els.btnMic) {
        els.btnMic.textContent = "⏹️";
        els.btnMic.classList.add("is-listening");
      }
      afficherMessageClair("Enregistrement en cours... Appuie de nouveau pour arrêter.", "info");
    };

    mediaRecorder.onerror = () => {
      afficherMessageClair("Erreur microphone pendant l'enregistrement.", "error");
    };

    mediaRecorder.onstop = async () => {
      enregistrementEnCours = false;
      if (els.btnMic) {
        els.btnMic.textContent = "🎤";
        els.btnMic.classList.remove("is-listening");
      }

      // Arrête les tracks pour libérer le micro.
      stream.getTracks().forEach((track) => track.stop());

      if (!chunksAudio.length) {
        afficherMessageClair("Aucun audio capturé.", "warning");
        return;
      }

      try {
        setLoading(true);

        const blob = new Blob(chunksAudio, { type: "audio/webm" });
        const formData = new FormData();
        formData.append("audio", blob, "voix_eleveur.webm");
        formData.append("langue", "auto");

        const response = await fetchAvecTimeout(`${API_BASE_URL}/transcrire-audio`, {
          method: "POST",
          body: formData,
        }, API_TIMEOUT_MS);

        if (!response.ok) {
          let detail = `Erreur transcription (${response.status})`;
          try {
            const err = await response.json();
            detail = err?.detail || detail;
          } catch (_) {
            // ignore
          }
          throw new Error(detail);
        }

        const data = await response.json();
        const texte = data?.texte || "";
        const lg = data?.langue_detectee || detecterLangueLocaleSimple(texte);

        if (els.texteDemande) {
          els.texteDemande.value = texte;
        }

        appState.langueDetectee = lg;

        // Affiche langue détectée (création dynamique si absent).
        let badgeLangue = document.getElementById("langueDetecteeBadge");
        if (!badgeLangue) {
          badgeLangue = document.createElement("p");
          badgeLangue.id = "langueDetecteeBadge";
          badgeLangue.style.marginTop = "8px";
          badgeLangue.style.fontWeight = "700";
          badgeLangue.style.color = "#1B5E20";
          const parent = els.texteDemande?.parentElement;
          parent?.appendChild(badgeLangue);
        }
        badgeLangue.textContent = `Langue détectée: ${lg}`;

        afficherMessageClair("Transcription réussie.", "success");
      } catch (error) {
        const isAbort = error?.name === "AbortError";
        if (isAbort) {
          afficherMessageClair("Transcription expirée (timeout). Réessaie.", "error");
        } else {
          afficherMessageClair(
            `Transcription impossible: ${error?.message || "Erreur inconnue"}`,
            "error"
          );
        }
      } finally {
        setLoading(false);
      }
    };

    mediaRecorder.start();
  } catch (error) {
    afficherMessageClair(
      "Autorisation microphone refusée ou indisponible.",
      "error"
    );
  }
}

/* ------------------------------
   Étape B.3 — Partage WhatsApp
   ------------------------------ */
function partagerWhatsApp(ration) {
  const texte = String(ration || appState.derniereRation || "").trim();
  if (!texte) {
    afficherMessageClair("Aucune ration à partager.", "warning");
    return;
  }

  const resume = texte.length > 900 ? `${texte.slice(0, 900)}...` : texte;
  const message = `🌽 FeedFormula AI — Ma ration\n\n${resume}`;
  const lien = `https://wa.me/?text=${encodeURIComponent(message)}`;

  window.open(lien, "_blank", "noopener,noreferrer");
}

/* ------------------------------
   Étape B.4 — Export PDF jsPDF
   ------------------------------ */
function telechargerPDF(ration) {
  const texte = String(ration || appState.derniereRation || "").trim();
  if (!texte) {
    afficherMessageClair("Aucune ration à exporter en PDF.", "warning");
    return;
  }

  if (!window.jspdf || !window.jspdf.jsPDF) {
    afficherMessageClair(
      "Bibliothèque PDF non chargée. Vérifie l'inclusion jsPDF dans index.html.",
      "error"
    );
    return;
  }

  try {
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF();

    doc.setFont("helvetica", "bold");
    doc.setFontSize(14);
    doc.text("FeedFormula AI — Ration générée", 14, 18);

    doc.setFont("helvetica", "normal");
    doc.setFontSize(11);
    doc.text(`Date: ${new Date().toLocaleString("fr-FR")}`, 14, 26);

    // Découpe du texte pour éviter débordement.
    const lignes = doc.splitTextToSize(texte, 180);
    doc.text(lignes, 14, 36);

    doc.save("ration_feedformula_ai.pdf");
    afficherMessageClair("PDF téléchargé avec succès.", "success");
  } catch (error) {
    afficherMessageClair(`Erreur PDF: ${error?.message || "inconnue"}`, "error");
  }
}

/* ------------------------------
   Étape B.5 — Gamification animée
   ------------------------------ */
function mettreAJourGamification(points, niveau = null) {
  // Mise à jour des points totaux.
  const pts = Number(points || 0);
  appState.pointsTotal += pts;

  // Définition simple des seuils (même logique UI).
  const niveaux = [
    { niveau: 1, seuil: 0 },
    { niveau: 2, seuil: 150 },
    { niveau: 3, seuil: 350 },
    { niveau: 4, seuil: 700 },
    { niveau: 5, seuil: 1200 },
    { niveau: 6, seuil: 1900 },
    { niveau: 7, seuil: 2800 },
    { niveau: 8, seuil: 4000 },
    { niveau: 9, seuil: 5500 },
    { niveau: 10, seuil: 7500 },
  ];

  const oldNiveau = appState.niveauActuel;
  let newNiveau = oldNiveau;

  for (let i = 0; i < niveaux.length; i += 1) {
    if (appState.pointsTotal >= niveaux[i].seuil) {
      newNiveau = niveaux[i].niveau;
    }
  }

  if (typeof niveau === "number" && Number.isFinite(niveau)) {
    newNiveau = Math.max(newNiveau, Math.floor(niveau));
  }

  appState.niveauActuel = newNiveau;

  // Calcul progression dans le niveau courant.
  const idx = niveaux.findIndex((n) => n.niveau === newNiveau);
  const seuilCurrent = niveaux[idx]?.seuil ?? 0;
  const seuilNext = niveaux[idx + 1]?.seuil ?? seuilCurrent + 1000;
  const ratio = Math.max(0, Math.min(1, (appState.pointsTotal - seuilCurrent) / Math.max(1, (seuilNext - seuilCurrent))));
  const pct = Math.round(ratio * 100);

  // Animation barre.
  if (els.xpFill) {
    els.xpFill.style.transition = "width 200ms ease";
    els.xpFill.style.width = `${pct}%`;
  }
  if (els.xpValue) {
    els.xpValue.textContent = `${pct}%`;
  }

  // Affichage niveau badge.
  if (els.levelBadge) {
    els.levelBadge.textContent = `Niveau ${newNiveau}`;
  }

  // Petite animation points gagnés.
  if (pts > 0) {
    afficherMessageClair(`+${pts} points 🌟`, "success");
  }

  // Célébration si level up.
  if (newNiveau > oldNiveau) {
    afficherMessageClair(`🎉 Bravo! Niveau ${newNiveau} atteint!`, "success");
    declencherPluieEtoiles();
  }
}

function declencherPluieEtoiles() {
  if (!els.celebrationLayer) return;

  const layer = els.celebrationLayer;
  layer.innerHTML = "";
  layer.classList.add("is-active");

  const total = 40;
  for (let i = 0; i < total; i += 1) {
    const star = document.createElement("span");
    star.className = "star";
    star.style.left = `${Math.random() * 100}%`;
    star.style.animationDelay = `${Math.random() * 450}ms`;
    star.style.animationDuration = `${1000 + Math.random() * 1000}ms`;
    layer.appendChild(star);
  }

  setTimeout(() => {
    layer.classList.remove("is-active");
    layer.innerHTML = "";
  }, 2200);
}

/* ------------------------------
   Timer défi quotidien
   ------------------------------ */
function initialiserTimerDefi() {
  if (!els.countdown) return;
  let secondes = 24 * 60 * 60 - 1;

  function format(s) {
    const h = String(Math.floor(s / 3600)).padStart(2, "0");
    const m = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
    const sec = String(Math.floor(s % 60)).padStart(2, "0");
    return `${h}:${m}:${sec}`;
  }

  els.countdown.textContent = format(secondes);

  setInterval(() => {
    secondes = secondes <= 0 ? (24 * 60 * 60 - 1) : (secondes - 1);
    if (els.countdown) els.countdown.textContent = format(secondes);
  }, 1000);
}

/* ------------------------------
   Initialisation générale
   ------------------------------ */
function initialiserDomRefs() {
  els.btnGenerer = getEl("btnGenerer");
  els.btnMic = getEl("btnMic");
  els.loadingZone = getEl("loadingZone");
  els.resultatZone = getEl("resultatZone");
  els.resultContent = getEl("resultContent");
  els.texteDemande = getEl("texteDemande");
  els.espece = getEl("espece");
  els.stade = getEl("stade");
  els.xpFill = getEl("xpFill");
  els.xpValue = getEl("xpValue");
  els.celebrationLayer = getEl("celebrationLayer");
  els.offlineBanner = getEl("offlineBanner");
  els.countdown = getEl("countdown");

  // Badge niveau (premier élément trouvé).
  els.levelBadge = document.querySelector(".level-badge");
}

function bindEvents() {
  els.btnGenerer?.addEventListener("click", genererRation);
  els.btnMic?.addEventListener("click", enregistrerVoix);

  window.addEventListener("online", () => {
    updateOfflineBanner();
    afficherMessageClair("Connexion rétablie. Tu peux générer ta ration.", "success");
  });

  window.addEventListener("offline", () => {
    updateOfflineBanner();
    afficherMessageClair("Tu es hors ligne. Le backend est temporairement inaccessible.", "warning");
  });
}

function bootstrap() {
  initialiserDomRefs();
  bindEvents();
  updateOfflineBanner();
  initialiserTimerDefi();

  // Expose certaines fonctions globalement (debug / boutons dynamiques).
  window.genererRation = genererRation;
  window.enregistrerVoix = enregistrerVoix;
  window.partagerWhatsApp = partagerWhatsApp;
  window.telechargerPDF = telechargerPDF;
  window.mettreAJourGamification = mettreAJourGamification;
}

// Démarrage après chargement DOM.
document.addEventListener("DOMContentLoaded", bootstrap);
