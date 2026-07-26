# Review Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, read-only CLI that classifies whether Copilot Code Review is
usable and selects Copilot, QA and SEC from review purpose and risk without using remaining budget
as a routing input.

**Architecture:** A stdlib-only Python package contains immutable domain contracts, pure policy and
risk functions, and an exact-head evidence validator. GitHub API/CLI and GitHub Status access live
behind injected ports in one adapter; TOML files under `core/` are the only machine-readable policy
sources. The CLI is the composition root and never dispatches a paid review.

**Tech Stack:** Python 3.11+, stdlib `dataclasses`, `enum`, `json`, `subprocess`, `tomllib`,
`urllib`, `unittest`; GitHub CLI `gh`; TOML policy; Markdown governance documentation.

## Global Constraints

- No third-party Python dependency.
- `probe` and `route` are read-only; no reviewer dispatch, comment, issue, push or merge.
- Remaining budget is diagnostic only and never changes a route.
- `quota_exhausted` requires explicit provider, API or operator evidence.
- `permission_denied`, `rate_limited`, `provider_unavailable` and `unknown` map fail-closed to
  `copilot_usable = false`.
- All external GitHub and status responses are mocked in automated tests.
- Every final/correction review is bound to explicit base and head SHAs.
- No token, authorization header, cookie, token fragment or token length is serialized or logged.
- The user performs the merge; the PR remains Draft until the later live positive test and final
  exact-head gates.

---

## File map

- `core/review-routing.toml`: route matrix, risk thresholds and path markers (SSOT).
- `review_routing/contracts.py`: the single module for every port, domain/config/evidence/error type.
- `review_routing/registry.py`: runtime factory registration and dependency resolution.
- `review_routing/risk.py`: pure diff risk classifier.
- `review_routing/policy.py`: pure usability classifier and reviewer route selector.
- `review_routing/evidence.py`: pure Copilot/QA/SEC exact-head evidence validation.
- `review_routing/adapters/toml_config.py`: strict TOML configuration port implementation.
- `review_routing/adapters/github_gh.py`: documented GitHub endpoints and error classification.
- `review_routing/__main__.py`: argument parsing, composition root, JSON and exitcodes.
- `tests/test_review_routing_*.py`: behavior specifications.
- `tests/fixtures/review-routing/*.json`: synthetic GitHub/status responses.
- `docs/decisions/0003-review-routing.md`: accepted architecture decision.

### Task 1: Policy SSOT and ADR

**Files:**
- Create: `core/review-routing.toml`
- Create: `docs/decisions/0003-review-routing.md`
- Create: `review_routing/__init__.py`
- Create: `review_routing/contracts.py`
- Create: `review_routing/registry.py`
- Create: `review_routing/adapters/__init__.py`
- Create: `review_routing/adapters/toml_config.py`
- Create: `tests/test_review_routing_config.py`
- Create: `tests/test_review_routing_architecture.py`
- Modify: `tests/test_governance.py`

**Interfaces:**
- Produces `ConfigPort.load_routing(path: Path) -> RoutingConfig`.
- Produces `RuntimeRegistry.register(factory: AdapterFactory) -> None` and
  `RuntimeRegistry.resolve(port: type[T]) -> T`.
- Produces: TOML tables `risk.thresholds`, `risk.path_markers`,
  `routing.<purpose>.<usable>`, `gate.required_checks` and `gate.publisher`.

- [ ] **Step 1: Write failing TOML/drift tests**

Test that:

```python
raw = tomllib.loads(Path("core/review-routing.toml").read_text())
self.assertEqual(raw["schema_version"], 1)
self.assertEqual(
    set(raw["routing"]),
    {"checkpoint", "final_exact_head"},
)
self.assertEqual(
    set(raw["routing"]["final_exact_head"]["usable"]),
    {"low", "medium", "high", "critical"},
)
self.assertNotIn("remaining", json.dumps(raw).lower())
```

Assert that `gate.required_checks` is non-empty and every entry contains only `name` and
`source_app_slug`. Assert that `gate.publisher.expected_app_slug` is non-empty. Also assert that
every `risk.path_markers` entry contains only `glob`, `level` and `security_relevant`.

Also require `core/core.md`, both adapters, QA role/template, README and the ADR to reference the
same `core/review-routing.toml`, without copying the complete route matrix.

- [ ] **Step 2: Run the focused tests and confirm RED**

Run:

```bash
python3 -m unittest tests.test_review_routing_config -v
```

Expected: failure because the TOML and parser do not exist.

- [ ] **Step 3: Add the minimal policy**

Bootstrap `core/review-routing.toml` from the approved design in specification §§4–5. The
specification tables are a historical design view only; from this task onward, the TOML file is
the sole normative source for thresholds and every matrix cell. Do not copy those values into
Python, Markdown, adapters or templates.

Represent each path marker as a closed object with explicit `glob`, `level` and
`security_relevant`. Add trusted required-check entries with `name` and `source_app_slug`, plus
the expected dedicated publisher app slug for the later Issue-#3 writer. Reject an empty required
check list.

The ADR records the binary usability decision, diagnostic status preservation, no
remaining-budget routing, COMMENTED evidence mapping, read-only boundary and rejected
alternatives.

Put every enum, immutable record, port protocol and typed error in `contracts.py`; it imports no
project module. Implement strict TOML parsing in `adapters/toml_config.py`. Reject unknown keys,
unsupported schema versions, non-positive/non-monotonic thresholds, incomplete tables, invalid
routes and absent matrix cells.

Add `[runtime] adapter_modules = [...]` to the TOML. `registry.py` imports configured modules with
`importlib`; factories declare provided/required ports. Add AST tests proving policy/risk/evidence/
adapters import only `contracts`, `__main__` imports no adapter, and missing/duplicate/cyclic
providers fail typed.

- [ ] **Step 4: Run focused and existing tests**

Run:

```bash
python3 -m unittest tests.test_review_routing_config tests.test_governance -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add core/review-routing.toml docs/decisions/0003-review-routing.md review_routing \
  tests/test_review_routing_config.py tests/test_review_routing_architecture.py \
  tests/test_governance.py
git commit -m "feat(governance): define review routing policy"
```

### Task 2: Domain contracts and deterministic route policy

**Files:**
- Create: `review_routing/policy.py`
- Create: `tests/test_review_routing_policy.py`

**Interfaces:**
- Produces enums `DiagnosticStatus`, `ReviewPurpose`, `RiskLevel`, `ReviewRoute`, `Reviewer`.
- Produces immutable `Usage`, `ProbeSignals`, `ProbeReport`, `RiskAssessment`, `ReviewRequest`,
  `QaCostEstimate`, `CapabilityEvidence`, `BillingPrincipal`, `RouteDecision` from contracts.
- Produces:
  `classify_usability(signals: ProbeSignals) -> tuple[bool, DiagnosticStatus]`.
- Produces:
  `route_review(request: ReviewRequest, config: RoutingConfig) -> RouteDecision`.

- [ ] **Step 1: Write failing status and matrix tests**

Table-drive all required diagnostics:

```python
cases = {
    DiagnosticStatus.AVAILABLE: True,
    DiagnosticStatus.LOW_BUDGET: True,
    DiagnosticStatus.QUOTA_EXHAUSTED: False,
    DiagnosticStatus.BUDGET_BLOCKED: False,
    DiagnosticStatus.RATE_LIMITED: False,
    DiagnosticStatus.PROVIDER_UNAVAILABLE: False,
    DiagnosticStatus.PERMISSION_DENIED: False,
    DiagnosticStatus.UNKNOWN: False,
}
```

Table-drive all 16 checkpoint/final combinations from the TOML. Assert that a known/unknown
`remaining` value produces the same route for otherwise identical input. Assert that unavailable
QA or SEC changes a required route to `BLOCKER`, never to a smaller reviewer set. Assert every
checkpoint with `copilot_usable = false` includes QA. Assert `security_relevant`, partial/unknown
file coverage and degraded/unknown Copilot mode add the required SEC/QA reviewers independently of
the numeric risk.

- [ ] **Step 2: Run the policy tests and confirm RED**

```bash
python3 -m unittest tests.test_review_routing_policy -v
```

Expected: import failure for `review_routing.contracts`.

- [ ] **Step 3: Implement immutable validated contracts**

Use string enums for stable JSON values. Validate:

```python
if not SHA_RE.fullmatch(base_sha) or not SHA_RE.fullmatch(head_sha):
    raise ValueError("base_sha and head_sha must be 40 lowercase hexadecimal characters")
if used is not None and (not math.isfinite(used) or used < 0):
    raise ValueError("used must be finite and non-negative")
```

`Usage.remaining` returns `None` unless both `used` and `limit` are known; it is never consumed by
`route_review`.

`QaCostEstimate` keeps model, estimated/actual input/output tokens, dated price source and
estimated/actual cost optional. `ReviewRequest` also carries `qa_available`/`sec_available`; a hard
QA budget or missing role context is represented as unavailable and can only create `BLOCKER` when
the matrix requires that reviewer.

`CapabilityEvidence` is repository-, principal- and review-mode-bound and expires. Historical
usage without a valid capability record never creates `copilot_usable = true`.

`RoutingConfig` contains the canonical `policy_digest`. Every `RouteDecision` copies this digest;
route serialization must never synthesize or omit it.

- [ ] **Step 4: Implement status precedence and policy lookup**

Use precedence:

```python
(
    BUDGET_BLOCKED,
    QUOTA_EXHAUSTED,
    RATE_LIMITED,
    PROVIDER_UNAVAILABLE,
    PERMISSION_DENIED,
    UNKNOWN,
    LOW_BUDGET,
    AVAILABLE,
)
```

For `CORRECTION`, require a non-empty prior reviewer set. Replace a now-unusable `COPILOT` with
`QA`, preserve prior QA/SEC requirements, bind the result to the new head, and map the resulting
reviewer set to one of the declared routes.

- [ ] **Step 5: Run focused tests and confirm GREEN**

```bash
python3 -m unittest tests.test_review_routing_policy -v
```

- [ ] **Step 6: Commit**

```bash
git add review_routing tests/test_review_routing_policy.py
git commit -m "feat(governance): implement deterministic review policy"
```

### Task 3: Deterministic risk classifier

**Files:**
- Create: `review_routing/risk.py`
- Create: `tests/test_review_routing_risk.py`

**Interfaces:**
- Consumes: `RoutingConfig`, `DiffSnapshot`, `RiskLevel`, `RiskAssessment`.
- Produces:
  `assess_risk(changes: DiffSnapshot, config: RoutingConfig) -> RiskAssessment`.

- [ ] **Step 1: Write failing boundary and path tests**

Cover one below/at/above each threshold, maximum-of-signals behavior, critical/high glob markers,
explicit risk escalation, inability to lower, separate `security_relevant`, missing diff data,
invalid negative counts and the closed versioned DiffSnapshot schema.

Example:

```python
assessment = assess_risk(
    DiffSnapshot(
        schema_version=1,
        repository="owner/repository",
        base_sha="a" * 40,
        head_sha="b" * 40,
        files=(
            DiffFile(
                path="core/core.md",
                status=FileStatus.MODIFIED,
                additions=1,
                deletions=0,
                binary=False,
            ),
        ),
    ),
    config,
)
self.assertEqual(assessment.level, RiskLevel.CRITICAL)
self.assertIn("critical_path:core/core.md", assessment.reasons)
```

- [ ] **Step 2: Run and confirm RED**

```bash
python3 -m unittest tests.test_review_routing_risk -v
```

- [ ] **Step 3: Implement pure maximum-based classification**

Use `fnmatch.fnmatchcase`, deterministic sorted reasons and explicit threshold reason names.
Consume the closed `DiffSnapshot` directly; do not introduce a second reduced change schema.
Normalize paths as relative NFC POSIX paths and reject absolute, `..`, backslash, duplicate and NUL
forms. Missing required data classifies `CRITICAL` with `incomplete_diff_metadata`.

- [ ] **Step 4: Run and confirm GREEN**

```bash
python3 -m unittest tests.test_review_routing_risk -v
```

- [ ] **Step 5: Commit**

```bash
git add review_routing/risk.py tests/test_review_routing_risk.py
git commit -m "feat(governance): classify review risk deterministically"
```

### Task 4: GitHub read-only probe adapter

**Files:**
- Create: `review_routing/adapters/github_gh.py`
- Create: `tests/test_review_routing_github.py`
- Create: `tests/fixtures/review-routing/ai-credits.json`
- Create: `tests/fixtures/review-routing/legacy-premium.json`
- Create: `tests/fixtures/review-routing/status-operational.json`

**Interfaces:**
- Implements contract ports `CommandPort`, `StatusPort`, `ClockPort`, `ProbePort`.
- Produces `GitHubGhProbe.probe(repository, context, billing_model) -> ProbeReport`.
- Uses documented API version `2026-03-10`.

- [ ] **Step 1: Write failing adapter tests with fake ports**

Cover:

- personal AI credits;
- AI credits without limit;
- legacy premium requests;
- organization seat confirmed;
- organization membership without seat evidence;
- manual requester versus automatic PR-author attribution;
- ambiguous organization/enterprise/cost-center principal;
- unknown enterprise/cost-center context;
- explicit quota and budget blocks;
- HTTP 403/permission diagnostics;
- 429/rate headers;
- 503/provider unavailable;
- empty, malformed and incomplete JSON;
- current explicit block plus API permission denial;
- absent/expired/wrong-principal capability evidence;
- valid recent capability evidence;
- endpoint selection and API version header;
- no raw stderr/header/token material in `ProbeReport.to_dict()`.

- [ ] **Step 2: Run and confirm RED**

```bash
python3 -m unittest tests.test_review_routing_github -v
```

- [ ] **Step 3: Implement the injected clients**

Invoke `gh api --include` without embedding credentials. Parse only HTTP status, selected safe
headers and JSON. Discard raw authorization/cookie headers and raw stderr after classification.
Use `urllib.request` only for the public GitHub Status components endpoint, with timeout and an
injectable client in tests.

Automatic context rules:

```text
manual -> requester is candidate principal
automatic -> PR author is candidate principal
confirmed personal billing -> personal
organization + confirmed seat/policy attribution -> organization
ambiguous or unpermitted attribution -> unknown/permission_denied
enterprise -> only explicit/API-backed selector
```

- [ ] **Step 4: Run and confirm GREEN**

```bash
python3 -m unittest tests.test_review_routing_github -v
```

- [ ] **Step 5: Commit**

```bash
git add review_routing/adapters/github_gh.py \
  tests/test_review_routing_github.py tests/fixtures/review-routing
git commit -m "feat(governance): probe Copilot availability read only"
```

### Task 5: CLI, JSON and exitcode contract

**Files:**
- Create: `review_routing/__main__.py`
- Create: `tests/test_review_routing_cli.py`

**Interfaces:**
- Consumes all earlier package interfaces.
- Produces `main(argv: Sequence[str] | None = None) -> int`.
- Produces injectable
  `CliDependencies(probe: ProbePort, routing_config: Path, clock: Clock)`.
- Commands initially: `probe`, `route`; output is one JSON object on stdout.

- [ ] **Step 1: Write failing CLI tests**

Use `main(..., dependencies=CliDependencies(...), stdout=StringIO())`. Cover valid probe,
permission/rate/provider/unknown/incomplete exitcodes `20`–`24`, every route, blocker `30`, invalid
input `31`, invalid SHA, invalid JSON and no dispatch side effect. Probe tests require
`--review-mode manual --requester USER` or
`--review-mode automatic --pull-request NUMBER`, plus a matching capability-evidence input before
`copilot_usable` may become true.

- [ ] **Step 2: Run and confirm RED**

```bash
python3 -m unittest tests.test_review_routing_cli -v
```

- [ ] **Step 3: Implement strict argparse and stable serialization**

The JSON object includes `schema_version`, `observed_at`, repository, context, model, usage,
signals, routing status, binary usability, evidence and warnings. Write diagnostics only inside
the JSON; stdout contains no progress prose. Invalid invocations use exit `31` with a sanitized
JSON error.

- [ ] **Step 4: Run and confirm GREEN**

```bash
python3 -m unittest tests.test_review_routing_cli -v
```

- [ ] **Step 5: Commit**

```bash
git add review_routing/__main__.py tests/test_review_routing_cli.py
git commit -m "feat(governance): expose review routing CLI"
```

### Task 6: Exact-head evidence validator

**Files:**
- Create: `review_routing/evidence.py`
- Create: `tests/test_review_routing_evidence.py`

**Interfaces:**
- Produces contract records `ReviewRecord`, `ThreadRecord`, `CheckRecord`, `FileCoverage`,
  `GateSnapshot`, `GateResult`, `PublicationReceipt`.
- Produces:
  `validate_exact_head(
      decision: RouteDecision,
      evidence: GateSnapshot,
      config: RoutingConfig,
  ) -> GateResult`.
- Extends CLI with:
  `validate --route-file ROUTE.json --evidence-file EVIDENCE.json
  --config core/review-routing.toml --json`.

- [ ] **Step 1: Write failing evidence tests**

Cover valid Copilot `COMMENTED`, wrong bot, wrong SHA, pending/error review, unresolved Copilot
thread, newer pending request, missing QA/SEC, stale QA/SEC, missing/failing/skipped/cancelled CI,
successful exact-head checks, unresolved non-Copilot thread, correction head invalidation,
excluded/unverified files, degraded/unknown Copilot mode, QA coverage replacement, stable check
name and deterministic policy/evidence digests. Also cover a route policy-digest mismatch,
an empty trusted required-check policy, a spoofed same-name check from the wrong app slug and an
attempt to inject required check names through evidence.

- [ ] **Step 2: Run and confirm RED**

```bash
python3 -m unittest tests.test_review_routing_evidence -v
```

- [ ] **Step 3: Implement fail-closed set validation**

Never emit `APPROVED` for Copilot. Return:

```python
GateResult(
    check_name="agent-governance/review-gate",
    conclusion="failure",
    reasons=("missing_reviewer:qa",),
)
```

Only all required reviewers + all policy-required successful checks from their expected app
sources + zero unresolved threads is valid.
Every diff file must have positive coverage by the route's reviewer set. The result includes repo,
PR, base/head, policy digest, evidence digest, reviewer sets and observation time. Define a
`GatePublisherPort.publish(result: GateResult) -> PublicationReceipt` in contracts but provide no
writer in this read-only PR. The receipt and port contract define the deterministic idempotency key
over repository/PR/head/policy/evidence digests, the dedicated publisher app identity and mandatory
read-only head revalidation immediately before a future write.

Wire the `validate` CLI command. Valid evidence returns `0`; missing, stale or contradictory
exact-head evidence returns `32` with sanitized reasons.

- [ ] **Step 4: Run and confirm GREEN**

```bash
python3 -m unittest tests.test_review_routing_evidence -v
```

- [ ] **Step 5: Commit**

```bash
git add review_routing/evidence.py review_routing/__main__.py \
  tests/test_review_routing_evidence.py tests/test_review_routing_cli.py
git commit -m "feat(governance): validate exact head review evidence"
```

### Task 7: Governance and documentation integration

**Files:**
- Modify: `core/core.md`
- Modify: `core/roles/qa.md`
- Modify: `core/roles/sec.md`
- Modify: `adapters/claude.md`
- Modify: `adapters/codex.md`
- Modify: `templates/claude-agents/qa-agent.md`
- Modify: `templates/claude-agents/sec-agent.md`
- Modify: `README.md`
- Modify: `INSTALL.md`
- Modify: `tools/tools.md`
- Modify: `tests/test_governance.py`

**Interfaces:**
- Consumes the CLI and TOML paths.
- Produces one prose contract that references, but does not duplicate, the machine matrix.

- [ ] **Step 1: Extend drift tests first**

Require all relevant artifacts to reference the policy, prohibit route-table duplication outside
the TOML/tests/ADR, require `probe`/`route` in README and tools catalog, and ensure templates no
longer claim QA after every cluster.

- [ ] **Step 2: Run and confirm RED**

```bash
python3 -m unittest tests.test_governance -v
```

- [ ] **Step 3: Update governance prose and harness wiring**

Change §5.5 and §16 so checkpoint QA is policy-driven, QA can be additive at high risk, unusable
Copilot always falls back to QA, critical risk adds SEC, corrections re-evaluate on the new head,
and paid dispatch needs explicit authorization. Preserve fail-closed CI and exact-head rules.

- [ ] **Step 4: Document real commands and limitations**

README/INSTALL/tools include:

```bash
python3 -m review_routing probe --repo OWNER/REPO --json
python3 -m review_routing route --probe-file probe.json \
  --purpose final_exact_head --base-sha BASE --head-sha HEAD \
  --diff-file diff.json --json
python3 -m unittest discover -s tests -v
```

Document required GitHub permissions, context limits, live-positive-test procedure and Issue #3.

- [ ] **Step 5: Run all tests**

```bash
python3 -m unittest discover -s tests -v
```

- [ ] **Step 6: Commit**

```bash
git add core adapters templates README.md INSTALL.md tools tests/test_governance.py
git commit -m "docs(governance): wire deterministic review routing"
```

### Task 8: Local negative acceptance and complete verification

**Files:**
- Modify: `README.md` or PR evidence only if a reproducible command was missing.

**Interfaces:**
- Validates the shipped repository; no new production interface.

- [ ] **Step 1: Run focused suites**

```bash
python3 -m unittest tests.test_review_routing_config \
  tests.test_review_routing_policy \
  tests.test_review_routing_risk \
  tests.test_review_routing_github \
  tests.test_review_routing_cli \
  tests.test_review_routing_evidence -v
```

- [ ] **Step 2: Run complete regression and syntax checks**

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q review_routing tests
git diff --check origin/main...HEAD
```

- [ ] **Step 3: Run the current live read-only negative probe**

Run only `probe`; never dispatch Copilot. Record exact head, sanitized JSON and exitcode. The
expected current result is unusable via explicit billing evidence and/or `permission_denied`.
Do not print auth state details.

- [ ] **Step 4: Scan for secrets and unfinished code**

```bash
rg -n "(TODO|FIXME|TBD|Authorization:|Bearer |gho_|github_pat_)" \
  review_routing core adapters templates tests docs README.md INSTALL.md
```

Expected: no unfinished implementation and no secret material; documentation terms may require
review rather than blind acceptance.

- [ ] **Step 5: Route any failure back to its owning task**

Do not create an unscoped cleanup commit. Re-enter the task that owns the failed contract, add a
regression test, make the minimum correction and use that task's explicit file list and commit
prefix.

- [ ] **Step 6: Push and bind evidence to the exact head**

```bash
git push
git rev-parse HEAD
gh pr view 5 --json headRefOid,statusCheckRollup
```

Update Issue #4 and PR #5 with exact local evidence. Leave GitHub CI and the real Copilot positive
test unchecked until the user confirms the billing lock is removed.
