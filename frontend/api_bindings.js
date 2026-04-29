/* eslint-disable no-console */
/**
 * FeedFormula AI — API bindings frontend
 *
 * Ce module ajoute une couche d’intégration backend sans casser les
 * comportements locaux déjà fournis par `script.js`.
 *
 * Stratégie :
 * - utiliser l’API quand elle est disponible
 * - préserver les fallbacks locaux quand l’API échoue
 * - rebrancher les boutons avec des handlers asynchrones
 * - précharger certaines données utiles au rendu
 */

(function apiBindings(global) {
  'use strict';

  const API = global.FeedFormulaAPI || null;

  const STORAGE_KEYS = {
    app: 'feedformula_app_state_v1',
    profile: 'feedformula_profile_state_v1',
    diagnostics: 'feedformula_diagnostics_history_v1',
    repro: 'feedformula_repro_state_v1',
    academy: 'feedformula_academy_state_v1',
    cache: 'feedformula_offline_cache_v1'
  };

  const DEFAULTS = {
    userId: '',
    langue: 'fr',
    espece: 'poulet',
    stage: 'croissance',
    objectifs: 'equilibre'
  };

  function qs(selector, root = document) {
    return root.querySelector(selector);
  }

  function qsa(selector, root = document) {
    return Array.from(root.querySelectorAll(selector));
  }

  function loadJSON(key, fallback) {
    try {
      const raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : fallback;
    } catch {
      return fallback;
    }
  }

  function saveJSON(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      // Rien à faire
    }
  }

  function cloneAndReplace(node) {
    if (!node || !node.parentNode) return node;
    const clone = node.cloneNode(true);
    node.parentNode.replaceChild(clone, node);
    return clone;
  }

  function ensureFunction(fn, fallback) {
    return typeof fn === 'function' ? fn : fallback;
  }

  function getAppState() {
    return loadJSON(STORAGE_KEYS.app, {});
  }

  function getProfileState() {
    return loadJSON(STORAGE_KEYS.profile, {});
  }

  function getUserId() {
    const profile = getProfileState();
    const app = getAppState();
    return (
      profile.id ||
      profile.user_id ||
      app.userId ||
      app.user_id ||
      DEFAULTS.userId ||
      ''
    );
  }

  function getLanguage() {
    const profile = getProfileState();
    const app = getAppState();
    return (
      profile.langue_preferee ||
      profile.language ||
      app.language ||
      localStorage.getItem('feedformula_language_v1') ||
      DEFAULTS.langue
    );
  }

  function getSelectedSpecies() {
    const app = getAppState();
    return app.selectedSpecies || app.species || DEFAULTS.espece;
  }

  function getSelectedStage() {
    const app = getAppState();
    return app.selectedStage || app.stage || DEFAULTS.stage;
  }

  function getObjective() {
    const app = getAppState();
    return app.objective || DEFAULTS.objectifs;
  }

  function getAnimalCount() {
    const app = getAppState();
    const value = Number(app.animalCount || app.count || 50);
    return Number.isFinite(value) && value > 0 ? value : 50;
  }

  function getIngredients() {
    const app = getAppState();
    const ingredients = Array.isArray(app.ingredients) ? app.ingredients : [];
    return ingredients.map((item) => String(item || '').trim()).filter(Boolean);
  }

  function notify(message, tone = 'success') {
    if (typeof global.toast === 'function') {
      global.toast(message, tone);
      return;
    }
    if (tone === 'warning') {
      console.warn(message);
    } else if (tone === 'error') {
      console.error(message);
    } else {
      console.info(message);
    }
  }

  function speakAya(message) {
    if (typeof global.updateAya === 'function') {
      global.updateAya(message);
    }
  }

  function addLocalPoints(points, reason) {
    if (typeof global.addPoints === 'function') {
      global.addPoints(points, reason);
      return;
    }
    const profile = getProfileState();
    profile.points = Number(profile.points || 0) + Number(points || 0);
    profile.stars = Number(profile.stars || 0) + Number(points || 0);
    saveJSON(STORAGE_KEYS.profile, profile);
  }

  function parseResponseError(error) {
    if (!error) return 'Erreur inconnue.';
    if (typeof error === 'string') return error;
    if (error.detail) return String(error.detail);
    if (error.message) return String(error.message);
    return 'Erreur inconnue.';
  }

  function normalizeComposition(composition) {
    if (!composition) return [];

    if (Array.isArray(composition)) {
      return composition
        .map((item) => ({
          name: String(item.name || item.label || item.ingredient || 'Ingrédient'),
          share: Number(item.share ?? item.pct ?? item.percent ?? item.value ?? 0),
          color: String(item.color || '#2E7D32')
        }))
        .filter((item) => item.name);
    }

    if (typeof composition === 'object') {
      return Object.entries(composition).map(([name, value], index) => ({
        name,
        share: Number(value || 0),
        color: ['#2E7D32', '#F9A825', '#1E88E5', '#8E24AA', '#EF5350', '#43A047'][index % 6]
      }));
    }

    return [];
  }

  function normalizeRationResponse(response, payload) {
    const composition = normalizeComposition(response.composition || response.composition_json);
    const totalCost = Number(
      response.cout_7_jours ??
        response.cout_fcfa_kg ??
        response.totalCost ??
        response.total_cost ??
        0
    );
    const totalKg = Number(response.totalKg ?? response.total_kg ?? payload.nombre_animaux ?? 50);
    const protein = Number(
      response.protein ??
        response.prot ??
        response.protein_pct ??
        response.protein_percent ??
        0
    );

    const steps = [];
    if (Array.isArray(response.steps)) {
      steps.push(...response.steps.map((step) => String(step)));
    }
    if (Array.isArray(response.recommandations)) {
      steps.push(...response.recommandations.map((step) => String(step)));
    }
    if (!steps.length && typeof response.ration === 'string') {
      steps.push(...response.ration.split('\n').map((line) => line.trim()).filter(Boolean).slice(0, 6));
    }
    if (!steps.length) {
      steps.push('Mélanger les ingrédients selon les proportions conseillées.');
      steps.push('Vérifier l’eau propre et l’accessibilité de l’aliment.');
    }

    const text = String(response.ration || response.texte || response.message || '').trim();

    return {
      species: payload.espece || payload.species || 'général',
      stage: payload.stade || payload.stage || 'général',
      objective: payload.objectif || 'equilibre',
      count: Number(payload.nombre_animaux || payload.count || 50),
      totalCost,
      totalKg,
      protein,
      composition,
      steps,
      text
    };
  }

  function persistRationHistory(ration) {
    const history = loadJSON('feedformula_rations_history_v1', []);
    history.unshift({
      date: new Date().toISOString(),
      species: ration.species,
      stage: ration.stage,
      cost: ration.totalCost,
      text: ration.text || '',
      composition: ration.composition
    });
    saveJSON('feedformula_rations_history_v1', history.slice(0, 20));
    saveJSON(STORAGE_KEYS.cache, { lastRation: history[0], rations: history.slice(0, 20) });
  }

  async function apiOrNull(task) {
    if (!API) return null;
    try {
      return await task(API);
    } catch (error) {
      console.warn('[FeedFormula API]', error);
      return null;
    }
  }

  function getAuthHeaders() {
    if (typeof API?.getAuthHeaders === 'function') {
      return API.getAuthHeaders();
    }
    return {};
  }

  function registerServiceWorker() {
    if (!('serviceWorker' in navigator)) return;
    navigator.serviceWorker.register('./sw.js').catch(() => {});
  }

  async function warmUpData() {
    if (!API) return;

    const tasks = [];
    tasks.push(apiOrNull((api) => api.sante()));
    tasks.push(apiOrNull((api) => api.gamification.defisDuJour()));
    tasks.push(apiOrNull((api) => api.gamification.classement()));
    tasks.push(apiOrNull((api) => api.academy.formations()));
    tasks.push(apiOrNull((api) => api.marche.prix()));

    await Promise.all(tasks);
  }

  function bindRationPage() {
    const generateButton = qs('#generateButton');
    const speakButton = qs('#speakButton');
    const saveHistoryButton = qs('#saveHistoryButton');
    const whatsappButton = qs('#whatsappButton');
    const pdfButton = qs('#pdfButton');

    if (generateButton) {
      const button = cloneAndReplace(generateButton);
      button.addEventListener('click', async () => {
        const payload = {
          espece: getSelectedSpecies(),
          stade: getSelectedStage(),
          ingredients_disponibles: getIngredients(),
          nombre_animaux: getAnimalCount(),
          langue: getLanguage(),
          objectif: getObjective()
        };

        const result = await apiOrNull((api) => api.genererRation(payload));

        if (result) {
          const ration = normalizeRationResponse(result, payload);
          global.__FF_LAST_RATION__ = ration;

          if (typeof global.renderRationResult === 'function') {
            global.renderRationResult(ration);
          }

          if (typeof global.storeRation === 'function') {
            global.storeRation(ration);
          } else {
            persistRationHistory(ration);
          }

          addLocalPoints(Number(result.points_gagnes || 10), 'la génération de votre ration');
          speakAya('Ration générée avec le backend.');

          const userId = getUserId();
          if (userId) {
            await apiOrNull((api) =>
              api.gamification.action({
                user_id: userId,
                action: 'generation_ration',
                code_langue: getLanguage(),
                offline_mode: false,
                multiplicateur_evenement: 1,
                region: getProfileState().region || 'Bénin',
                module: 'nutricore',
                espece: payload.espece
              })
            );
          }
          return;
        }

        if (typeof global.genererRation === 'function') {
          const local = global.genererRation();
          global.__FF_LAST_RATION__ = local;
        }
      });
    }

    if (speakButton) {
      const button = cloneAndReplace(speakButton);
      button.addEventListener('click', async () => {
        const text =
          (global.__FF_LAST_RATION__ && (global.__FF_LAST_RATION__.text || global.__FF_LAST_RATION__.ration)) ||
          qs('#rationText')?.textContent ||
          '';

        if (!text) {
          notify('Aucun texte disponible pour la synthèse.', 'warning');
          return;
        }

        const result = await apiOrNull((api) =>
          api.request('/audio/synthese', {
            method: 'POST',
            body: {
              texte: text,
              langue: getLanguage()
            },
            responseType: 'blob'
          })
        );

        if (result instanceof Blob) {
          const url = URL.createObjectURL(result);
          const audio = new Audio(url);
          audio.onended = () => URL.revokeObjectURL(url);
          audio.play().catch(() => notify('Impossible de lire l’audio.', 'warning'));
          speakAya('Synthèse audio lancée.');
          return;
        }

        if (typeof global.lireRationVocalement === 'function') {
          global.lireRationVocalement(text);
        }
      });
    }

    if (saveHistoryButton) {
      const button = cloneAndReplace(saveHistoryButton);
      button.addEventListener('click', () => {
        if (global.__FF_LAST_RATION__) {
          if (typeof global.storeRation === 'function') {
            global.storeRation(global.__FF_LAST_RATION__);
          } else {
            persistRationHistory(global.__FF_LAST_RATION__);
          }
          notify('Ration enregistrée dans l’historique.');
        }
      });
    }

    if (whatsappButton) {
      const button = cloneAndReplace(whatsappButton);
      button.addEventListener('click', async () => {
        if (typeof global.partagerWhatsApp === 'function') {
          global.partagerWhatsApp();
        }
        const userId = getUserId();
        if (userId) {
          await apiOrNull((api) =>
            api.gamification.action({
              user_id: userId,
              action: 'partage_whatsapp',
              code_langue: getLanguage(),
              offline_mode: false,
              multiplicateur_evenement: 1,
              region: getProfileState().region || 'Bénin',
              module: 'nutricore',
              espece: getSelectedSpecies()
            })
          );
        }
      });
    }

    if (pdfButton) {
      const button = cloneAndReplace(pdfButton);
      button.addEventListener('click', () => {
        if (typeof global.telechargerPDF === 'function') {
          global.telechargerPDF();
        }
      });
    }
  }

  function renderVetScanResult(result, fallbackSpecies, fallbackSymptoms) {
    const resultPanel = qs('#vetscanResult');
    const confidence = qs('#confidenceScore');
    const diagnosisList = qs('#diagnosisList');
    const protocol = qs('#careProtocol');
    const decision = qs('#decisionBanner');
    const findVetButton = qs('#findVetButton');

    if (resultPanel) resultPanel.hidden = false;

    const items = [];
    if (result.diagnostics && Array.isArray(result.diagnostics)) {
      items.push(...result.diagnostics);
    } else {
      ['diagnostic_1', 'diagnostic_2', 'diagnostic_3'].forEach((key) => {
        if (result[key]) items.push(result[key]);
      });
    }

    if (!items.length && result.hypotheses && Array.isArray(result.hypotheses)) {
      items.push(...result.hypotheses);
    }

    const confidenceValue = Number(
      result.confiance ??
        result.score ??
        result.confidence ??
        result.confidence_score ??
        0
    );

    if (confidence) {
      confidence.textContent = `${Math.round((confidenceValue || 0) * 100 || confidenceValue || 0)}%`;
    }

    if (diagnosisList) {
      diagnosisList.innerHTML = items
        .map((item) => {
          const label = item.nom || item.label || item.name || 'Hypothèse';
          const prob = Number(item.score ?? item.probability ?? item.prob ?? 0);
          const pct = prob <= 1 ? Math.round(prob * 100) : Math.round(prob);
          return `
            <div class="probability-item">
              <div class="probability-item__header">
                <strong>${label}</strong>
                <span>${pct}%</span>
              </div>
              <div class="progress-track">
                <span class="progress-track__bar" style="width:${pct}%"></span>
              </div>
              ${item.description ? `<p>${item.description}</p>` : ''}
            </div>
          `;
        })
        .join('');
    }

    const protocolSteps = result.protocole_soins || result.protocol || result.care_protocol || result.steps || [];
    if (protocol) {
      protocol.innerHTML = protocolSteps
        .map((step) => `<li>${step}</li>`)
        .join('');
    }

    const isUrgent =
      String(result.decision || result.status || '').toLowerCase().includes('urgence') ||
      String(result.message_urgence || result.alert || '').toLowerCase().includes('urgence') ||
      Boolean(result.urgent);

    if (decision) {
      decision.className = `decision-banner ${isUrgent ? 'decision-banner--danger' : 'decision-banner--ok'}`;
      decision.textContent = isUrgent
        ? '⚠️ URGENCE VÉTÉRINAIRE'
        : '✅ Soins autonomes possibles';
    }

    if (findVetButton) {
      findVetButton.hidden = !isUrgent;
    }

    const history = loadJSON(STORAGE_KEYS.diagnostics, []);
    history.unshift({
      date: new Date().toISOString(),
      species: fallbackSpecies,
      symptoms: fallbackSymptoms,
      score: confidenceValue,
      urgent: isUrgent
    });
    saveJSON(STORAGE_KEYS.diagnostics, history.slice(0, 5));

    addLocalPoints(20, 'le diagnostic VetScan');
  }

  function bindVetScanPage() {
    const diagnoseButton = qs('#diagnoseButton');
    const analyzePhotoButton = qs('#analyzePhotoButton');
    const photoInput = qs('#photoInput');
    const symptomsInput = qs('#symptomsInput');
    const speciesSelect = qs('#vetscanSpecies');
    const micButton = qs('#vetscanMicButton');

    if (diagnoseButton) {
      const button = cloneAndReplace(diagnoseButton);
      button.addEventListener('click', async () => {
        const payload = {
          espece: speciesSelect?.value || 'poulet',
          symptomes: symptomsInput?.value || '',
          langue: getLanguage(),
          user_id: getUserId() || undefined
        };

        const result = await apiOrNull((api) => api.vetscan.diagnostiquer(payload));
        if (result) {
          renderVetScanResult(result, payload.espece, payload.symptomes);
          speakAya('Diagnostic backend terminé.');
          return;
        }

        if (typeof global.diagnose === 'function') {
          global.diagnose();
          return;
        }

        notify('Diagnostic indisponible.', 'warning');
      });
    }

    if (analyzePhotoButton) {
      const button = cloneAndReplace(analyzePhotoButton);
      button.addEventListener('click', async () => {
        const file = photoInput?.files?.[0];
        if (!file) {
          notify('Veuillez d’abord choisir une photo.', 'warning');
          return;
        }

        const formData = new FormData();
        formData.append('image', file);
        formData.append('espece', speciesSelect?.value || 'poulet');
        formData.append('langue', getLanguage());
        const userId = getUserId();
        if (userId) formData.append('user_id', userId);

        const result = await apiOrNull((api) => api.vetscan.analyserPhoto(formData));
        if (result) {
          renderVetScanResult(result, speciesSelect?.value || 'poulet', 'photo analysée');
          speakAya('Photo envoyée au backend.');
          return;
        }

        notify('Analyse photo indisponible.', 'warning');
      });
    }

    if (micButton) {
      const button = cloneAndReplace(micButton);
      button.addEventListener('click', async () => {
        if (typeof global.initMicrophone === 'function') {
          global.initMicrophone();
        }
      });
    }
  }

  function renderReproTrackFromApi(data) {
    const calendar = qs('#reproCalendar');
    const monthLabel = qs('#calendarMonthLabel');
    const trackedAnimals = qs('#trackedAnimals');
    const fertilityRate = qs('#fertilityRate');
    const calvingInterval = qs('#calvingInterval');
    const birthsThisMonth = qs('#birthsThisMonth');

    if (!data) return;

    if (monthLabel && data.date) {
      const date = new Date(data.date);
      if (!Number.isNaN(date.getTime())) {
        monthLabel.textContent = date.toLocaleDateString('fr-FR', {
          month: 'long',
          year: 'numeric'
        });
      }
    }

    if (trackedAnimals && Array.isArray(data.evenements)) {
      trackedAnimals.innerHTML = data.evenements
        .slice(0, 12)
        .map((evt) => `
          <article class="tracked-item">
            <div>
              <strong>${evt.animal_id || evt.animal || 'Animal'}</strong>
              <p>${evt.type_evenement || evt.type || ''}</p>
            </div>
            <span class="tracked-item__days">✓</span>
          </article>
        `)
        .join('');
    }

    if (fertilityRate && typeof data.taux_gestation_global !== 'undefined') {
      fertilityRate.textContent = `${Number(data.taux_gestation_global || 0).toFixed(0)}%`;
    }

    if (calvingInterval && typeof data.calving_interval !== 'undefined') {
      calvingInterval.textContent = `${data.calving_interval} jours`;
    }

    if (birthsThisMonth && typeof data.total_mises_bas !== 'undefined') {
      birthsThisMonth.textContent = String(data.total_mises_bas);
    }

    if (calendar && data.calendrier_html) {
      calendar.innerHTML = data.calendrier_html;
    }
  }

  function bindReproTrackPage() {
    const saveEventButton = qs('#saveEventButton');
    const eventType = qs('#eventType');
    const eventAnimal = qs('#eventAnimal');

    if (saveEventButton) {
      const button = cloneAndReplace(saveEventButton);
      button.addEventListener('click', async () => {
        const payload = {
          user_id: getUserId() || 'local-user',
          animal_id: (eventAnimal?.value || '').trim() || 'animal-local',
          espece: getProfileState().espece_principale || getSelectedSpecies() || 'vache',
          type_evenement: eventType?.value || 'saillie',
          date_evenement: new Date().toISOString(),
          date_prevue_prochain: null,
          notes: ''
        };

        const result = await apiOrNull((api) => api.reprotrack.evenement(payload));
        if (result) {
          notify('Événement reproduction enregistré.');
          if (eventAnimal) eventAnimal.value = '';

          const userId = payload.user_id;
          await apiOrNull((api) => api.reprotrack.calendrier(userId));
          await apiOrNull((api) => api.reprotrack.alertes(userId));
          return;
        }

        if (typeof global.saveEventButton?.click === 'function') {
          global.saveEventButton.click();
        }
      });
    }

    const userId = getUserId();
    if (!userId || !API) return;

    apiOrNull((api) => api.reprotrack.calendrier(userId)).then((data) => {
      if (data) renderReproTrackFromApi(data);
    });
    apiOrNull((api) => api.reprotrack.stats(userId)).then((data) => {
      if (data) renderReproTrackFromApi(data);
    });
    apiOrNull((api) => api.reprotrack.alertes(userId)).then((data) => {
      if (data && Array.isArray(data.alertes)) {
        const trackedAnimals = qs('#trackedAnimals');
        if (trackedAnimals && !trackedAnimals.dataset.hasAlerts) {
          trackedAnimals.dataset.hasAlerts = 'true';
          trackedAnimals.innerHTML = data.alertes
            .map((alert) => `
              <article class="tracked-item">
                <div>
                  <strong>${alert.animal_id || alert.animal || 'Alerte'}</strong>
                  <p>${alert.message || alert.type || 'Alerte reproduction'}</p>
                </div>
                <span class="tracked-item__days">!</span>
              </article>
            `)
            .join('');
        }
      }
    });
  }

  function bindProfilPage() {
    const profile = getProfileState();
    const userId = getUserId();

    const name = qs('#profileName');
    const region = qs('#profileRegion');
    const memberSince = qs('#profileMemberSince');
    const avatar = qs('#profileAvatar');
    const levelBadge = qs('#profileLevelBadge');
    const points = qs('#profilePoints');
    const nextLevel = qs('#profileNextLevel');
    const goldSeeds = qs('#goldSeeds');

    if (avatar && profile.prenom) {
      avatar.textContent = profile.prenom
        .split(' ')
        .filter(Boolean)
        .slice(0, 2)
        .map((part) => part[0]?.toUpperCase() || '')
        .join('');
    }

    if (name && profile.prenom) name.textContent = profile.prenom;
    if (region && profile.region) region.textContent = `Région : ${profile.region}`;
    if (memberSince && profile.date_inscription) {
      memberSince.textContent = `Inscription : ${profile.date_inscription}`;
    }

    if (!API || !userId) return;

    apiOrNull((api) => api.auth.profil()).then((payload) => {
      if (payload && payload.user) {
        const user = payload.user;
        if (name && user.prenom) name.textContent = user.prenom;
        if (region && user.region) region.textContent = `Région : ${user.region}`;
        if (memberSince && user.date_inscription) {
          memberSince.textContent = `Inscription : ${user.date_inscription}`;
        }
      }
    });

    apiOrNull((api) => api.gamification.profil(userId)).then((payload) => {
      if (!payload) return;
      if (levelBadge && payload.ligue?.icone && payload.ligue?.nom) {
        levelBadge.textContent = `${payload.ligue.icone} ${payload.ligue.nom}`;
      }
      if (points && typeof payload.points_total !== 'undefined') {
        const next = Number(payload.points_pour_niveau_suivant || payload.points_restant || 0);
        points.textContent = `${Number(payload.points_total || 0).toLocaleString('fr-FR')} pts`;
        if (nextLevel) {
          nextLevel.textContent = `Niveau suivant : ${payload.niveau_suivant || '—'}`;
        }
      }
      if (goldSeeds && typeof payload.graines_or !== 'undefined') {
        goldSeeds.textContent = `🌟 ${Number(payload.graines_or || 0).toLocaleString('fr-FR')}`;
      }
    });
  }

  function renderRanking(payload) {
    const podium = qs('#podium');
    const rankingList = qs('#rankingList');
    const status = qs('#leagueStatus');

    if (!payload) return;

    const rows = payload.classement || payload.top || payload.users || payload.ranking || [];
    if (!Array.isArray(rows) || !rows.length) return;

    const toName = (row, index) => row.prenom || row.name || row.nom || `Éleveur ${index + 1}`;
    const toPoints = (row) => Number(row.points_total ?? row.points ?? row.score ?? 0);
    const toLevel = (row) => Number(row.niveau_actuel ?? row.level ?? row.niveau ?? 1);

    if (podium && rows.length >= 3) {
      podium.innerHTML = `
        <article class="podium-card podium-card--second">
          <span>🥈</span>
          <strong>${toName(rows[1], 2)}</strong>
          <p>${toPoints(rows[1]).toLocaleString('fr-FR')} pts</p>
        </article>
        <article class="podium-card podium-card--first">
          <span>🥇</span>
          <strong>${toName(rows[0], 1)}</strong>
          <p>${toPoints(rows[0]).toLocaleString('fr-FR')} pts</p>
        </article>
        <article class="podium-card podium-card--third">
          <span>🥉</span>
          <strong>${toName(rows[2], 3)}</strong>
          <p>${toPoints(rows[2]).toLocaleString('fr-FR')} pts</p>
        </article>
      `;
    }

    if (rankingList) {
      rankingList.innerHTML = rows.slice(3).map((row, index) => `
        <article class="ranking-row ${row.me ? 'is-me' : ''}">
          <strong>#${index + 4}</strong>
          <div class="ranking-row__avatar">${String(toName(row, index + 4)).split(' ').filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase() || '').join('')}</div>
          <div class="ranking-row__meta">
            <strong>${toName(row, index + 4)}</strong>
            <span>Niveau ${toLevel(row)}</span>
          </div>
          <span class="ranking-row__points">${toPoints(row).toLocaleString('fr-FR')} pts</span>
        </article>
      `).join('');
    }

    if (status && rows[0]) {
      const me = rows.find((row) => row.me) || rows[Math.min(rows.length - 1, 10)] || rows[0];
      const rank = Number(me.rank || me.position || 0);
      const zone = rank <= 3 ? 'monte' : rank <= 10 ? 'neutre' : 'descente';
      status.className = `league-status league-status--${zone}`;
      status.textContent =
        zone === 'monte'
          ? '⬆️ Tu es en zone montée'
          : zone === 'descente'
            ? '⬇️ Tu es en zone descente'
            : '➡️ Tu es en zone neutre';
    }
  }

  function bindClassementPage() {
    const tabs = qsa('[data-board]');
    if (!tabs.length || !API) return;

    const refresh = async (region) => {
      const payload =
        region && region !== 'national'
          ? await apiOrNull((api) => api.gamification.classementRegion(region))
          : await apiOrNull((api) => api.gamification.classement());

      if (payload) renderRanking(payload);
    };

    tabs.forEach((tab) => {
      tab.addEventListener('click', async () => {
        const board = tab.dataset.board || 'commune';
        await refresh(board === 'departement' ? 'Département' : board === 'national' ? 'national' : 'Commune');
      });
    });

    refresh('Commune');
  }

  function renderAcademyCatalog(payload) {
    const catalog = qs('#academyCatalog');
    if (!catalog) return;

    const formations = payload.formations || payload.catalogue || payload.items || [];
    if (!Array.isArray(formations) || !formations.length) return;

    catalog.innerHTML = formations
      .map((formation, index) => `
        <article class="academy-card ${index === 0 ? 'is-active' : ''}" data-index="${index}" data-id="${formation.id}">
          <div class="academy-card__icon">${formation.icone || formation.icon || '📘'}</div>
          <div class="academy-card__body">
            <h3>${formation.titre || formation.title || 'Formation'}</h3>
            <p>${formation.niveau || formation.level || ''} · ${formation.duree || formation.duration || ''}</p>
            <small>${formation.resume || formation.description || ''}</small>
          </div>
        </article>
      `)
      .join('');

    qsa('.academy-card', catalog).forEach((card) => {
      card.addEventListener('click', async () => {
        qsa('.academy-card', catalog).forEach((item) => item.classList.toggle('is-active', item === card));
        const formationId = card.dataset.id;
        if (!formationId) return;

        const lesson = await apiOrNull((api) =>
          api.academy.lecon({
            formation_id: formationId,
            lesson_index: 0
          })
        );

        if (lesson) {
          const title = qs('#lessonTitle');
          const content = qs('#lessonContent');
          const quiz = qs('#lessonQuiz');
          const progress = qs('#lessonProgress');

          if (title) title.textContent = lesson.lecon?.titre || lesson.formation?.titre || 'Leçon';
          if (content) {
            content.innerHTML = `
              <p>${lesson.lecon?.contenu || lesson.formation?.resume || ''}</p>
              <div class="lesson-image-placeholder">Image pédagogique</div>
            `;
          }
          if (quiz && lesson.quiz) {
            quiz.innerHTML = (lesson.quiz.questions || [])
              .map((question) => `
                <div class="quiz-card">
                  <strong>${question.question}</strong>
                  <div class="quiz-options">
                    ${(question.choix || []).map((choice) => `
                      <button type="button" class="quiz-option">${choice}</button>
                    `).join('')}
                  </div>
                </div>
              `)
              .join('');
          }
          if (progress) {
            progress.textContent = `${lesson.progression?.lecon_courante || 1} / ${lesson.progression?.total_lecons || formations.length}`;
          }
        }
      });
    });
  }

  function bindAcademyPage() {
    const catalog = qs('#academyCatalog');
    const prevButton = qs('#prevLessonButton');
    const nextButton = qs('#nextLessonButton');

    if (!catalog || !API) return;

    const state = {
      formations: [],
      currentFormationIndex: 0,
      currentLessonIndex: 0
    };

    const renderLesson = async () => {
      const formation = state.formations[state.currentFormationIndex];
      if (!formation) return;

      const lesson = await apiOrNull((api) =>
        api.academy.lecon({
          formation_id: formation.id,
          lesson_index: state.currentLessonIndex
        })
      );

      if (!lesson) return;

      const title = qs('#lessonTitle');
      const content = qs('#lessonContent');
      const quiz = qs('#lessonQuiz');
      const progress = qs('#lessonProgress');

      if (title) title.textContent = lesson.lecon?.titre || formation.titre;
      if (content) {
        content.innerHTML = `
          <p>${lesson.lecon?.contenu || formation.resume || ''}</p>
          <div class="lesson-image-placeholder">Image pédagogique</div>
        `;
      }
      if (quiz) {
        const quizData = await apiOrNull((api) =>
          api.academy.quiz({
            formation_id: formation.id,
            lesson_index: state.currentLessonIndex
          })
        );

        if (quizData) {
          quiz.innerHTML = (quizData.quiz?.questions || [])
            .map((question) => `
              <div class="quiz-card">
                <strong>${question.question}</strong>
                <div class="quiz-options">
                  ${(question.choix || []).map((choice, index) => `
                    <button type="button" class="quiz-option" data-correct="${index === Number(question.bonne_reponse || 0)}">${choice}</button>
                  `).join('')}
                </div>
              </div>
            `)
            .join('');

          qsa('.quiz-option', quiz).forEach((btn) => {
            btn.addEventListener('click', () => {
              if (btn.dataset.correct === 'true') {
                notify('Bonne réponse ! +20 🌟');
                addLocalPoints(20, 'une bonne réponse');
              } else {
                notify('Réponse incorrecte, essayez encore.', 'warning');
              }
            });
          });
        }
      }
      if (progress) {
        progress.textContent = `${state.currentLessonIndex + 1} / ${formation.total_lecons || 1}`;
      }
    };

    const renderCatalog = (payload) => {
      const formations = payload.formations || [];
      if (!formations.length) return;
      state.formations = formations.map((item) => ({
        id: item.id,
        titre: item.titre || item.title || 'Formation',
        resume: item.resume || item.description || '',
        niveau: item.niveau || item.level || '',
        duree: item.duree || item.duration || '',
        icon: item.icone || item.icon || '📘',
        total_lecons: Number(item.total_lecons || item.lessons || 1)
      }));
      renderAcademyCatalog({ formations: state.formations });
    };

    const load = async () => {
      const payload = await apiOrNull((api) => api.academy.formations());
      if (!payload) return;
      renderCatalog(payload);
      state.currentFormationIndex = 0;
      state.currentLessonIndex = 0;
      await renderLesson();
    };

    if (prevButton) {
      const button = cloneAndReplace(prevButton);
      button.addEventListener('click', async () => {
        state.currentLessonIndex = Math.max(0, state.currentLessonIndex - 1);
        await renderLesson();
      });
    }

    if (nextButton) {
      const button = cloneAndReplace(nextButton);
      button.addEventListener('click', async () => {
        const formation = state.formations[state.currentFormationIndex];
        if (!formation) return;
        state.currentLessonIndex = Math.min(
          Math.max(0, Number(formation.total_lecons || 1) - 1),
          state.currentLessonIndex + 1
        );
        await renderLesson();
      });
    }

    load();
  }

  function bindAbonnementPage() {
    const root = qs('[data-page="abonnement"]');
    if (!root || !API) return;

    apiOrNull((api) => api.paiement.offres()).then((payload) => {
      if (!payload || !Array.isArray(payload.offres)) return;
      const list = qs('#subscriptionOffers');
      if (!list) return;

      list.innerHTML = payload.offres
        .map((offer) => `
          <article class="pricing-card ${offer.code === 'free' ? 'is-free' : ''}" data-offer="${offer.code}">
            <h3>${offer.label}</h3>
            <p>${Number(offer.prix_fcfa || 0).toLocaleString('fr-FR')} FCFA</p>
            <ul>
              ${(offer.benefices || []).map((benefit) => `<li>${benefit}</li>`).join('')}
            </ul>
            <button type="button" class="primary-action subscribe-button" data-code="${offer.code}">S'abonner</button>
          </article>
        `)
        .join('');

      qsa('.subscribe-button', list).forEach((button) => {
        button.addEventListener('click', async () => {
          const userId = getUserId();
          if (!userId) {
            notify('Veuillez vous connecter pour souscrire.', 'warning');
            return;
          }

          const telephone = getProfileState().telephone || '';
          const payload = {
            user_id: userId,
            abonnement: button.dataset.code || 'free',
            telephone
          };

          const result = await apiOrNull((api) => api.paiement.creer(payload));
          if (result?.lien_paiement) {
            global.location.href = result.lien_paiement;
          }
        });
      });
    });
  }

  function bindCommonPrefetch() {
    const userId = getUserId();

    if (API && userId) {
      apiOrNull((api) => api.gamification.defisDuJour());
      apiOrNull((api) => api.gamification.profil(userId));
      apiOrNull((api) => api.reprotrack.calendrier(userId));
      apiOrNull((api) => api.reprotrack.alertes(userId));
    }
  }

  function boot() {
    registerServiceWorker();
    bindRationPage();
    bindVetScanPage();
    bindReproTrackPage();
    bindProfilPage();
    bindClassementPage();
    bindAcademyPage();
    bindAbonnementPage();
    bindCommonPrefetch();
    warmUpData();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})(typeof window !== 'undefined' ? window : globalThis);
