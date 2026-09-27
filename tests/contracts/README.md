# Test contracts and intentional independence

Production authority stays in `bundle/agent-governance/ssot/` and the template
registry. `contracts/governance-contract.json` owns the shared structural schema
introduced by #90. Neither is generated from tests.

The JSON files in this directory are manually reviewed test evidence. Production
code must never import them, and no generator synchronizes them with production.
Changing a selected semantic contract requires an explicit review of both sides.
Tests compare semantic values, not TOML formatting or prose.

| Domain | Shared positive expectation | Why it remains independent |
| --- | --- | --- |
| Routing | `routing.json`: exact tool IDs, policy tags and resource scopes | A structurally valid added/removed/renamed entry must not silently change the installed inventory. |
| Discovery | No additional positive oracle | Candidate classes, evidence families and field sets already belong to the #90 structural contract. Repeating them in another file would add no independent behavioral coverage. Existing boundedness, confidence, parser and conformance tests remain. |
| Templates | `templates.json`: exact IDs, paths, categories and formats | The loader must resolve the agreed forms. Categories and expected directories in tests derive from this one test reference. |
| Work items | `work-items.json`: exact dimension cardinalities and required stable IDs/label names | Cardinality is executable behavior. Required IDs/names intentionally describe a subset; other classification values and label descriptions/colors remain solely in their productive catalogs. |
| Commands (#88, unchanged) | `public-commands.json` | Ordered public command semantics retain their existing independent oracle. |

Python and TypeScript read the same positive oracle for each applicable domain.
`tests/installer/catalog-oracles.ts` only loads test data and supplies compile-time
types; it neither derives expectations nor implements validation. Python reads the
JSON directly. Missing or changed selected entries fail comparisons against real
loaders/validators. Routing's runtime result deliberately has no tool inventory;
its test inspects the input after the real routing validator has accepted it.

The following repetitions have a different purpose and are retained:

- Synthetic valid parser inputs provide a small starting point for negative tests;
  they do not claim to enumerate the installed catalog.
- Negative mutations and focused behavioral assertions independently specify
  rejection, reference closure, authorization boundaries, label projection and
  cardinality outcomes. Deriving their expected verdict from production would
  remove their ability to detect a bug.
- `conformance-mutations.json` remains the #90 cross-language rejection battery;
  it is not a second positive inventory.
- Minimal TypeScript union types describe compile-time API boundaries. Runtime
  validators still consume the existing structural contract. This change does not
  introduce another production registry or change public types.
- Generic schema shape and sanitization checks remain validator responsibilities;
  positive field-set checks reuse the shared structural contract.

All #91 changes live under `tests/`, which is excluded from the published npm
package. No runtime dependency, additional npm package, public contract change or
separate versioned release is needed. A reviewed and verified merge publishes this
test improvement. Package inventory verification must confirm that boundary.
