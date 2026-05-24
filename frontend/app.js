/**
 * Frontend controller for GenericRagGenerator.
 * CSP-compliant: no inline scripts, no eval, all listeners attached in JS.
 */

const API = {
  health: "/api/health",
  documents: "/api/documents",
  repositories: "/api/repositories",
  chat: "/api/chat",
};

const elements = {
  healthPill: document.getElementById("health-pill"),
  uploadForm: document.getElementById("upload-form"),
  uploadBtn: document.getElementById("upload-btn"),
  uploadStatus: document.getElementById("upload-status"),
  fileInput: document.getElementById("file-input"),
  documentList: document.getElementById("document-list"),
  repoForm: document.getElementById("repo-form"),
  repoBtn: document.getElementById("repo-btn"),
  repoStatus: document.getElementById("repo-status"),
  repoInput: document.getElementById("repo-input"),
  repositoryList: document.getElementById("repository-list"),
  chatForm: document.getElementById("chat-form"),
  chatInput: document.getElementById("chat-input"),
  chatSend: document.getElementById("chat-send"),
  chatLog: document.getElementById("chat-log"),
};

const state = {
  history: [],
};

/**
 * Bootstrap the UI: probe health, load documents, wire event listeners.
 * @returns {Promise<void>}
 */
async function bootstrap() {
  attachListeners();
  await Promise.all([refreshHealth(), refreshDocuments(), refreshRepositories()]);
}

/**
 * Wire DOM event listeners.
 * @returns {void}
 */
function attachListeners() {
  elements.uploadForm.addEventListener("submit", handleUpload);
  elements.repoForm.addEventListener("submit", handleRepoUpload);
  elements.chatForm.addEventListener("submit", handleChat);
  elements.chatInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      elements.chatForm.requestSubmit();
    }
  });
}

/**
 * Probe `/api/health` and update the status pill.
 * @returns {Promise<void>}
 */
async function refreshHealth() {
  try {
    const response = await fetch(API.health);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const payload = await response.json();
    const reachable = payload.ollama_reachable === true;
    setPill(reachable ? "ok" : "down", reachable ? "online" : "ollama down");
  } catch (error) {
    setPill("down", "offline");
  }
}

/**
 * Update the status pill with a given variant and label.
 * @param {"ok"|"down"|"unknown"} variant Visual variant.
 * @param {string} label Text to display.
 * @returns {void}
 */
function setPill(variant, label) {
  elements.healthPill.className = `pill pill--${variant}`;
  elements.healthPill.textContent = label;
}

/**
 * Reload the indexed-document list from the backend.
 * @returns {Promise<void>}
 */
async function refreshDocuments() {
  try {
    const response = await fetch(API.documents);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const documents = await response.json();
    renderDocuments(documents);
  } catch (error) {
    elements.documentList.innerHTML = "";
    setUploadStatus(`Failed to load documents: ${error.message}`, "error");
  }
}

/**
 * Render the sidebar list of indexed documents.
 * @param {Array<{id:string, filename:string, chunks:number, uploaded_at:string}>} documents
 * @returns {void}
 */
function renderDocuments(documents) {
  elements.documentList.innerHTML = "";
  if (!documents.length) {
    const empty = document.createElement("li");
    empty.className = "empty";
    empty.textContent = "No documents yet.";
    elements.documentList.appendChild(empty);
    return;
  }
  for (const document_ of documents) {
    elements.documentList.appendChild(buildDocumentItem(document_));
  }
}

/**
 * Build a single `<li>` for a document.
 * @param {{id:string, filename:string, chunks:number}} document_ Document metadata.
 * @returns {HTMLLIElement}
 */
function buildDocumentItem(document_) {
  const item = document.createElement("li");
  item.className = "document";

  const text = document.createElement("div");
  const name = document.createElement("div");
  name.className = "document__name";
  name.textContent = document_.filename;
  const meta = document.createElement("div");
  meta.className = "document__meta";
  meta.textContent = `${document_.chunks} chunks`;
  text.append(name, meta);

  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "document__delete";
  remove.textContent = "remove";
  remove.addEventListener("click", () => handleDelete(document_.id));

  item.append(text, remove);
  return item;
}

/**
 * Submit the upload form.
 * @param {SubmitEvent} event Form submit event.
 * @returns {Promise<void>}
 */
async function handleUpload(event) {
  event.preventDefault();
  const file = elements.fileInput.files?.[0];
  if (!file) {
    setUploadStatus("Pick a file first.", "error");
    return;
  }
  toggleUpload(true);
  setUploadStatus(`Uploading ${file.name}…`, "info");

  try {
    const body = new FormData();
    body.append("file", file);
    const response = await fetch(API.documents, { method: "POST", body });
    if (!response.ok) {
      const detail = await safeDetail(response);
      throw new Error(detail);
    }
    const payload = await response.json();
    setUploadStatus(`Indexed ${payload.document.filename} (${payload.document.chunks} chunks).`, "success");
    elements.uploadForm.reset();
    await refreshDocuments();
  } catch (error) {
    setUploadStatus(`Upload failed: ${error.message}`, "error");
  } finally {
    toggleUpload(false);
  }
}

/**
 * Delete a document by id.
 * @param {string} documentId Identifier of the document to remove.
 * @returns {Promise<void>}
 */
async function handleDelete(documentId) {
  try {
    const response = await fetch(`${API.documents}/${documentId}`, { method: "DELETE" });
    if (!response.ok && response.status !== 204) {
      throw new Error(await safeDetail(response));
    }
    await refreshDocuments();
  } catch (error) {
    setUploadStatus(`Delete failed: ${error.message}`, "error");
  }
}

/**
 * Reload the indexed-repository list from the backend.
 * @returns {Promise<void>}
 */
async function refreshRepositories() {
  try {
    const response = await fetch(API.repositories);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const repos = await response.json();
    renderRepositories(repos);
  } catch (error) {
    elements.repositoryList.innerHTML = "";
    setRepoStatus(`Failed to load repositories: ${error.message}`, "error");
  }
}

/**
 * Render the sidebar list of indexed repositories.
 * @param {Array<{id:string,name:string,total_chunks:number,uploaded_at:string}>} repos
 * @returns {void}
 */
function renderRepositories(repos) {
  elements.repositoryList.innerHTML = "";
  if (!repos.length) {
    const empty = document.createElement("li");
    empty.className = "empty";
    empty.textContent = "No repositories yet.";
    elements.repositoryList.appendChild(empty);
    return;
  }
  for (const repo of repos) {
    elements.repositoryList.appendChild(buildRepositoryItem(repo));
  }
}

/**
 * Build a single `<li>` for a repository entry.
 * @param {{id:string,name:string,total_chunks:number}} repo Repository metadata.
 * @returns {HTMLLIElement}
 */
function buildRepositoryItem(repo) {
  const item = document.createElement("li");
  item.className = "document";

  const text = document.createElement("div");
  const name = document.createElement("div");
  name.className = "document__name";
  name.textContent = repo.name || repo.id;
  const meta = document.createElement("div");
  meta.className = "document__meta";
  meta.textContent = `${repo.total_chunks} chunks`;
  text.append(name, meta);

  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "document__delete";
  remove.textContent = "remove";
  remove.addEventListener("click", () => handleRepoDelete(repo.id));

  item.append(text, remove);
  return item;
}

/**
 * Submit the repository ZIP upload form.
 * @param {SubmitEvent} event Form submit event.
 * @returns {Promise<void>}
 */
async function handleRepoUpload(event) {
  event.preventDefault();
  const file = elements.repoInput.files?.[0];
  if (!file) {
    setRepoStatus("Pick a ZIP file first.", "error");
    return;
  }
  toggleRepoUpload(true);
  setRepoStatus(`Uploading ${file.name}…`, "info");

  try {
    const body = new FormData();
    body.append("file", file);
    const response = await fetch(API.repositories, { method: "POST", body });
    if (!response.ok) {
      throw new Error(await safeDetail(response));
    }
    const payload = await response.json();
    const repository = payload.repository;
    const summary = `${repository.files_indexed} files (${repository.total_chunks} chunks)`;
    const skipped = repository.skipped?.length
      ? ` — skipped ${repository.skipped.length}`
      : "";
    setRepoStatus(`Indexed ${repository.name}: ${summary}${skipped}.`, "success");
    elements.repoForm.reset();
    await refreshRepositories();
  } catch (error) {
    setRepoStatus(`Upload failed: ${error.message}`, "error");
  } finally {
    toggleRepoUpload(false);
  }
}

/**
 * Delete a repository by id.
 * @param {string} repositoryId Repository identifier.
 * @returns {Promise<void>}
 */
async function handleRepoDelete(repositoryId) {
  try {
    const response = await fetch(`${API.repositories}/${repositoryId}`, { method: "DELETE" });
    if (!response.ok && response.status !== 204) {
      throw new Error(await safeDetail(response));
    }
    await refreshRepositories();
  } catch (error) {
    setRepoStatus(`Delete failed: ${error.message}`, "error");
  }
}

/**
 * Send a chat message and stream the assistant response.
 * @param {SubmitEvent} event Form submit event.
 * @returns {Promise<void>}
 */
async function handleChat(event) {
  event.preventDefault();
  const content = elements.chatInput.value.trim();
  if (!content) {
    return;
  }
  appendMessage("user", content);
  state.history.push({ role: "user", content });
  elements.chatInput.value = "";
  toggleChat(true);

  const assistantBubble = appendMessage("assistant", "");
  let accumulated = "";

  try {
    const response = await fetch(API.chat, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: state.history }),
    });
    if (!response.ok || !response.body) {
      throw new Error(await safeDetail(response));
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) {
        if (!line.trim()) {
          continue;
        }
        accumulated = handleEvent(JSON.parse(line), assistantBubble, accumulated);
      }
    }
    if (accumulated) {
      state.history.push({ role: "assistant", content: accumulated });
    }
  } catch (error) {
    assistantBubble.textContent = `Error: ${error.message}`;
  } finally {
    toggleChat(false);
    elements.chatInput.focus();
  }
}

/**
 * Apply one streamed event to the assistant bubble.
 * @param {{type:string, [key:string]:any}} event Decoded event payload.
 * @param {HTMLElement} bubble Assistant message element being updated.
 * @param {string} accumulated Current accumulated response text.
 * @returns {string} Updated accumulated text.
 */
function handleEvent(event, bubble, accumulated) {
  if (event.type === "sources") {
    renderSources(bubble, event.sources ?? []);
    return accumulated;
  }
  if (event.type === "delta") {
    const next = accumulated + (event.content ?? "");
    setBubbleText(bubble, next);
    elements.chatLog.scrollTop = elements.chatLog.scrollHeight;
    return next;
  }
  if (event.type === "error") {
    setBubbleText(bubble, `Error: ${event.message ?? "unknown"}`);
    return accumulated;
  }
  return accumulated;
}

/**
 * Render the citation chips above an assistant bubble.
 * @param {HTMLElement} bubble Assistant message element.
 * @param {Array<{filename:string,kind?:string,line_start?:number,line_end?:number,repository_name?:string,preview?:string}>} sources Source descriptors.
 * @returns {void}
 */
function renderSources(bubble, sources) {
  const existing = bubble.querySelector(".sources");
  if (existing) {
    existing.remove();
  }
  if (!sources.length) {
    return;
  }
  const container = document.createElement("div");
  container.className = "sources";
  const seen = new Set();
  for (const source of sources) {
    const key = sourceKey(source);
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    container.appendChild(buildSourceChip(source));
  }
  bubble.prepend(container);
}

/**
 * Stable de-duplication key for a source (path + line range).
 * @param {{filename:string,line_start?:number,line_end?:number}} source Source descriptor.
 * @returns {string} Composite key.
 */
function sourceKey(source) {
  const range = source.line_start ? `:${source.line_start}-${source.line_end}` : "";
  return `${source.filename}${range}`;
}

/**
 * Build one citation chip element.
 * @param {{filename:string,kind?:string,line_start?:number,line_end?:number,repository_name?:string,preview?:string}} source Source descriptor.
 * @returns {HTMLSpanElement}
 */
function buildSourceChip(source) {
  const chip = document.createElement("span");
  const isCode = source.kind === "code";
  chip.className = isCode ? "source source--code" : "source";

  const kind = document.createElement("span");
  kind.className = "source__kind";
  kind.textContent = isCode ? "code" : "doc";
  chip.appendChild(kind);

  const path = document.createElement("span");
  path.className = "source__path";
  const prefix = source.repository_name ? `${source.repository_name}/` : "";
  path.textContent = `${prefix}${source.filename}`;
  chip.appendChild(path);

  if (source.line_start && source.line_end) {
    const lines = document.createElement("span");
    lines.className = "source__lines";
    lines.textContent = `:${source.line_start}-${source.line_end}`;
    chip.appendChild(lines);
  }
  chip.title = source.preview ?? "";
  return chip;
}

/**
 * Append a chat message bubble to the log.
 * @param {"user"|"assistant"} role Speaker role.
 * @param {string} content Initial text content.
 * @returns {HTMLLIElement} The created bubble element.
 */
function appendMessage(role, content) {
  const item = document.createElement("li");
  item.className = `message message--${role}`;
  const body = document.createElement("span");
  body.className = "message__body";
  body.textContent = content;
  item.appendChild(body);
  elements.chatLog.appendChild(item);
  elements.chatLog.scrollTop = elements.chatLog.scrollHeight;
  return item;
}

/**
 * Replace the textual content of a bubble while preserving its source chips.
 * @param {HTMLElement} bubble Bubble element.
 * @param {string} text New text.
 * @returns {void}
 */
function setBubbleText(bubble, text) {
  let body = bubble.querySelector(".message__body");
  if (!body) {
    body = document.createElement("span");
    body.className = "message__body";
    bubble.appendChild(body);
  }
  body.textContent = text;
}

/**
 * Toggle upload form interactivity.
 * @param {boolean} busy Whether the upload is in progress.
 * @returns {void}
 */
function toggleUpload(busy) {
  elements.uploadBtn.disabled = busy;
  elements.fileInput.disabled = busy;
}

/**
 * Toggle repository upload form interactivity.
 * @param {boolean} busy Whether the repo upload is in progress.
 * @returns {void}
 */
function toggleRepoUpload(busy) {
  elements.repoBtn.disabled = busy;
  elements.repoInput.disabled = busy;
}

/**
 * Set the repository upload status message.
 * @param {string} message Text to display.
 * @param {"info"|"error"|"success"} variant Visual variant.
 * @returns {void}
 */
function setRepoStatus(message, variant) {
  elements.repoStatus.textContent = message;
  elements.repoStatus.className = `status status--${variant}`;
}

/**
 * Toggle chat form interactivity.
 * @param {boolean} busy Whether a chat request is in flight.
 * @returns {void}
 */
function toggleChat(busy) {
  elements.chatSend.disabled = busy;
  elements.chatInput.disabled = busy;
}

/**
 * Set the upload status message.
 * @param {string} message Text to display.
 * @param {"info"|"error"|"success"} variant Visual variant.
 * @returns {void}
 */
function setUploadStatus(message, variant) {
  elements.uploadStatus.textContent = message;
  elements.uploadStatus.className = `status status--${variant}`;
}

/**
 * Best-effort extraction of a `detail` error message from a Response.
 * @param {Response} response HTTP response.
 * @returns {Promise<string>} Human-readable error.
 */
async function safeDetail(response) {
  try {
    const data = await response.json();
    if (typeof data?.detail === "string") {
      return data.detail;
    }
    return JSON.stringify(data);
  } catch {
    return `HTTP ${response.status}`;
  }
}

bootstrap();
