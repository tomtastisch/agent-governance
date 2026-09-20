import assert from "node:assert/strict";
import test from "node:test";
import {
  buildLabelProjectionPlan,
  classifyLabels,
  classifyTitleMarkers,
  detectProjectionDrift,
  deriveTitleMarkers,
  loadWorkItemSsot,
  parseClassificationsText,
  parseProjectionsText,
  resolveClassification,
  validateWorkItemClassification,
  type GitHubLabel,
} from "../../src/work-items.ts";

const MINIMAL_CLASSIFICATIONS = `schema_version = 1

[dimensions.type]
label = "Type"
cardinality = "one"
description = "Art des Work Items."

[dimensions.semver]
label = "SemVer Impact"
cardinality = "at_most_one"
description = "Erwartete Versionsauswirkung."

[classifications.type.feature]
label = "Feature"
description = "Neue Funktionalität."

[classifications.type.fix]
label = "Fix"
description = "Fehlerkorrektur."

[classifications.semver.patch]
label = "Patch"
description = "Rückwärtskompatible Korrektur."
`;

test("the canonical classification SSOT resolves every stable ID deterministically", () => {
  const { classifications, projections } = loadWorkItemSsot();
  assert.equal(classifications.schemaVersion, 1);
  const dimensions = Object.keys(classifications.dimensions).sort();
  assert.deepEqual(dimensions, ["area", "horizon", "semver", "type"]);
  for (const id of Object.keys(classifications.classifications)) {
    assert.match(id, /^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$/);
    const resolved = resolveClassification(classifications, id);
    assert.equal(resolved.id, id);
  }
  for (const projection of Object.values(projections.projections)) {
    const resolved = resolveClassification(classifications, projection.classification);
    assert.equal(resolved.id, projection.classification);
  }
});

test("dimensions declare explicit cardinality", () => {
  const { classifications } = loadWorkItemSsot();
  assert.equal(classifications.dimensions.type!.cardinality, "one");
  assert.equal(classifications.dimensions.area!.cardinality, "many");
  assert.equal(classifications.dimensions.horizon!.cardinality, "at_most_one");
  assert.equal(classifications.dimensions.semver!.cardinality, "at_most_one");
});

test("policy_tags remain a separate domain from work-item classification", () => {
  const { classifications } = loadWorkItemSsot();
  const ids = new Set(Object.keys(classifications.classifications));
  for (const policyTag of ["read", "write"]) {
    assert.ok(!ids.has(policyTag), `policy tag ${policyTag} must not be a classification`);
  }
  const dimensions = Object.keys(classifications.dimensions);
  assert.ok(!dimensions.includes("policy_tag"), "no policy_tag dimension");
});

test("the classification SSOT carries no dynamic lifecycle state", () => {
  const { classifications } = loadWorkItemSsot();
  const ids = Object.keys(classifications.classifications);
  for (const lifecycle of ["in_progress", "blocked", "completed", "ready", "draft", "superseded", "work_started"]) {
    assert.ok(!ids.some((id) => id.includes(lifecycle)), `no lifecycle state ${lifecycle}`);
  }
});

test("duplicate semantic ID fails closed", () => {
  const duplicate = `${MINIMAL_CLASSIFICATIONS}\n[classifications.type.feature]\nlabel = "Feature"\ndescription = "dup"\n`;
  assert.throws(() => parseClassificationsText(duplicate), /duplicate/i);
});

test("unknown dimension fails closed", () => {
  const unknown = `${MINIMAL_CLASSIFICATIONS}\n[classifications.missing.value]\nlabel = "X"\ndescription = "Y"\n`;
  assert.throws(() => parseClassificationsText(unknown), /unknown dimension/i);
});

test("a dimension without classification values fails closed", () => {
  const missing = `schema_version = 1

[dimensions.type]
label = "Type"
cardinality = "one"
description = "Art."

[dimensions.semver]
label = "SemVer"
cardinality = "at_most_one"
description = "Auswirkung."

[classifications.type.feature]
label = "Feature"
description = "Neu."
`;
  assert.throws(() => parseClassificationsText(missing), /no classification values/i);
});

test("invalid (unregistered) value fails closed", () => {
  const index = parseClassificationsText(MINIMAL_CLASSIFICATIONS);
  assert.throws(() => resolveClassification(index, "type.unknown"), /unknown classification ID/i);
});

test("cardinality violation in a single-value dimension is reported as invalid", () => {
  const index = parseClassificationsText(MINIMAL_CLASSIFICATIONS);
  const result = validateWorkItemClassification(index, ["type.feature", "type.fix"]);
  assert.ok(result.violations.some((v) => v.dimension === "type" && v.cardinality === "one"));
});

test("cardinality accepts multiple values in a many dimension", () => {
  const { classifications } = loadWorkItemSsot();
  const result = validateWorkItemClassification(classifications, ["area.cli", "area.github", "type.feature"]);
  assert.deepEqual(result.violations, []);
});

test("projection collision on the same label name fails closed", () => {
  const index = parseClassificationsText(MINIMAL_CLASSIFICATIONS);
  const collision = `schema_version = 1

[projections.a]
classification = "type.feature"
name = "dup"
description = "a"
color = "000000"
aliases = []

[projections.b]
classification = "type.fix"
name = "dup"
description = "b"
color = "111111"
aliases = []

[title_markers.t]
classification = "type.feature"
marker = "[T]"
`;
  assert.throws(() => parseProjectionsText(collision, index), /collision/i);
});

test("duplicate projection for one classification fails closed", () => {
  const index = parseClassificationsText(MINIMAL_CLASSIFICATIONS);
  const duplicate = `schema_version = 1

[projections.a]
classification = "type.feature"
name = "one"
description = "a"
color = "000000"
aliases = []

[projections.b]
classification = "type.feature"
name = "two"
description = "b"
color = "111111"
aliases = []

[title_markers.t]
classification = "type.feature"
marker = "[T]"
`;
  assert.throws(() => parseProjectionsText(duplicate, index), /duplicate projection/i);
});

test("unknown projection classification fails closed", () => {
  const index = parseClassificationsText(MINIMAL_CLASSIFICATIONS);
  const unknown = `schema_version = 1

[projections.a]
classification = "type.missing"
name = "x"
description = "a"
color = "000000"
aliases = []

[title_markers.t]
classification = "type.feature"
marker = "[T]"
`;
  assert.throws(() => parseProjectionsText(unknown, index), /unknown projection classification/i);
});

test("invalid projection color fails closed", () => {
  const index = parseClassificationsText(MINIMAL_CLASSIFICATIONS);
  const badColor = `schema_version = 1

[projections.semver_patch]
classification = "semver.patch"
name = "semver:patch"
description = "Patch"
color = "zzz"
aliases = []

[title_markers.t]
classification = "type.feature"
marker = "[T]"
`;
  assert.throws(() => parseProjectionsText(badColor, index), /color is invalid/i);
});

const inventory = (labels: GitHubLabel[]): GitHubLabel[] => labels;

test("managed label matching a projection yields NOOP", () => {
  const { projections } = loadWorkItemSsot();
  const plan = buildLabelProjectionPlan(projections, inventory([
    { name: "semver:patch", color: "0E8A16", description: "Erfordert voraussichtlich eine rückwärtskompatible Korrektur oder Dokumentationsänderung" },
  ]));
  assert.equal(plan.entries.length, 18);
  assert.deepEqual(plan.entries.find((e) => e.labelName === "semver:patch"), {
    action: "NOOP",
    classification: "semver.patch",
    labelName: "semver:patch",
    reason: "managed label matches the projection",
  });
});

test("managed label drift yields UPDATE without mutation", () => {
  const { projections } = loadWorkItemSsot();
  const plan = buildLabelProjectionPlan(projections, inventory([
    { name: "semver:patch", color: "000000", description: "changed" },
  ]));
  assert.equal(plan.entries.find((e) => e.labelName === "semver:patch")?.action, "UPDATE");
});

test("missing managed label yields CREATE without mutation", () => {
  const { projections } = loadWorkItemSsot();
  const plan = buildLabelProjectionPlan(projections, inventory([]));
  assert.equal(plan.entries.filter((e) => e.action === "CREATE").length, 18);
});

test("external label yields UNMANAGED", () => {
  const { projections } = loadWorkItemSsot();
  const plan = buildLabelProjectionPlan(projections, inventory([
    { name: "triage", color: "ffffff", description: "external" },
  ]));
  assert.equal(plan.entries.find((e) => e.labelName === "triage")?.action, "UNMANAGED");
});

test("ownership collision yields CONFLICT and never overwrites", () => {
  const { projections } = loadWorkItemSsot();
  const plan = buildLabelProjectionPlan(projections, inventory([
    { name: "semver:patch", color: "000000", description: "foreign", managed: false },
  ]));
  assert.equal(plan.entries.find((e) => e.labelName === "semver:patch")?.action, "CONFLICT");
});

test("legacy label matching an alias yields CANDIDATE", () => {
  const { projections } = loadWorkItemSsot();
  const plan = buildLabelProjectionPlan(projections, inventory([
    { name: "github-hardening", color: "1E5AA8", description: "GitHub repository protection, rulesets, policies, and automated hardening" },
  ]));
  const entry = plan.entries.find((e) => e.labelName === "github-hardening");
  assert.equal(entry?.action, "CANDIDATE");
  assert.equal(entry?.classification, "area.github");
});

test("the projection plan is deterministic and read-only", () => {
  const { projections } = loadWorkItemSsot();
  const labels = inventory([
    { name: "semver:patch", color: "0E8A16", description: "Erfordert voraussichtlich eine rückwärtskompatible Korrektur oder Dokumentationsänderung" },
    { name: "future", color: "808080", description: "Planned future capability outside the current release scope" },
    { name: "bug", color: "d73a4a", description: "Something isn't working" },
  ]);
  const first = buildLabelProjectionPlan(projections, labels);
  const second = buildLabelProjectionPlan(projections, labels);
  assert.deepEqual(first, second);
});

test("title markers derive deterministically from the classification SSOT", () => {
  const { projections } = loadWorkItemSsot();
  assert.deepEqual(deriveTitleMarkers(projections, ["horizon.future", "area.cli"]), ["[FUTURE]"]);
  assert.deepEqual(deriveTitleMarkers(projections, ["area.cli"]), []);
  assert.deepEqual(classifyTitleMarkers(projections, "[FUTURE][CLI] Work-Item"), ["horizon.future"]);
});

test("title markers are a projection, never a second authority", () => {
  const { classifications, projections } = loadWorkItemSsot();
  const fromTitle = classifyTitleMarkers(projections, "[FUTURE] x");
  const fromLabels = classifyLabels(projections, [{ name: "future", color: "808080", description: "Planned future capability outside the current release scope" }]);
  assert.deepEqual(fromTitle, ["horizon.future"]);
  assert.deepEqual(fromLabels, ["horizon.future"]);
  assert.deepEqual(detectProjectionDrift(classifications, fromTitle, fromLabels), []);
});

test("projection drift between title and label sources is reported deterministically", () => {
  const { classifications } = loadWorkItemSsot();
  const drift = detectProjectionDrift(classifications, ["horizon.future"], ["horizon.current"]);
  assert.deepEqual(drift, [{ dimension: "horizon", values: ["horizon.future", "horizon.current"] }]);
  const consistent = detectProjectionDrift(classifications, ["horizon.future"], ["horizon.future"]);
  assert.deepEqual(consistent, []);
});

test("the real GitHub label inventory classifies without any GitHub mutation", () => {
  const { projections } = loadWorkItemSsot();
  const realLabels: GitHubLabel[] = [
    { name: "bug", color: "d73a4a", description: "Something isn't working" },
    { name: "documentation", color: "0075ca", description: "Improvements or additions to documentation" },
    { name: "duplicate", color: "cfd3d7", description: "This issue or pull request already exists" },
    { name: "enhancement", color: "a2eeef", description: "New feature or request" },
    { name: "good first issue", color: "7057ff", description: "Good for newcomers" },
    { name: "help wanted", color: "008672", description: "Extra attention is needed" },
    { name: "invalid", color: "e4e669", description: "This doesn't seem right" },
    { name: "question", color: "d876e3", description: "Further information is requested" },
    { name: "wontfix", color: "ffffff", description: "This will not be worked on" },
    { name: "future", color: "808080", description: "Planned future capability outside the current release scope" },
    { name: "github-hardening", color: "1E5AA8", description: "GitHub repository protection, rulesets, policies, and automated hardening" },
    { name: "enforcement", color: "E10600", description: "Programmatic fail-closed enforcement of critical governance rules" },
    { name: "terminal-ux", color: "62CBCC", description: "Terminal visualization, interaction, and Agent Governance identity" },
    { name: "semver:major", color: "B60205", description: "Erfordert voraussichtlich eine nicht rückwärtskompatible Major-Version" },
    { name: "semver:minor", color: "1D76DB", description: "Erfordert voraussichtlich eine neue rückwärtskompatible Funktionalität" },
    { name: "semver:none", color: "6E7781", description: "Erfordert voraussichtlich keine neue Paketversion" },
    { name: "semver:patch", color: "0E8A16", description: "Erfordert voraussichtlich eine rückwärtskompatible Korrektur oder Dokumentationsänderung" },
    { name: "semver:pending", color: "D4C5F9", description: "SemVer-Auswirkung ist noch nicht ausreichend geklärt" },
    { name: "cli", color: "5319E7", description: "LLM-unabhängige CLI, öffentliche Commands und Command-SSOT" },
    { name: "in-progress", color: "FFFF00", description: "Lokale Umsetzung dieses Issues wurde begonnen und ist aktuell in Bearbeitung" },
    { name: "superseded", color: "6E7781", description: "Replaced by newer issue(s); retained for historical context" },
  ];
  const plan = buildLabelProjectionPlan(projections, realLabels);
  const counts = (action: string) => plan.entries.filter((e) => e.action === action).length;
  assert.equal(counts("NOOP"), 8);
  assert.equal(counts("CREATE"), 10);
  assert.equal(counts("CANDIDATE"), 2);
  assert.equal(counts("UNMANAGED"), 11);
  assert.equal(counts("CONFLICT"), 0);
  assert.equal(counts("UPDATE"), 0);
  for (const entry of plan.entries.filter((e) => e.action === "UNMANAGED")) {
    assert.ok(["bug", "documentation", "duplicate", "enhancement", "good first issue", "help wanted", "invalid", "question", "wontfix", "in-progress", "superseded"].includes(entry.labelName));
  }
});
