# Work-Item-Klassifikation

> Nicht normative Referenz. Maßgeblich bleibt die deklarative SSOT-Domain `work_items` unter
> `bundle/agent-governance/ssot/work-items/`.

Der Paket-Subpfad `@tomtastisch/agent-governance/work-items` projiziert die statische
Work-Item-Klassifikation und ihre plattformbezogenen Projektionen als read-only TypeScript-API.
Der kanonische Classifier ist ausschließlich `work-items/classifications.toml`; GitHub-Labels
(`work-items/projections/github-labels.toml`) und Titelmarker sind deterministische Projektionen
derselben SSOT und niemals eine zweite fachliche Authority. Tool-/Effect-Tags (`policy_tags`)
bleiben eine getrennte Domain. Dieses Modul führt keine GitHub-Mutation aus; es liest nur und
erzeugt Pläne.

## Verwendung

```ts
import {
  loadWorkItemSsot,
  validateWorkItemClassification,
  buildLabelProjectionPlan,
} from "@tomtastisch/agent-governance/work-items";
import type { GitHubLabel } from "@tomtastisch/agent-governance/work-items";

const ssot = loadWorkItemSsot(); // /absolute/verified-package
const result = validateWorkItemClassification(ssot.classifications, ["type.refactor", "priority.high"]);

const inventory: GitHubLabel[] = [
  { name: "semver:patch", color: "0D9BF2", description: "" },
];
const plan = buildLabelProjectionPlan(ssot.projections, inventory);
```

`loadWorkItemSsot(releaseRoot?)` liest `classifications.toml` und `github-labels.toml` über den
SSOT-Index und validiert beide geschlossen. Eine unbekannte, ungültige oder unvollständige Datei
scheitert fail-closed; es findet keine Netzwerk- oder Remote-Abfrage statt.

## Öffentliche Funktionen

- `parseClassificationsText` / `parseProjectionsText`: geschlossene Text-Parser der beiden
  SSOT-Dateien.
- `loadWorkItemSsot`: lädt den vollständigen, validierten `WorkItemSsot` aus der SSOT-Domain.
- `resolveClassification`: löst eine stabile ID (`<dimension>.<value>`) in ihren Klassifikationswert.
- `validateWorkItemClassification`: prüft eine ID-Menge gegen Kardinalitäten und meldet Verstöße.
- `buildLabelProjectionPlan`: erzeugt einen `NOOP`/`CREATE`/`UPDATE`/`CONFLICT`/`UNMANAGED`-Plan
  gegen ein read-only GitHub-Label-Inventar.
- `deriveTitleMarkers`, `classifyLabels`, `classifyTitleMarkers`, `parseTitleMarkers`,
  `detectProjectionDrift`: lesen und projizieren die Titelmarker- und Label-Projektionen.

Kardinalitäten (`CARDINALITIES`), Dimensionen, Klassifikationswerte und Projektionsdrift folgen
ausschließlich der SSOT; diese Referenz wiederholt sie nicht. GitHub-Labels werden aus dem
`ProjectionPlan` heraus durch den Aufrufer angelegt oder gepflegt — dieses Modul mutiert niemals
selbst.
