const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const vm = require("node:vm");

const script = readFileSync(path.join(__dirname, "../dashboard/dashboard.js"), "utf8");

function viewer() {
  const elements = { explorer: {}, snapshot: {} };
  const context = vm.createContext({
    fetch: async () => ({ ok: false }),
    document: { getElementById: (id) => elements[id] },
  });
  vm.runInContext(script, context);
  return { elements, context };
}

const activity = [
  { year: 2024, month: 2, matched: 3, unmatched: 2, unidentified: 5 },
  { year: 2024, month: 2, matched: 1, unmatched: 0, unidentified: 0 },
  { year: 2024, month: 4, matched: 1, unmatched: 2, unidentified: 4 },
  { year: 2025, month: 2, matched: 7, unmatched: 0, unidentified: 0 },
];
const dates = { min: "2024-02-28", max: "2025-02-28" };

test("annual and monthly counts retain all linkage groups and leave calendar gaps", () => {
  const { context } = viewer();
  const years = context.timeSeries(activity, 2024, 2025, "annual", dates);
  assert.equal(years[0].value, 18);
  assert.match(years[0].detail, /2 \/ 12.*boundary/);
  assert.equal(years[1].value, 7);
  const months = context.timeSeries(activity, 2024, 2024, "monthly", dates);
  assert.equal(months.length, 12);
  assert.equal(months[1].value, 11);
  assert.equal(months[2].value, null);
  assert.equal(months[3].value, 7);
});

test("seasonal mean omits partial boundaries and years with no observations", () => {
  const { context } = viewer();
  const months = context.timeSeries(activity, 2024, 2025, "seasonal", dates);
  assert.equal(months[0].value, null);
  assert.equal(months[1].value, 7);
  assert.match(months[1].detail, /1 \/ 2/);
  assert.equal(months[3].value, 7);
  const fullFebruary = { min: "2024-02-01", max: "2025-02-28" };
  assert.equal(context.timeSeries(activity, 2024, 2025, "seasonal", fullFebruary)[1].value, 9);
  assert.equal(context.partialMonth("2024-02", { min: "2024-01-01", max: "2024-02-28" }), true);
  assert.equal(context.partialMonth("2024-02", { min: "2024-01-01", max: "2024-02-29" }), false);
});

test("missing export leaves the viewer closed and identifies the expected file", async () => {
  const { elements } = viewer();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(elements.explorer.hidden, true);
  assert.match(elements.snapshot.textContent, /dashboard\.json/);
});
