const state = {
  currentFile: null,
  providers: [{ id: "local", name: "Local Ollama", kind: "ollama", base_url: "http://localhost:11434" }],
  agents: [
    { id: crypto.randomUUID(), name: "Ada", role: "implementation engineer", model: "qwen3:8b", provider_id: "local", instructions: "Inspect the project before proposing changes.", capabilities: ["list_files", "read_file", "search_files", "write_file"], max_tool_rounds: 6 },
    { id: crypto.randomUUID(), name: "Linus", role: "skeptical code reviewer", model: "qwen3:8b", provider_id: "local", instructions: "Find defects, security risks, and missing tests.", capabilities: ["list_files", "read_file", "search_files"], max_tool_rounds: 6 },
    { id: crypto.randomUUID(), name: "Grace", role: "technical lead and synthesizer", model: "qwen3:8b", provider_id: "local", instructions: "Synthesize a precise, actionable final result.", capabilities: ["list_files", "read_file", "search_files"], max_tool_rounds: 6 },
  ]
};

const $ = (selector) => document.querySelector(selector);
const workspace = () => $("#workspace").value.trim() || ".";
const escapeHtml = (value) => String(value).replace(/[&<>'"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]));

async function api(url, options = {}) {
  const response = await fetch(url, { headers: { "Content-Type": "application/json" }, ...options });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `Request failed (${response.status})`);
  return body;
}

function setStatus(text, busy = false) {
  $("#statusText").textContent = text;
  $(".status-dot").style.background = busy ? "#d3a74d" : "#41d6aa";
}

async function loadFiles() {
  setStatus("Loading workspace", true);
  try {
    const data = await api(`/api/files?workspace=${encodeURIComponent(workspace())}`);
    $("#fileTree").innerHTML = data.files.map(path => `<button class="file" data-path="${escapeHtml(path)}" title="${escapeHtml(path)}">${escapeHtml(path)}</button>`).join("") || '<p class="muted">No text files found.</p>';
    document.querySelectorAll(".file").forEach(button => button.addEventListener("click", () => openFile(button.dataset.path)));
    setStatus(`${data.files.length} files`);
  } catch (error) { showError(error); }
}

async function openFile(path) {
  try {
    const data = await api(`/api/file?workspace=${encodeURIComponent(workspace())}&path=${encodeURIComponent(path)}`);
    state.currentFile = path;
    $("#fileName").textContent = path.split("/").pop();
    $("#editor").value = data.content;
    updateEditor();
    document.querySelectorAll(".file").forEach(el => el.classList.toggle("active", el.dataset.path === path));
  } catch (error) { showError(error); }
}

async function saveFile() {
  if (!state.currentFile) return;
  try {
    await api(`/api/file?workspace=${encodeURIComponent(workspace())}`, { method: "PUT", body: JSON.stringify({ path: state.currentFile, content: $("#editor").value }) });
    setStatus(`Saved ${state.currentFile}`);
  } catch (error) { showError(error); }
}

function updateEditor() {
  const editor = $("#editor");
  const lines = editor.value.split("\n").length;
  $("#lineNumbers").textContent = Array.from({length: lines}, (_, i) => i + 1).join("\n");
  const before = editor.value.slice(0, editor.selectionStart).split("\n");
  $("#cursor").textContent = `Ln ${before.length}, Col ${before.at(-1).length + 1}`;
  const extension = (state.currentFile || "welcome.md").split(".").pop();
  $("#language").textContent = ({py:"Python",js:"JavaScript",ts:"TypeScript",json:"JSON",md:"Markdown",html:"HTML",css:"CSS"})[extension] || "Plain Text";
}

function renderAgents() {
  $("#agentList").innerHTML = state.agents.map(agent => `<div class="agent-card" data-id="${agent.id}"><strong>${escapeHtml(agent.name)}</strong><p>${escapeHtml(agent.role)}</p><small>${escapeHtml(agent.model)} · ${escapeHtml(agent.provider_id)}</small></div>`).join("");
  document.querySelectorAll(".agent-card").forEach(card => card.addEventListener("click", () => editAgent(card.dataset.id)));
  const pattern = $("#pattern").value;
  $("#teamCanvas").innerHTML = state.agents.map((agent, index) => `${index ? `<span class="connector">${pattern === "panel" ? "+" : "→"}</span>` : ""}<div class="agent-node"><span class="agent-avatar">${escapeHtml(agent.name.slice(0, 1))}</span><span><strong>${escapeHtml(agent.name)}</strong><small>${escapeHtml(agent.role)}</small></span></div>`).join("");
}

function editAgent(id = null) {
  const agent = state.agents.find(item => item.id === id);
  $("#agentId").value = agent?.id || "";
  $("#agentName").value = agent?.name || "";
  $("#agentRole").value = agent?.role || "";
  $("#agentModel").value = agent?.model || "qwen3:8b";
  $("#agentInstructions").value = agent?.instructions || "";
  $("#agentProvider").innerHTML = state.providers.map(provider => `<option value="${provider.id}">${escapeHtml(provider.name)}</option>`).join("");
  $("#agentProvider").value = agent?.provider_id || "local";
  document.querySelectorAll('[name="capability"]').forEach(check => check.checked = (agent?.capabilities || ["list_files", "read_file", "search_files"]).includes(check.value));
  $("#agentDialog").showModal();
}

function saveAgent(event) {
  event.preventDefault();
  const id = $("#agentId").value || crypto.randomUUID();
  const config = { id, name: $("#agentName").value, role: $("#agentRole").value, provider_id: $("#agentProvider").value, model: $("#agentModel").value, instructions: $("#agentInstructions").value, capabilities: [...document.querySelectorAll('[name="capability"]:checked')].map(item => item.value), max_tool_rounds: 6 };
  const index = state.agents.findIndex(agent => agent.id === id);
  if (index >= 0) state.agents[index] = config; else state.agents.push(config);
  $("#agentDialog").close();
  renderAgents();
}

function renderProviders() {
  $("#providerList").innerHTML = state.providers.map((provider, index) => `<div class="provider" data-index="${index}"><input data-field="name" value="${escapeHtml(provider.name)}" aria-label="Provider name"><input data-field="base_url" value="${escapeHtml(provider.base_url)}" aria-label="Base URL"><select data-field="kind"><option value="ollama" ${provider.kind === "ollama" ? "selected" : ""}>Ollama</option><option value="openai-compatible" ${provider.kind === "openai-compatible" ? "selected" : ""}>OpenAI compatible</option></select><input data-field="api_key" type="password" value="${escapeHtml(provider.api_key || "")}" placeholder="API key (optional)" aria-label="API key"></div>`).join("");
}

function saveProviders(event) {
  event.preventDefault();
  document.querySelectorAll(".provider").forEach((row, index) => row.querySelectorAll("[data-field]").forEach(input => state.providers[index][input.dataset.field] = input.value));
  $("#providerDialog").close();
  renderAgents();
}

function appendMessage(who, text, type = "agent") {
  const initials = who.slice(0, 1).toUpperCase();
  $("#conversation").insertAdjacentHTML("beforeend", `<div class="message ${type}"><span class="avatar">${escapeHtml(initials)}</span><div><strong>${escapeHtml(who)}</strong><p>${escapeHtml(text)}</p></div></div>`);
  $("#conversation").scrollTop = $("#conversation").scrollHeight;
}

function showError(error) { setStatus("Error"); appendMessage("Error", error.message, "error"); }

async function runTeam(event) {
  event.preventDefault();
  const task = $("#task").value.trim();
  if (!task) return;
  appendMessage("You", task, "user");
  $("#runButton").disabled = true;
  setStatus("Agents working", true);
  const pattern = $("#pattern").value;
  const last = state.agents.at(-1)?.id;
  const body = { task, workspace: workspace(), allow_writes: $("#allowWrites").checked, providers: state.providers, team: { name: "Studio team", pattern, agents: state.agents, synthesizer_id: pattern === "panel" ? last : null, judge_id: pattern === "debate" ? last : null, router_id: pattern === "route" ? state.agents[0]?.id : null, debate_rounds: 2 } };
  try {
    const result = await api("/api/runs", { method: "POST", body: JSON.stringify(body) });
    appendMessage("Team", result.output);
    $("#eventList").innerHTML = result.events.map(item => `<div class="event ${escapeHtml(item.kind)}"><strong>${escapeHtml(item.agent)}</strong> · ${escapeHtml(item.kind)}</div>`).join("");
    setStatus("Run complete");
  } catch (error) { showError(error); }
  finally { $("#runButton").disabled = false; }
}

document.querySelectorAll(".activity-button").forEach(button => button.addEventListener("click", () => {
  document.querySelectorAll(".activity-button,.side-view").forEach(item => item.classList.remove("active"));
  button.classList.add("active");
  $(`#${button.dataset.view}View`).classList.add("active");
}));
$("#openWorkspace").addEventListener("click", loadFiles);
$("#refreshFiles").addEventListener("click", loadFiles);
$("#addAgent").addEventListener("click", () => editAgent());
$("#agentForm").addEventListener("submit", saveAgent);
$("#pattern").addEventListener("change", renderAgents);
$("#settingsButton").addEventListener("click", () => { renderProviders(); $("#providerDialog").showModal(); });
$("#addProvider").addEventListener("click", () => { state.providers.push({ id: `external-${state.providers.length}`, name: "External provider", kind: "openai-compatible", base_url: "https://api.openai.com/v1", api_key: "" }); renderProviders(); });
$("#providerForm").addEventListener("submit", saveProviders);
$("#taskForm").addEventListener("submit", runTeam);
$("#editor").addEventListener("input", updateEditor);
$("#editor").addEventListener("click", updateEditor);
$("#editor").addEventListener("keyup", updateEditor);
$("#editor").addEventListener("scroll", event => $("#lineNumbers").scrollTop = event.target.scrollTop);
document.addEventListener("keydown", event => {
  if ((event.ctrlKey || event.metaKey) && event.key === "s") { event.preventDefault(); saveFile(); }
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") runTeam(event);
});

renderAgents();
updateEditor();
loadFiles();

