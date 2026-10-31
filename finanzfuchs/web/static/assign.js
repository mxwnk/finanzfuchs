// The assigning page: one transaction at a time, plan lines as chips, keyboard first.
(() => {
  "use strict";
  const euro = new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" });
  const dateFormat = new Intl.DateTimeFormat("de-DE", { weekday: "short", day: "2-digit", month: "2-digit", year: "numeric" });
  const DOUBT_PREFIX = "ZWEIFEL";
  const $ = id => document.getElementById(id);

  let entries = [];
  let planLines = [];
  let total = 0;
  let index = 0;
  let busy = false;

  async function load() {
    const response = await fetch("/api/attention", { headers: { Accept: "application/json" } });
    if (response.status === 401) { location.href = "/auth/login"; return; }
    if (!response.ok) { $("headline").textContent = "Konnte die Buchungen nicht laden."; return; }
    const data = await response.json();
    entries = data.entries;
    planLines = data.planLines;
    total = Math.max(total, entries.length);
    index = Math.min(index, Math.max(entries.length - 1, 0));
    render();
  }

  function render() {
    renderProgress();
    renderQueue();
    const entry = entries[index];
    $("current").hidden = !entry;
    $("done").hidden = Boolean(entry);
    if (!entry) return;
    const isDoubt = !entry.isOpen;
    $("kind").textContent = isDoubt ? "Zweifel" : "Offen";
    $("kind").className = `kind ${isDoubt ? "doubt" : "open"}`;
    $("date").textContent = dateFormat.format(new Date(entry.date));
    $("amount").textContent = euro.format(entry.amount);
    $("amount").classList.toggle("in", entry.amount > 0);
    $("counterparty").textContent = entry.counterparty || "–";
    $("purpose").textContent = entry.purpose;
    $("guess").hidden = !isDoubt;
    if (isDoubt) {
      $("guess-line").textContent = describe(entry.line);
      $("guess-note").textContent = entry.note.replace(new RegExp(`^${DOUBT_PREFIX}:?\\s*`), "");
    }
    $("remember").checked = false;
    $("remember-label").textContent = entry.counterparty ? `Künftig alle von „${entry.counterparty}“ so zuordnen` : "Künftig immer so";
    $("search").value = "";
    renderLines();
  }

  function renderProgress() {
    const done = total - entries.length;
    $("headline").textContent = entries.length
      ? `${entries.length} ${entries.length === 1 ? "Buchung braucht" : "Buchungen brauchen"} euch`
      : "Fertig";
    $("bar").style.width = total ? `${(done / total) * 100}%` : "100%";
  }

  function renderQueue() {
    $("queue").innerHTML = "";
    entries.slice(0, 60).forEach((entry, position) => {
      const item = document.createElement("li");
      item.className = position === index ? "active" : "";
      item.append(span("who", entry.counterparty || "–"), span("how-much num", euro.format(entry.amount)),
        span("when", `${dateFormat.format(new Date(entry.date))}${entry.isOpen ? "" : " · Zweifel"}`));
      item.addEventListener("click", () => { index = position; render(); });
      $("queue").append(item);
    });
  }

  function renderLines() {
    const query = $("search").value.trim().toLowerCase();
    const entry = entries[index];
    const wanted = entry.amount > 0 ? "Einnahme" : "Ausgabe";
    const matching = planLines.filter(line => !query || `${line.description} ${line.category} ${line.id}`.toLowerCase().includes(query));
    // Lines of the fitting kind first: income for money that came in, spending otherwise.
    matching.sort((a, b) => (a.type === wanted ? 0 : 1) - (b.type === wanted ? 0 : 1));
    const byCategory = new Map();
    matching.forEach(line => {
      if (!byCategory.has(line.category)) byCategory.set(line.category, []);
      byCategory.get(line.category).push(line);
    });
    $("lines").innerHTML = "";
    let first = true;
    byCategory.forEach((lines, category) => {
      const group = document.createElement("div");
      const title = document.createElement("h3");
      title.textContent = category;
      const chips = document.createElement("div");
      chips.className = "chips";
      lines.forEach(line => {
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = `chip${query && first ? " highlight" : ""}`;
        chip.textContent = line.description;
        chip.dataset.line = line.id;
        chip.addEventListener("click", () => assign(line.id));
        chips.append(chip);
        first = false;
      });
      group.append(title, chips);
      $("lines").append(group);
    });
    if (!matching.length) $("lines").innerHTML = `<p class="muted">Keine Planzeile passt zu „${escapeText(query)}“.</p>`;
  }

  async function assign(lineId) {
    const entry = entries[index];
    const remember = $("remember").checked;
    const result = await post(`/api/transactions/${encodeURIComponent(entry.id)}/assign`, { plan_line_id: lineId, remember });
    if (!result) return;
    feedback(`→ ${describe(lineId)}${result.alsoAssigned ? ` · ${result.alsoAssigned} weitere gleich mit erledigt` : ""}`);
    await load();
  }

  async function confirmGuess() {
    const entry = entries[index];
    if (!entry || entry.isOpen) return;
    const result = await post(`/api/transactions/${encodeURIComponent(entry.id)}/confirm`, {});
    if (!result) return;
    feedback(`✓ ${describe(entry.line)} bestätigt`);
    await load();
  }

  async function post(url, body) {
    if (busy) return null;
    busy = true;
    try {
      const response = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      if (response.status === 401) { location.href = "/auth/login"; return null; }
      if (!response.ok) { feedback("Das hat nicht geklappt – bitte neu laden."); return null; }
      return await response.json();
    } finally {
      busy = false;
    }
  }

  function skip() {
    if (!entries.length) return;
    index = (index + 1) % entries.length;
    render();
  }

  function feedback(text) { $("feedback").textContent = text; }
  function describe(lineId) { return planLines.find(line => line.id === lineId)?.description ?? lineId; }
  function span(className, text) { const element = document.createElement("span"); element.className = className; element.textContent = text; return element; }
  function escapeText(text) { const element = document.createElement("span"); element.textContent = text; return element.innerHTML; }

  $("search").addEventListener("input", renderLines);
  $("search").addEventListener("keydown", event => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    const firstChip = $("lines").querySelector(".chip");
    if (firstChip && $("search").value.trim()) assign(firstChip.dataset.line);
  });
  $("confirm").addEventListener("click", confirmGuess);
  $("skip").addEventListener("click", skip);
  document.addEventListener("keydown", event => {
    const typing = event.target instanceof HTMLInputElement && event.target.type !== "checkbox";
    if (event.key === "/" && !typing) { event.preventDefault(); $("search").focus(); }
    if (typing) return;
    if (event.key === "Enter") { event.preventDefault(); confirmGuess(); }
    if (event.key.toLowerCase() === "s") skip();
  });

  load();
})();
