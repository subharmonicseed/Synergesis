/* Local-only client. The Python engine owns conversation, memory and receipts. */
"use strict";

(() => {
  const byId = (id) => document.getElementById(id);
  const ui = Object.fromEntries([
    "new-conversation", "nav-conversation", "nav-memory", "nav-sources",
    "nav-memory-count", "nav-source-count", "server-dot", "server-status", "shutdown",
    "model-name", "ollama-status", "model-status", "notification", "notification-text",
    "refresh", "turns-label", "message-scroll", "welcome", "messages", "processing",
    "processing-text", "suggest-hello", "suggest-document", "mode-message", "mode-document",
    "mode-web", "document-tools", "document-select", "choose-document", "document-file",
    "message-form", "message-label", "message", "send", "send-label", "mode-explanation",
    "context-panel", "close-panel", "tab-memory", "tab-sources", "panel-memory", "panel-sources",
    "memory-count", "source-count", "memory-form", "memory-text", "remember", "recall-all",
    "memories", "recall-form", "recall-query", "recall", "source-list"
  ].map((id) => [id, byId(id)]));

  let state = null;
  let connected = false;
  let stopped = false;
  let shutdownRequested = false;
  let shutdownConfirmed = false;
  let localPending = false;
  let fileChooserOpen = false;
  let mode = "message";
  let pollTimer = null;
  let pollDeadline = 0;
  let refreshPending = false;
  let lastOperationId = null;
  let messagesSignature = "";
  let memoriesSignature = "";
  let sourcesSignature = "";
  let documentsSignature = "";
  let selectedDocumentId = "";
  // arXiv retrieval can precede the model's 180-second timeout.
  const POLL_WINDOW_MS = 240000;
  const actionLabels = {
    message: "Syn prépare sa réponse…",
    remember: "Enregistrement du souvenir…",
    recall: "Consultation de la mémoire…",
    new_conversation: "Ouverture d’une nouvelle conversation…",
    web: "Recherche arXiv et préparation de la synthèse…",
    upload_document: "Import du document…",
    document_question: "Lecture du document et préparation de la réponse…",
    shutdown: "Arrêt de l’application…"
  };

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = String(text);
    return node;
  }

  function showNotification(message, kind = "error", canRefresh = true) {
    ui.notification.hidden = !message;
    ui.notification.className = `notification ${kind}`;
    ui["notification-text"].textContent = message;
    ui.refresh.hidden = !canRefresh;
  }

  function dateLabel(raw) {
    if (!raw) return "Date non fournie";
    const parsed = new Date(raw);
    if (Number.isNaN(parsed.getTime())) return String(raw);
    return new Intl.DateTimeFormat("fr-FR", {
      day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit"
    }).format(parsed);
  }

  // A source URL must be an exact HTTPS arXiv host. Untrusted paths stay plain text.
  function arxivUrl(raw) {
    try {
      const url = new URL(String(raw));
      if (url.protocol !== "https:" || url.username || url.password || url.port) return null;
      if (!["arxiv.org", "export.arxiv.org"].includes(url.hostname)) return null;
      return url.href;
    } catch {
      return null;
    }
  }

  function activeLock() {
    return localPending || Boolean(state?.busy) || !connected || stopped;
  }

  function modelReady() {
    return state?.provider?.available === true && state?.provider?.model_available === true;
  }

  function updateControls() {
    const locked = activeLock();
    document.querySelectorAll("[data-mutation]").forEach((button) => { button.disabled = locked; });
    const remainingTurns = state?.conversation?.remaining_turns;
    const noTurns = typeof remainingTurns === "number" && remainingTurns <= 0;
    const searchRemaining = state?.limits?.search_remaining;
    const noSearch = mode !== "message" && typeof searchRemaining === "number" && searchRemaining <= 0;
    const researchDisabled = mode === "web" && state?.internet === false;
    const noDocument = mode === "document" && !ui["document-select"].value;
    ui.send.disabled = locked || !modelReady() || noTurns || noSearch || noDocument || researchDisabled || !ui.message.value.trim();
    ui.send.title = !connected ? "Actualisez pour retrouver la connexion locale."
      : !modelReady() ? "Vérifiez la disponibilité d’Ollama et du modèle."
      : noTurns ? "Ouvrez une nouvelle conversation pour poursuivre."
      : researchDisabled ? "arXiv est désactivé pour ce lancement."
      : noSearch ? "Les trois recherches documentaires et arXiv de cette conversation ont été utilisées."
      : noDocument ? "Importez ou choisissez un document."
      : "";
    ui.remember.disabled = locked || !ui["memory-text"].value.trim();
    const profileRemaining = state?.limits?.profile_commands_remaining;
    if (typeof profileRemaining === "number" && profileRemaining <= 0) {
      ui.remember.disabled = true;
      ui.recall.disabled = true;
    }
    const maxDocuments = state?.limits?.max_documents ?? 16;
    if ((state?.documents?.length ?? 0) >= maxDocuments || fileChooserOpen) ui["choose-document"].disabled = true;
    ui["document-select"].disabled = locked;
    ui["document-file"].disabled = locked;
    ui["recall-all"].disabled = !connected || stopped || refreshPending || localPending;
    ui.refresh.disabled = refreshPending || localPending;
    ui["suggest-hello"].disabled = locked;
    ui.message.disabled = stopped;
    ui["memory-text"].disabled = stopped;
    ui["recall-query"].disabled = stopped;
    ui["server-status"].textContent = stopped && shutdownConfirmed ? "Application arrêtée" : connected ? "Serveur local actif" : "Serveur local non joignable";
    ui["server-dot"].className = `status-dot ${stopped ? "" : connected ? "online" : "error"}`;
    if (!connected) {
      ui["ollama-status"].textContent = "Ollama · état inconnu";
      ui["model-status"].textContent = "Modèle · état inconnu";
      ui["ollama-status"].className = "status-pill";
      ui["model-status"].className = "status-pill";
    }
    ui.processing.hidden = !(localPending || state?.busy) || stopped || !connected;
    if (state?.busy && !localPending) {
      ui["processing-text"].textContent = actionLabels[state.operation?.action] || "Traitement en cours…";
    }
  }

  function setMode(nextMode, focus = true) {
    mode = nextMode;
    ["message", "document", "web"].forEach((name) => {
      const active = mode === name;
      ui[`mode-${name}`].classList.toggle("selected", active);
      ui[`mode-${name}`].setAttribute("aria-pressed", String(active));
    });
    ui["document-tools"].hidden = mode !== "document";
    ui.message.maxLength = mode === "web" ? 300 : mode === "document" ? 2048 : 8192;
    ui.message.placeholder = mode === "web" ? "Quel sujet rechercher sur arXiv ?" : mode === "document" ? "Votre question sur le document choisi…" : "Écrivez à Syn…";
    ui["message-label"].textContent = mode === "web" ? "Mots-clés de la recherche scientifique arXiv" : mode === "document" ? "Question sur le document choisi" : "Votre message à Syn";
    ui["send-label"].textContent = mode === "web" ? "Rechercher" : "Envoyer";
    ui["mode-explanation"].textContent = mode === "web"
      ? state?.internet === false ? "La recherche arXiv est désactivée pour ce lancement. Rouvrez Syn avec la recherche scientifique activée."
      : "Recherche sur arXiv uniquement, suivie d’une synthèse locale. Seuls vos mots-clés sont envoyés à arXiv · 300 caractères maximum."
      : mode === "document"
      ? "Documents .txt et .md · 256 Kio maximum par fichier. Syn s’appuie sur les extraits retrouvés, avec leurs références."
      : "Votre modèle local peut se tromper. Les détails de chaque réponse restent consultables.";
    updateControls();
    if (focus) ui.message.focus();
  }

  function openPanel(name, focus = false) {
    ["memory", "sources"].forEach((tab) => {
      const active = name === tab;
      ui[`tab-${tab}`].classList.toggle("selected", active);
      ui[`tab-${tab}`].setAttribute("aria-selected", String(active));
      ui[`tab-${tab}`].tabIndex = active ? 0 : -1;
      ui[`panel-${tab}`].hidden = !active;
      ui[`nav-${tab}`].classList.toggle("active", active);
    });
    ui["nav-conversation"].classList.remove("active");
    ui["context-panel"].classList.add("open");
    if (focus) ui[`tab-${name}`].focus();
  }

  function closePanel() {
    ui["context-panel"].classList.remove("open");
    ui["nav-conversation"].classList.add("active");
    ui["nav-memory"].classList.remove("active");
    ui["nav-sources"].classList.remove("active");
  }

  function renderMessages(messages) {
    const signature = JSON.stringify(messages);
    if (signature === messagesSignature) return;
    messagesSignature = signature;
    const nearBottom = ui["message-scroll"].scrollHeight - ui["message-scroll"].scrollTop - ui["message-scroll"].clientHeight < 130;
    const fragment = document.createDocumentFragment();
    messages.forEach((entry) => {
      const role = entry.role === "user" ? "user" : "assistant";
      const message = element("article", `message ${role}${entry.error ? " error" : ""}`);
      const avatar = element("div", "avatar", entry.error ? "!" : role === "user" ? "V" : "s");
      avatar.setAttribute("aria-hidden", "true");
      const body = element("div", "message-body");
      const head = element("div", "message-head");
      head.append(element("span", "message-role", role === "user" ? "Vous" : "Syn"));
      const receipt = entry.receipt;
      if (role === "assistant" && receipt && typeof receipt === "object") {
        const kindLabels = { memory_saved: "Mémoire locale", memory_lookup: "Mémoire locale", arxiv_search: "Recherche arXiv", upload_document: "Document local" };
        if (receipt.kind) head.append(element("span", "message-kind", kindLabels[receipt.kind] || "Opération locale"));
      }
      if (entry.error) head.append(element("span", "message-kind", "Erreur"));
      body.append(head, element("div", "message-text", entry.content ?? ""));
      if (receipt && typeof receipt === "object") {
        if (Array.isArray(receipt.source_references) && receipt.source_references.length) {
          const references = element("div", "response-references");
          receipt.source_references.forEach((reference) => {
            const label = reference.alias ? `[${reference.alias}]` : "Source";
            const badge = element("span", `reference-badge${reference.cited ? " cited" : ""}`, `${label} · ${reference.cited ? "citée" : "fournie au modèle"}`);
            badge.title = String(reference.path || reference.id || "");
            references.append(badge);
          });
          body.append(references);
        }
        const details = element("details", "trace-details");
        details.append(element("summary", "", "Détails · trace de cette réponse"));
        details.append(element("pre", "", JSON.stringify({
          receipt,
          session: {
            conversation_id: state?.conversation?.id,
            model_configure: state?.provider?.model,
            dernier_modele_utilise: state?.provider?.last_model,
            journaux: state?.conversation?.output,
            transport_trace_path: state?.transport_trace_path
          }
        }, null, 2)));
        body.append(details);
      }
      message.append(avatar, body);
      fragment.append(message);
    });
    ui.messages.replaceChildren(fragment);
    ui.welcome.hidden = messages.length > 0;
    if (nearBottom || localPending) requestAnimationFrame(() => { ui["message-scroll"].scrollTop = ui["message-scroll"].scrollHeight; });
  }

  function emptyPanel(icon, title, text) {
    const empty = element("div", "empty-panel");
    const mark = element("span", "empty-icon", icon);
    mark.setAttribute("aria-hidden", "true");
    empty.append(mark, element("strong", "", title), element("p", "", text));
    return empty;
  }

  function renderMemories(memories) {
    ui["memory-count"].textContent = String(memories.length);
    ui["nav-memory-count"].textContent = String(memories.length);
    const signature = JSON.stringify(memories);
    if (signature === memoriesSignature) return;
    memoriesSignature = signature;
    const fragment = document.createDocumentFragment();
    if (!memories.length) fragment.append(emptyPanel("◇", "La mémoire commence avec vous.", "Ajoutez un premier souvenir. Il restera disponible après le redémarrage."));
    memories.forEach((memory) => {
      const card = element("article", "memory-card");
      card.append(element("p", "", memory.text ?? ""));
      card.append(element("div", "card-meta", `Souvenir déclaré · non vérifié\n${dateLabel(memory.created_at)}`));
      fragment.append(card);
    });
    ui.memories.replaceChildren(fragment);
  }

  function renderSources(sources) {
    ui["source-count"].textContent = String(sources.length);
    ui["nav-source-count"].textContent = String(sources.length);
    const signature = JSON.stringify(sources);
    if (signature === sourcesSignature) return;
    sourcesSignature = signature;
    const fragment = document.createDocumentFragment();
    if (!sources.length) fragment.append(emptyPanel("▤", "Vos sources apparaîtront ici.", "Importez un document ou lancez une recherche scientifique."));
    sources.forEach((source) => {
      const card = element("article", "source-card");
      card.append(element("h3", "source-title", source.title || "Document local"));
      const location = element("div", "source-location");
      const url = arxivUrl(source.path);
      if (url) {
        const link = element("a", "", String(source.path));
        link.href = url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        location.append(link);
      } else {
        location.textContent = `${source.path || "Document local"}${source.line ? ` · ligne ${source.line}` : ""}`;
      }
      card.append(location);
      const tags = element("div", "source-tags");
      tags.append(element("span", "source-tag", "Consultée"));
      if (source.supplied === true) tags.append(element("span", "source-tag supplied", "Fournie au modèle"));
      if (source.cited === true) tags.append(element("span", "source-tag cited", `Citée${source.alias ? ` [${source.alias}]` : ""}`));
      else if (source.supplied === true) tags.append(element("span", "source-tag", "Citation non repérée"));
      card.append(tags, element("p", "source-excerpt", source.text ?? ""));
      card.append(element("div", "source-receipt", `Consultée le ${dateLabel(source.retrieved_at)}\nReçu : ${source.receipt_id || "non fourni"}`));
      const details = element("details", "");
      details.append(element("summary", "", "Détails de la source"));
      details.append(element("pre", "", JSON.stringify(source, null, 2)));
      card.append(details);
      fragment.append(card);
    });
    ui["source-list"].replaceChildren(fragment);
  }

  function renderDocuments(documents) {
    const signature = JSON.stringify(documents);
    if (signature === documentsSignature) return;
    documentsSignature = signature;
    const previous = ui["document-select"].value || selectedDocumentId;
    const fragment = document.createDocumentFragment();
    const placeholder = element("option", "", documents.length ? "Choisir un document…" : "Importez un document pour commencer…");
    placeholder.value = "";
    fragment.append(placeholder);
    documents.forEach((documentEntry) => {
      const option = element("option", "", documentEntry.name || "Document local");
      option.value = String(documentEntry.id);
      fragment.append(option);
    });
    ui["document-select"].replaceChildren(fragment);
    if (state?.operation?.action === "upload_document" && state.operation.status === "succeeded" && documents.length) ui["document-select"].value = String(documents[documents.length - 1].id);
    else if (documents.some((documentEntry) => String(documentEntry.id) === previous)) ui["document-select"].value = previous;
    else if (documents.length) ui["document-select"].value = String(documents[documents.length - 1].id);
    selectedDocumentId = ui["document-select"].value;
  }

  function render(snapshot) {
    state = snapshot;
    const provider = snapshot.provider || {};
    ui["model-name"].textContent = provider.last_model ? `Utilisé : ${provider.last_model}` : provider.model ? `Choisi : ${provider.model}` : "Modèle non configuré";
    if (provider.digest) ui["model-name"].title = `Identifiant du modèle installé : ${provider.digest}`;
    else ui["model-name"].removeAttribute("title");
    ui["ollama-status"].textContent = provider.available === true ? "Ollama · connecté" : provider.available === false ? "Ollama · indisponible" : "Ollama · vérification";
    ui["model-status"].textContent = provider.model_available === true ? "Modèle · prêt" : provider.model_available === false ? "Modèle · indisponible" : "Modèle · vérification";
    ui["ollama-status"].className = `status-pill ${provider.available === true ? "ok" : provider.available === false ? "error" : ""}`;
    ui["model-status"].className = `status-pill ${provider.model_available === true ? "ok" : provider.model_available === false ? "error" : ""}`;
    const conversation = snapshot.conversation || {};
    ui["turns-label"].textContent = typeof conversation.remaining_turns === "number" ? `${conversation.remaining_turns} / ${conversation.max_turns} échanges restants` : "Session locale";
    renderMessages(Array.isArray(conversation.messages) ? conversation.messages : []);
    renderMemories(Array.isArray(snapshot.memories) ? snapshot.memories : []);
    renderSources(Array.isArray(snapshot.sources) ? snapshot.sources : []);
    renderDocuments(Array.isArray(snapshot.documents) ? snapshot.documents : []);
    setMode(mode, false);
    if (!snapshot.busy) localPending = false;
    const operation = snapshot.operation || {};
    if (operation.id && operation.id !== lastOperationId && ["succeeded", "failed"].includes(operation.status)) {
      lastOperationId = operation.id;
      if (operation.status === "failed") {
        if (operation.action === "shutdown") shutdownRequested = false;
        showNotification(operation.error || snapshot.last_error || "L’opération a échoué. Corrigez votre demande ou vérifiez le moteur, puis réessayez.");
      } else {
        if (operation.action === "shutdown") {
          shutdownConfirmed = true;
          stopped = true;
          connected = false;
          localPending = false;
        }
        const successLabels = {
          remember: "Souvenir enregistré dans votre profil local.",
          recall: "Mémoire consultée. Le résultat apparaît dans la conversation.",
          upload_document: "Document importé. Vous pouvez maintenant poser une question à son sujet.",
          new_conversation: "Nouvelle conversation ouverte. Votre mémoire et vos documents restent disponibles.",
          shutdown: "Application arrêtée. Pour la rouvrir, utilisez le raccourci « Ouvrir Syn »."
        };
        showNotification(successLabels[operation.action] || "", operation.action === "shutdown" ? "stopped" : "success", false);
        if (operation.action === "upload_document") setMode("document", false);
      }
    }
    if (provider.available === false && !snapshot.busy && !stopped) {
      showNotification("Ollama n’est pas joignable. Démarrez le fournisseur local, puis actualisez pour reprendre.");
    } else if (provider.model_available === false && !snapshot.busy && !stopped) {
      showNotification(`Le modèle « ${provider.model || "configuré"} » n’est pas disponible dans Ollama. Vérifiez le modèle déjà installé, puis actualisez.`);
    } else if (typeof conversation.remaining_turns === "number" && conversation.remaining_turns <= 0 && !snapshot.busy && !stopped) {
      showNotification("Cette conversation a atteint sa limite. Ouvrez une nouvelle conversation pour poursuivre.", "success", false);
    }
    updateControls();
  }

  async function fetchJson(path, options = {}) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
      const response = await fetch(path, { ...options, signal: controller.signal, cache: "no-store", credentials: "same-origin" });
      const contentType = response.headers.get("Content-Type") || "";
      let data = {};
      if (contentType.includes("application/json")) data = await response.json();
      if (!response.ok) {
        const failure = new Error(typeof data.error === "string" ? data.error : typeof data.message === "string" ? data.message : `La requête locale a échoué (HTTP ${response.status}).`);
        failure.httpStatus = response.status;
        throw failure;
      }
      if (!contentType.includes("application/json")) throw new Error("Le serveur local n’a pas retourné un état valide.");
      return data;
    } finally {
      clearTimeout(timeout);
    }
  }

  function clearPoll() {
    if (pollTimer !== null) clearTimeout(pollTimer);
    pollTimer = null;
  }

  function schedulePoll() {
    clearPoll();
    if (!state?.busy || !connected || stopped) return;
    if (Date.now() >= pollDeadline) {
      showNotification("Le traitement dure plus longtemps que prévu. Il peut encore être en cours : actualisez pour vérifier son état. Aucune demande n’est relancée automatiquement.");
      updateControls();
      return;
    }
    pollTimer = setTimeout(() => { refreshState(false); }, 1000);
  }

  async function refreshState(manual = true) {
    if (refreshPending || localPending && !state?.busy) return;
    clearPoll();
    refreshPending = true;
    updateControls();
    try {
      const snapshot = await fetchJson("/api/state");
      if (snapshot.app !== "synergesis-local-ui" || !snapshot.csrf_token || !snapshot.instance_id) throw new Error("Ce serveur ne correspond pas à l’application locale Syn.");
      const wasConnected = connected;
      connected = true;
      stopped = false;
      if (manual) {
        pollDeadline = Date.now() + POLL_WINDOW_MS;
        showNotification("");
      }
      if (snapshot.busy && (!state?.busy || !wasConnected)) pollDeadline = Date.now() + POLL_WINDOW_MS;
      render(snapshot);
    } catch (error) {
      connected = false;
      localPending = false;
      if (shutdownRequested) stopped = true;
      showNotification(shutdownRequested && !shutdownConfirmed
        ? "Arrêt demandé. Le serveur local n’est plus joignable. Utilisez « Ouvrir Syn » pour rouvrir l’application."
        : stopped
        ? "Application arrêtée. Utilisez le raccourci « Ouvrir Syn » pour la rouvrir."
        : "Le serveur local n’est pas joignable. Rouvrez « Ouvrir Syn », puis actualisez. Une demande interrompue n’est pas relancée automatiquement.", stopped ? "stopped" : "error");
    } finally {
      refreshPending = false;
      updateControls();
      schedulePoll();
    }
  }

  // The lock is set synchronously, before reading a file or beginning any request.
  async function executeAction(action, payload = {}, options = {}) {
    if (activeLock()) return;
    localPending = true;
    clearPoll();
    ui["processing-text"].textContent = actionLabels[action] || "Traitement en cours…";
    showNotification("");
    updateControls();
    let accepted = false;
    try {
      if (options.prepare) payload = await options.prepare();
      const requestId = crypto.randomUUID();
      await fetchJson("/api/action", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Syn-Token": state.csrf_token },
        body: JSON.stringify({ request_id: requestId, action, ...payload })
      });
      accepted = true;
      if (options.onAccepted) options.onAccepted();
      if (action === "shutdown") {
        shutdownRequested = true;
        showNotification("Arrêt demandé. Le serveur termine l’opération…", "success", false);
      }
      pollDeadline = Date.now() + POLL_WINDOW_MS;
      // Keep the lock while obtaining the accepted operation’s first snapshot.
      const snapshot = await fetchJson("/api/state");
      if (snapshot.app !== "synergesis-local-ui" || !snapshot.csrf_token || snapshot.instance_id !== state.instance_id) throw new Error("Le serveur local a changé pendant l’opération. Actualisez avant de poursuivre.");
      render(snapshot);
    } catch (error) {
      localPending = false;
      if (error.httpStatus) {
        showNotification(error.httpStatus === 409 ? "Une autre opération est déjà en cours. Actualisez pour consulter son état." : error.message);
        if (error.httpStatus === 409) {
          await refreshState(true);
          showNotification("Une autre opération est déjà en cours. Attendez sa fin avant de poursuivre.", "success", false);
        }
      } else if (error.localValidation) {
        showNotification(error.message, "error", false);
      } else {
        connected = false;
        if (action === "shutdown" && accepted) stopped = true;
        showNotification(action === "shutdown" && accepted
          ? "Arrêt demandé. Le serveur local n’est plus joignable. Utilisez « Ouvrir Syn » pour rouvrir l’application."
          : accepted
          ? "La demande a été acceptée, mais la connexion locale a été interrompue. Actualisez pour connaître le résultat. La demande ne sera pas renvoyée automatiquement."
          : "Le serveur local ne répond plus. La demande a pu être reçue : actualisez son état avant de réessayer. Aucune demande n’est renvoyée automatiquement.");
      }
    } finally {
      if (!state?.busy || !accepted) localPending = false;
      updateControls();
      schedulePoll();
    }
  }

  function sendMessage() {
    const text = ui.message.value.trim();
    if (!text || activeLock()) return;
    if (!modelReady()) {
      showNotification("Le modèle local n’est pas disponible. Vérifiez Ollama et le modèle, puis actualisez.");
      return;
    }
    if (ui.send.disabled) return;
    if (mode === "document" && text.length > 2048) {
      showNotification("La question sur un document accepte au maximum 2048 caractères. Raccourcissez votre question.", "error", false);
      return;
    }
    if (mode === "web" && /[\r\n\t]/.test(text)) {
      showNotification("La recherche arXiv doit tenir sur une seule ligne. Utilisez des mots-clés courts.", "error", false);
      return;
    }
    if (mode === "web" && text.length > 300) {
      showNotification("La recherche arXiv accepte au maximum 300 caractères. Raccourcissez vos mots-clés.", "error", false);
      return;
    }
    if (mode === "document" && !ui["document-select"].value) {
      showNotification("Importez ou choisissez un document avant de poser votre question.", "error", false);
      return;
    }
    const action = mode === "document" ? "document_question" : mode;
    const payload = { text };
    if (action === "document_question") payload.document_id = ui["document-select"].value;
    executeAction(action, payload, { onAccepted: () => { ui.message.value = ""; } });
  }

  function validationError(message) {
    const error = new Error(message);
    error.localValidation = true;
    return error;
  }

  function readDocument(file) {
    const maxBytes = state?.limits?.max_document_bytes ?? 262144;
    if (!/\.(txt|md)$/i.test(file.name)) throw validationError("Format refusé. Choisissez un document .txt ou .md.");
    if (file.size > maxBytes) throw validationError("Le document dépasse la limite de 256 Kio. Choisissez un fichier plus petit.");
    if (file.size === 0) throw validationError("Le document est vide. Choisissez un fichier contenant du texte.");
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const content = String(reader.result ?? "");
        if (!content.trim()) return reject(validationError("Le document ne contient aucun texte utilisable."));
        if (content.includes("\u0000")) return reject(validationError("Ce document contient des données binaires. Choisissez un fichier texte UTF-8."));
        if (new TextEncoder().encode(content).byteLength > maxBytes) return reject(validationError("Le texte importé dépasse la limite de 256 Kio."));
        resolve({ name: file.name, content });
      };
      reader.onerror = () => reject(validationError("Le fichier n’a pas pu être lu. Choisissez-le à nouveau."));
      reader.onabort = () => reject(validationError("La lecture du fichier a été interrompue."));
      reader.readAsText(file, "UTF-8");
    });
  }

  ui["message-form"].addEventListener("submit", (event) => { event.preventDefault(); sendMessage(); });
  ui.message.addEventListener("input", updateControls);
  ui.message.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      sendMessage();
    }
  });
  ["message", "document", "web"].forEach((name) => { ui[`mode-${name}`].addEventListener("click", () => setMode(name)); });
  ui["suggest-hello"].addEventListener("click", () => { setMode("message"); ui.message.value = "Bonjour Syn"; updateControls(); ui.message.focus(); });
  ui["suggest-document"].addEventListener("click", () => { setMode("document"); });
  ui["new-conversation"].addEventListener("click", () => {
    executeAction("new_conversation", {}, { onAccepted: () => { ui.message.value = ""; setMode("message"); } });
  });
  ui.shutdown.addEventListener("click", () => executeAction("shutdown"));
  ui.refresh.addEventListener("click", () => refreshState(true));
  ui["nav-conversation"].addEventListener("click", () => { closePanel(); ui.message.focus(); });
  ui["nav-memory"].addEventListener("click", () => openPanel("memory", true));
  ui["nav-sources"].addEventListener("click", () => openPanel("sources", true));
  ui["close-panel"].addEventListener("click", () => { closePanel(); ui["nav-conversation"].focus(); });
  ["memory", "sources"].forEach((name) => {
    ui[`tab-${name}`].addEventListener("click", () => openPanel(name));
    ui[`tab-${name}`].addEventListener("keydown", (event) => {
      if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
        event.preventDefault();
        openPanel(event.key === "Home" ? "memory" : event.key === "End" ? "sources" : name === "memory" ? "sources" : "memory", true);
      }
    });
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && ui["context-panel"].classList.contains("open")) { closePanel(); ui["nav-conversation"].focus(); }
  });
  ui["memory-text"].addEventListener("input", updateControls);
  ui["memory-form"].addEventListener("submit", (event) => {
    event.preventDefault();
    const text = ui["memory-text"].value.trim();
    if (text) executeAction("remember", { text }, { onAccepted: () => { ui["memory-text"].value = ""; } });
  });
  ui["recall-form"].addEventListener("submit", (event) => {
    event.preventDefault();
    const text = ui["recall-query"].value.trim();
    if (text) executeAction("recall", { text });
  });
  ui["recall-all"].addEventListener("click", () => refreshState(true));
  ui["document-select"].addEventListener("change", () => { selectedDocumentId = ui["document-select"].value; updateControls(); });
  ui["choose-document"].addEventListener("click", () => {
    if (activeLock() || fileChooserOpen) return;
    fileChooserOpen = true;
    ui["document-file"].value = "";
    updateControls();
    ui["document-file"].click();
  });
  ui["document-file"].addEventListener("cancel", () => { fileChooserOpen = false; updateControls(); });
  ui["document-file"].addEventListener("change", () => {
    fileChooserOpen = false;
    const file = ui["document-file"].files?.[0];
    if (file) executeAction("upload_document", {}, { prepare: () => readDocument(file) });
    else updateControls();
  });

  updateControls();
  refreshState(true);
})();
