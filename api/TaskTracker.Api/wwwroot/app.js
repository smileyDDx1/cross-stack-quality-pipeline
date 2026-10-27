"use strict";

const TOKEN_KEY = "tasktracker.token";
const STATUS_LABELS = { todo: "To do", in_progress: "In progress", done: "Done", cancelled: "Cancelled" };
// Mirrors TaskWorkflow on the server so only sensible buttons are shown; the server stays the authority.
const TRANSITIONS = {
  todo: [["in_progress", "Start"], ["cancelled", "Cancel"]],
  in_progress: [["done", "Complete"], ["todo", "Back to to-do"], ["cancelled", "Cancel"]],
  done: [["in_progress", "Reopen"]],
  cancelled: [["todo", "Restore"]],
};

const $ = (id) => document.getElementById(id);
const state = { authMode: "login", user: null, projectId: null };

function getToken() {
  try { return sessionStorage.getItem(TOKEN_KEY); } catch { return null; }
}

function setToken(token) {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token);
    else sessionStorage.removeItem(TOKEN_KEY);
  } catch { /* storage unavailable: the session just won't survive a reload */ }
}

class ApiError extends Error {
  constructor(status, problem) {
    super(problemMessage(problem) || `Request failed (${status}).`);
    this.status = status;
    this.problem = problem;
  }
}

function problemMessage(problem) {
  if (!problem) return "";
  if (problem.errors) return Object.values(problem.errors).flat().join(" ");
  return problem.detail || problem.title || "";
}

async function api(method, path, body) {
  const headers = { Accept: "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const res = await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  if (res.status === 401 && token) {
    signOut();
    throw new ApiError(401, { title: "Your session has expired. Please sign in again." });
  }
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = null; }
  if (!res.ok) throw new ApiError(res.status, data);
  return data;
}

function el(tag, props = {}, dataset = {}) {
  const node = Object.assign(document.createElement(tag), props);
  Object.assign(node.dataset, dataset);
  return node;
}

function showError(id, message) {
  const node = $(id);
  node.textContent = message;
  node.hidden = false;
}

function hideError(id) {
  $(id).hidden = true;
}

function show(viewId) {
  for (const id of ["auth-view", "projects-view", "project-view"]) $(id).hidden = id !== viewId;
}

function navigate(hash) {
  if (location.hash === hash) route();
  else location.hash = hash;
}

function plural(count, word) {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

async function route() {
  if (!getToken()) {
    renderSession();
    show("auth-view");
    return;
  }
  try {
    if (!state.user) state.user = await api("GET", "/api/auth/me");
    renderSession();
    const match = location.hash.match(/^#\/projects\/([0-9a-f-]{36})$/i);
    if (match) await showProject(match[1]);
    else await showProjects();
  } catch (err) {
    if (err.status !== 401) console.error(err);
  }
}

function renderSession() {
  $("session").hidden = !state.user;
  $("current-user").textContent = state.user ? state.user.displayName : "";
}

function signOut() {
  setToken(null);
  state.user = null;
  navigate("#/login");
}

// --- Auth -----------------------------------------------------------------

function setAuthMode(mode) {
  state.authMode = mode;
  const register = mode === "register";
  $("auth-title").textContent = register ? "Create account" : "Sign in";
  $("auth-submit").textContent = register ? "Create account" : "Sign in";
  $("display-name-field").hidden = !register;
  $("auth-switch-text").textContent = register ? "Already registered?" : "No account?";
  $("auth-toggle").textContent = register ? "Sign in" : "Create one";
  hideError("auth-error");
}

$("auth-toggle").addEventListener("click", () => setAuthMode(state.authMode === "login" ? "register" : "login"));

$("auth-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.target);
  const credentials = { email: form.get("email"), password: form.get("password") };
  hideError("auth-error");
  $("auth-submit").disabled = true;
  try {
    if (state.authMode === "register") {
      await api("POST", "/api/auth/register", { ...credentials, displayName: form.get("displayName") });
    }
    const token = await api("POST", "/api/auth/login", credentials);
    setToken(token.accessToken);
    state.user = null;
    event.target.reset();
    setAuthMode("login");
    navigate("#/projects");
  } catch (err) {
    showError("auth-error", err.message);
  } finally {
    $("auth-submit").disabled = false;
  }
});

$("logout").addEventListener("click", signOut);

// --- Projects -------------------------------------------------------------

async function showProjects() {
  show("projects-view");
  const data = await api("GET", "/api/projects?pageSize=100");
  const list = $("project-list");
  list.replaceChildren();
  $("projects-empty").hidden = data.items.length > 0;
  for (const project of data.items) {
    const item = el("li", { className: "item" }, { testid: "project-card", projectId: project.id });
    item.append(
      el("a", { href: `#/projects/${project.id}`, textContent: project.name, className: "item-title" }, { testid: "project-link" }),
      el("span", {
        className: "muted",
        textContent: `${plural(project.taskCount, "task")} · ${project.openTaskCount} open`,
      }, { testid: "project-counts" }),
    );
    if (project.description) item.append(el("p", { className: "muted small", textContent: project.description }));
    list.append(item);
  }
}

$("project-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.target);
  hideError("project-error");
  try {
    await api("POST", "/api/projects", { name: form.get("name"), description: form.get("description") || null });
    event.target.reset();
    await showProjects();
  } catch (err) {
    showError("project-error", err.message);
  }
});

// --- Tasks ----------------------------------------------------------------

async function showProject(projectId) {
  show("project-view");
  if (state.projectId !== projectId) {
    state.projectId = projectId;
    $("status-filter").value = "";
    hideError("task-error");
  }
  let project;
  try {
    project = await api("GET", `/api/projects/${projectId}`);
  } catch (err) {
    if (err.status === 404) {
      navigate("#/projects");
      return;
    }
    throw err;
  }
  $("project-title").textContent = project.name;
  $("project-description-text").textContent = project.description || "";
  await loadTasks();
}

async function loadTasks() {
  const query = new URLSearchParams({ pageSize: "100" });
  const status = $("status-filter").value;
  if (status) query.set("status", status);
  const data = await api("GET", `/api/projects/${state.projectId}/tasks?${query}`);

  const list = $("task-list");
  list.replaceChildren();
  $("tasks-empty").hidden = data.items.length > 0;
  for (const task of data.items) list.append(renderTask(task));
}

function renderTask(task) {
  const item = el("li", { className: "item task" }, { testid: "task-row", taskId: task.id, status: task.status });
  const details = el("div", { className: "task-details" });
  details.append(
    el("span", { className: "item-title", textContent: task.title }, { testid: "task-title-text" }),
    el("span", { className: `badge priority-${task.priority}`, textContent: task.priority }, { testid: "task-priority-badge" }),
    el("span", { className: `badge status-${task.status}`, textContent: STATUS_LABELS[task.status] }, { testid: "task-status" }),
  );
  if (task.dueDate) details.append(el("span", { className: "muted small", textContent: `due ${task.dueDate}` }, { testid: "task-due" }));

  const actions = el("div", { className: "task-actions" });
  for (const [target, label] of TRANSITIONS[task.status]) {
    const button = el("button", { type: "button", textContent: label, className: "secondary" }, { testid: `task-action-${target}` });
    button.addEventListener("click", () => changeStatus(task.id, target));
    actions.append(button);
  }
  const remove = el("button", { type: "button", textContent: "Delete", className: "danger" }, { testid: "task-delete" });
  remove.addEventListener("click", () => deleteTask(task.id));
  actions.append(remove);

  item.append(details, actions);
  return item;
}

async function changeStatus(taskId, status) {
  hideError("task-error");
  try {
    await api("POST", `/api/tasks/${taskId}/status`, { status });
    await loadTasks();
  } catch (err) {
    showError("task-error", err.message);
  }
}

async function deleteTask(taskId) {
  hideError("task-error");
  try {
    await api("DELETE", `/api/tasks/${taskId}`);
    await loadTasks();
  } catch (err) {
    showError("task-error", err.message);
  }
}

$("task-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.target);
  hideError("task-error");
  try {
    await api("POST", `/api/projects/${state.projectId}/tasks`, {
      title: form.get("title"),
      priority: form.get("priority"),
      dueDate: form.get("dueDate") || null,
    });
    event.target.reset();
    await loadTasks();
  } catch (err) {
    showError("task-error", err.message);
  }
});

$("status-filter").addEventListener("change", () => loadTasks().catch((err) => showError("task-error", err.message)));

window.addEventListener("hashchange", route);
setAuthMode("login");
route();
