"use strict";

const byId = (id) => document.getElementById(id);
const number = new Intl.NumberFormat("en-US", {maximumFractionDigits: 1});
const compact = new Intl.NumberFormat("en-US", {notation: "compact", maximumFractionDigits: 1});
const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const operationNames = new Map([["A", "A · Interstate"], ["B", "B · Intrastate, hazardous materials"],
  ["C", "C · Intrastate, non-hazardous"]]);
const fleetOrder = ["0", "1", "2-5", "6-20", "21-100", "101+", "Missing"];
let dataset;
let view = "trends";
let chartRows = [];
let chartStyle;

function choices(id, pairs, selected) {
  const field = byId(id);
  field.replaceChildren(...pairs.map(([value, label]) => new Option(label, value)));
  field.value = selected;
}

function recordCount(row) {
  return row.matched + row.unmatched + row.unidentified;
}

function monthKey(year, month) {
  return year + "-" + String(month).padStart(2, "0");
}

// A boundary inside a month makes the whole-month comparison ambiguous.
function partialMonth(key, dates) {
  if (dates.min?.slice(0, 7) === key && Number(dates.min.slice(8, 10)) > 1) return true;
  if (dates.max?.slice(0, 7) !== key) return false;
  const [year, month, day] = dates.max.slice(0, 10).split("-").map(Number);
  return day < new Date(Date.UTC(year, month, 0)).getUTCDate();
}

function timeSeries(activity, first, last, grouping, dates) {
  const monthly = new Map();
  for (const row of activity) {
    const key = monthKey(row.year, row.month);
    monthly.set(key, (monthly.get(key) ?? 0) + recordCount(row));
  }
  const groups = new Map();
  for (let year = first; year <= last; year++) {
    for (let month = 1; month <= 12; month++) {
      const key = monthKey(year, month);
      const label = grouping === "annual" ? String(year) : grouping === "seasonal" ? monthNames[month - 1] : key;
      if (!groups.has(label)) groups.set(label, {label, sum: 0, months: 0, planned: 0, partial: false});
      const group = groups.get(label);
      group.planned++;
      if (!monthly.has(key)) continue;
      const partial = partialMonth(key, dates);
      if (grouping === "seasonal" && partial) continue;
      group.partial ||= partial;
      group.sum += monthly.get(key);
      group.months++;
    }
  }
  return Array.from(groups.values(), (g) => ({
    label: g.label,
    value: g.months === 0 ? null : grouping === "seasonal" ? g.sum / g.months : g.sum,
    partial: g.partial || (grouping === "annual" && g.months < g.planned),
    detail: g.months + " / " + g.planned + (g.partial ? " · boundary month" : "")
  }));
}

function svgElement(tag, attributes, text) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [name, value] of Object.entries(attributes)) node.setAttribute(name, value);
  if (text !== undefined) node.textContent = text;
  return node;
}

function drawChart() {
  const box = byId("chart");
  box.replaceChildren();
  const values = chartRows.filter(r => r.value !== null);
  if (!values.length) {
    box.textContent = "No observations for these filters.";
    return;
  }
  const max = Math.max(1, ...values.map(r => r.value));
  if (chartStyle === "bars") {
    const bars = document.createElement("div");
    bars.className = "bars";
    for (const r of chartRows.slice(0, 12)) {
      const row = document.createElement("div");
      row.className = "bar-row";
      const label = document.createElement("span");
      label.textContent = r.label;
      const bar = document.createElement("i");
      bar.style.width = (100 * r.value / max) + "%";
      const value = document.createElement("span");
      value.textContent = number.format(r.value);
      row.append(label, bar, value);
      bars.append(row);
    }
    box.append(bars);
    return;
  }
  const width = Math.max(200, box.clientWidth);
  const height = width < 560 ? 215 : 235;
  const left = 49, right = width - 26, top = 12, bottom = height - 28;
  const x = (i) => chartRows.length === 1 ? (left + right) / 2 : left + i * (right - left) / (chartRows.length - 1);
  const y = (v) => bottom - (bottom - top) * v / max;
  const svg = svgElement("svg", {class: "plot", viewBox: "0 0 " + width + " " + height, "aria-hidden": "true"});
  for (const fraction of [0, .5, 1]) {
    svg.append(svgElement("line", {x1: left, x2: right, y1: y(max * fraction), y2: y(max * fraction)}),
      svgElement("text", {x: left - 6, y: y(max * fraction) + 4, "text-anchor": "end"}, compact.format(max * fraction)));
  }
  const tickCount = Math.min(chartRows.length, Math.max(2, Math.floor((right - left) / 75)));
  const ticks = new Set(Array.from({length: tickCount}, (_, i) => Math.round(i * (chartRows.length - 1) / Math.max(1, tickCount - 1))));
  let path = "", penDown = false;
  chartRows.forEach((row, index) => {
    if (ticks.has(index)) svg.append(svgElement("text", {x: x(index), y: height - 6, "text-anchor": "middle"}, row.label));
    if (row.value === null) {
      penDown = false;
      return;
    }
    path += (penDown ? "L" : "M") + x(index) + " " + y(row.value) + " ";
    penDown = true;
    const dot = svgElement("circle", {cx: x(index), cy: y(row.value), r: chartRows.length > 40 ? 2 : 4,
      class: row.partial ? "partial" : ""});
    dot.append(svgElement("title", {}, row.label + " · " + number.format(row.value)));
    svg.append(dot);
  });
  const line = svgElement("path", {d: path, "pointer-events": "none"});
  svg.insertBefore(line, svg.querySelector("circle"));
  box.append(svg);
}

function renderTable(headings) {
  const table = byId("rows");
  table.replaceChildren();
  const header = table.createTHead().insertRow();
  for (const label of headings) {
    const th = document.createElement("th");
    th.scope = "col";
    th.textContent = label;
    header.append(th);
  }
  const body = table.createTBody();
  for (const row of chartRows) {
    const tr = body.insertRow();
    for (const value of [row.label, row.value === null ? "Unobserved" : number.format(row.value), row.detail]) {
      tr.insertCell().textContent = value;
    }
  }
}

function render() {
  const source = byId("source").value;
  const first = Number(byId("first").value), last = Number(byId("last").value);
  const dates = dataset.snapshot.coverage[source];
  const sourceLabel = source === "crash" ? "Crash" : "Inspection";
  const geography = source === "crash" ? "Reported crash location" : "Inspection reporting jurisdiction";
  const national = dataset.activity.filter(r => r.source === source && r.year >= first && r.year <= last);
  const state = view === "trends" ? byId("state").value : "";
  const activity = state ? national.filter(r => r.state === state) : national;
  const months = new Set(activity.map(r => monthKey(r.year, r.month)));
  const nMonths = (last - first + 1) * 12;
  const unmatched = activity.reduce((sum, r) => sum + r.unmatched, 0);
  const unidentified = activity.reduce((sum, r) => sum + r.unidentified, 0);
  const matched = activity.reduce((sum, r) => sum + r.matched, 0);
  const all = matched + unmatched + unidentified;
  const carrier = view === "carriers";
  byId("region").hidden = view !== "trends";
  byId("trendControl").hidden = view !== "trends";
  byId("carrierControl").hidden = !carrier;
  byId("categoryControl").hidden = !carrier;
  byId("monthsLabel").textContent = carrier ? "National months with records" : "Months with records";
  byId("regionLabel").textContent = geography;
  byId("metricLabel").textContent = (carrier ? "Matched " + source : sourceLabel) + " records";
  byId("recordCount").textContent = months.size ? number.format(carrier ? matched : all) : "Unobserved";
  byId("monthsSeen").textContent = months.size + " / " + nMonths;
  byId("qualityLabel").textContent = carrier ? "Excluded nationally" : "Census-matched share";
  byId("qualityValue").textContent = carrier ? (months.size ? number.format(unmatched + unidentified) : "—") :
    (all ? number.format(100 * matched / all) + "%" : "—");
  let title, note, headings;
  chartStyle = "line";
  if (view === "trends") {
    const grouping = byId("grouping").value;
    chartRows = timeSeries(activity, first, last, grouping, dates);
    title = {annual: "Annual record counts", monthly: "Monthly record counts", seasonal: "Average records by calendar month"}[grouping];
    note = grouping === "seasonal" ? "Each point averages monthly counts across years with records. Months cut short by the source date bounds are omitted." :
      "Counts include all three Census-linkage groups. A break in the line marks an unobserved period.";
    if (chartRows.some(r => r.partial && r.value !== null)) note += " An open circle marks a partial period.";
    headings = ["Period", grouping === "seasonal" ? "Mean records" : "Records", "Months included / selected"];
  } else if (view === "geography") {
    const states = new Map();
    for (const r of activity) {
      if (!states.has(r.state)) states.set(r.state, {value: 0, months: new Set()});
      const group = states.get(r.state);
      group.value += recordCount(r);
      group.months.add(monthKey(r.year, r.month));
    }
    chartRows = Array.from(states, ([label, g]) => ({label, value: g.value, detail: g.months.size + " / " + nMonths}))
      .sort((a, b) => b.value - a.value || a.label.localeCompare(b.label));
    chartStyle = "bars";
    title = "Records by jurisdiction";
    note = geography + ". " + (chartRows.length > 12 ? "The chart shows the 12 largest counts. The table includes every recorded jurisdiction." : "The table includes each observed jurisdiction.");
    headings = ["Jurisdiction", "Records", "Months observed / selected"];
  } else {
    const dimension = byId("dimension").value;
    const years = new Set(activity.map(r => r.year));
    const categories = new Map();
    for (const r of dataset.carriers) {
      if (r.dimension !== dimension || !years.has(r.year) || r[source + "_records"] === null) continue;
      if (!categories.has(r.category)) categories.set(r.category, {value: 0, years: 0});
      const group = categories.get(r.category);
      group.value += r[source + "_records"];
      group.years += r.carrier_years;
    }
    const sorted = Array.from(categories).sort(([a], [b]) => dimension === "fleet" ?
      fleetOrder.indexOf(a) - fleetOrder.indexOf(b) : a.localeCompare(b));
    const categoryLabel = code => dimension === "operation" ? operationNames.get(code) ?? code : code;
    const selected = byId("category").value;
    const filter = categories.has(selected) ? selected : "";
    choices("category", [["", "All groups"], ...sorted.map(([code]) => [code, categoryLabel(code)])], filter);
    chartRows = sorted.filter(([code]) => !filter || code === filter).map(([code, g]) => ({
      label: categoryLabel(code), value: g.value, detail: number.format(g.years)
    }));
    if (filter) {
      byId("metricLabel").textContent = "Matched records in group";
      byId("recordCount").textContent = number.format(categories.get(filter).value);
    }
    chartStyle = "bars";
    title = dimension === "fleet" ? "Matched records by fleet size" : "Matched records by carrier operation";
    note = "National counts grouped by current Census attributes. A carrier can appear in several years. " +
      (months.size ? "Excluded records include " + number.format(unmatched) + " unmatched and " + number.format(unidentified) + " unidentified." : "");
    headings = [dimension === "fleet" ? "Power units" : "Operation code", sourceLabel + " records", "Matched carrier-years with either event type"];
  }
  byId("figureTitle").textContent = title;
  byId("figureNote").textContent = note;
  byId("dates").textContent = ["crash", "inspection"].map(s => {
    const range = dataset.snapshot.coverage[s];
    return (s === "crash" ? "Crash" : "Inspection") + " record dates: " + (range.min && range.max ? range.min + " to " + range.max : "unobserved") + ".";
  }).join(" ");
  byId("coverage").textContent = dates.min && dates.max ?
    sourceLabel + " records in this extract span " + dates.min + " to " + dates.max + ". Months without records have unknown activity. Compare partial years with care." :
    "This extract contains no observed dates for this source.";
  drawChart();
  renderTable(headings);
}

function setStates() {
  const states = [...new Set(dataset.activity.filter(r => r.source === byId("source").value).map(r => r.state))].sort();
  choices("state", [["", "All jurisdictions"], ...states.map(s => [s, s])], "");
}

function compatible(data) {
  const period = data?.snapshot?.period;
  const sources = ["crash", "inspection"];
  const count = n => Number.isSafeInteger(n) && n >= 0;
  const year = n => Number.isInteger(n) && n >= period[0] && n <= period[1];
  const date = v => v === null || (typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v));
  return data?.version === 1 && typeof data.snapshot?.id === "string" && Array.isArray(period) &&
    period.length === 2 && period.every(y => Number.isInteger(y) && y > 0 && y <= 9999) &&
    period[1] >= period[0] && sources.every(s => {
      const bounds = data.snapshot.coverage?.[s];
      return bounds && date(bounds.min) && date(bounds.max);
    }) &&
    Array.isArray(data.activity) && data.activity.every(r => r && year(r.year) && sources.includes(r.source) &&
      typeof r.state === "string" && Number.isInteger(r.month) && r.month >= 1 && r.month <= 12 &&
      [r.matched, r.unmatched, r.unidentified].every(count)) &&
    Array.isArray(data.carriers) && data.carriers.every(r => r && year(r.year) && ["fleet", "operation"].includes(r.dimension) &&
      typeof r.category === "string" && count(r.carrier_years) &&
      [r.crash_records, r.inspection_records].every(n => n === null || count(n)));
}

async function start() {
  try {
    const response = await fetch("data/dashboard.json");
    if (!response.ok) throw new Error("missing snapshot");
    dataset = await response.json();
    if (!compatible(dataset)) throw new Error("incompatible snapshot");
    const [first, last] = dataset.snapshot.period;
    const years = Array.from({length: last - first + 1}, (_, i) => [first + i, first + i]);
    choices("first", years, first);
    choices("last", years, last);
    setStates();
    byId("snapshot").textContent = "FMCSA · " + first + "–" + last + " · Snapshot " + (dataset.snapshot.run_date ?? dataset.snapshot.id.slice(0, 12));
    byId("fingerprint").textContent = dataset.snapshot.id;
    byId("explorer").hidden = false;
    render();
    document.querySelectorAll("[data-view]").forEach(button => button.addEventListener("click", () => {
      view = button.dataset.view;
      document.querySelectorAll("[data-view]").forEach(item => item.setAttribute("aria-pressed", String(item === button)));
      render();
    }));
    byId("controls").addEventListener("change", e => {
      if (e.target.id === "source") setStates();
      if (Number(byId("first").value) > Number(byId("last").value)) {
        byId(e.target.id === "first" ? "last" : "first").value = e.target.value;
      }
      render();
    });
    window.addEventListener("resize", drawChart);
  } catch {
    byId("explorer").hidden = true;
    byId("snapshot").textContent = "The dashboard export could not be loaded. Generate data/dashboard.json and open this directory through a local HTTP server.";
  }
}
start();
