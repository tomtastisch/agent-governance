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
- `review_routing/runtime.toml`: installed bootstrap SSOT for immutable port-to-factory selection.
- `review_routing/contracts.py`: the single module for every port, domain/config/evidence/error type.
- `review_routing/registry.py`: runtime factory registration and dependency resolution.
- `review_routing/risk.py`: pure diff risk classifier.
- `review_routing/policy.py`: pure usability classifier and reviewer route selector.
- `review_routing/evidence.py`: pure Copilot/QA/SEC exact-head evidence validation.
- `review_routing/adapters/toml_config.py`: strict TOML configuration port implementation.
- `review_routing/adapters/git_cli.py`: trusted read-only policy and complete diff acquisition.
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
- Create: `review_routing/runtime.toml`
- Create: `review_routing/contracts.py`
- Create: `review_routing/registry.py`
- Create: `review_routing/adapters/__init__.py`
- Create: `review_routing/adapters/toml_config.py`
- Create: `tests/test_review_routing_config.py`
- Create: `tests/test_review_routing_architecture.py`

**Interfaces:**
- Produces
  `ConfigPort.parse_routing(document: PolicyDocument) -> RoutingConfig`.
- Produces `RuntimeRegistry.register(factory: AdapterFactory) -> None` and
  `RuntimeRegistry.resolve(port: type[T]) -> T`.
- Produces `DocumentTrust(development|commit_object)`, `RuntimeTrustSource`,
  `RuntimeTrustConfig(expected_runtime_digest, source, observed_at)`,
  `RuntimeTrustPort.load() -> RuntimeTrustConfig` and
  `RuntimeProvenance(digest, trust=installed|development)`.
- Only a manifest digest matching an externally supplied pin from `publisher_app` or
  `installed_config` yields `installed`; missing pin is development, mismatched pin is a typed
  hard failure. This PR has no trusted publisher implementation of `RuntimeTrustPort`.
- `RuntimeRegistry.bootstrap(None)` creates the built-in development-only trust config. A trusted
  port is injectable only through programmatic `CliDependencies`; no CLI flag may claim installed
  trust.
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
self.assertNotIn("runtime", raw)
```

Assert that `gate.required_checks` is non-empty and every entry contains only `name` and
`source_app_slug`. Assert that `gate.publisher.expected_app_slug` is non-empty. Also assert that
every `risk.path_markers` entry contains only `glob`, `level` and `security_relevant`.
Parse `review_routing/runtime.toml` separately; require only the closed bootstrap keys and prove
that changing/injecting a runtime table in the candidate routing policy cannot change the loaded
factory set.

At this stage, require only the TOML, parser, contracts, registry and ADR to agree. Full
core/adapter/template/README drift tests are deliberately deferred to Task 7, where those files
are first modified.

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
`security_relevant`. Reject any `[runtime]` table in the routing policy. Add trusted required-check
entries with `name` and `source_app_slug`, plus
the expected dedicated publisher app slug for the later Issue-#3 writer. Reject an empty required
check list.

The ADR records the binary usability decision, diagnostic status preservation, no
remaining-budget routing, COMMENTED evidence mapping, read-only boundary and rejected
alternatives.

Put the config/registry records, declared ports and typed errors needed by this task in
`contracts.py`; it imports no project module. Every later task adds its new domain/evidence types
to this same module before implementing behavior—no second contracts module is allowed.
Implement strict TOML parsing in `adapters/toml_config.py`. Reject unknown keys, unsupported
schema versions, non-positive/non-monotonic thresholds, incomplete tables, invalid routes and
absent matrix cells.

Add adapter module identifiers only to the separate packaged `review_routing/runtime.toml`.
`registry.py` loads that bootstrap SSOT with `importlib.resources` and imports configured modules
with `importlib`; factories declare provided/required ports. A development/source-checkout
runtime is explicitly non-gate-eligible; the later publisher binds the installed manifest digest.
Test that a `[runtime]` injection in `core/review-routing.toml` is rejected and cannot replace
Policy-/Diff-source factories. In this task, AST-test only the modules
that exist now: `contracts.py` imports no project module; `registry.py` and `toml_config.py` know
only the contracts boundary. Test missing/duplicate/cyclic providers with typed failures.
Test external runtime pin absent/matching/mismatching and source trust. Task 1 lists only the
TOML-config factory in `runtime.toml` and resolves it successfully.
Each later task extends this same architecture test when its new module first exists; no
vacuously passing checks for absent modules.

- [ ] **Step 4: Run focused and existing tests**

Run:

```bash
python3 -m unittest tests.test_review_routing_config \
  tests.test_review_routing_architecture tests.test_governance -v
```

Expected: all pass.

- [x] **Step 5: Commit**

```bash
git add core/review-routing.toml docs/decisions/0003-review-routing.md review_routing \
  tests/test_review_routing_config.py tests/test_review_routing_architecture.py
git commit -m "feat(governance): define review routing policy"
```

### Task 2: Domain contracts and deterministic route policy

**Files:**
- Modify: `review_routing/contracts.py`
- Modify: `review_routing/runtime.toml`
- Create: `review_routing/policy.py`
- Create: `tests/test_review_routing_policy.py`
- Modify: `tests/test_review_routing_architecture.py`

**Interfaces:**
- Produces enums `DiagnosticStatus`, `ReviewPurpose`, `RiskLevel`, `ReviewRoute`, `Reviewer`.
- Produces immutable `Usage`, `ProbeSignals`, `ProbeReport`, `RiskAssessment`, `ReviewRequest`,
  `QaCostEstimate`, `CapabilityEvidence`, `BillingPrincipal`, `RouteDecision` from contracts.
- Produces:
  `classify_usability(signals: ProbeSignals) -> tuple[bool, DiagnosticStatus]`.
- Produces:
  `route_review(request: ReviewRequest, config: RoutingConfig) -> RouteDecision`.
- Implements `RoutingPolicyPort`.
- Adds `RoutingPolicyPort.route(request, config) -> RouteDecision` to contracts together with all
  referenced request/decision types.
- Adds the policy factory to `runtime.toml` and proves registry resolution in RED/GREEN tests.

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
python3 -m unittest tests.test_review_routing_policy \
  tests.test_review_routing_architecture -v
```

Expected: failure because `review_routing.policy` does not exist.

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
route serialization must never synthesize or omit it. It also carries `policy_source_ref`,
`policy_source_path`, `runtime_digest`, `runtime_trust`, `diff_digest` and all policy-relevant
request inputs needed for deterministic revalidation.

Extend the architecture test so `policy.py` imports only `contracts.py`.

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
python3 -m unittest tests.test_review_routing_policy \
  tests.test_review_routing_architecture -v
```

- [ ] **Step 6: Commit**

```bash
git add review_routing tests/test_review_routing_policy.py \
  tests/test_review_routing_architecture.py
git commit -m "feat(governance): implement deterministic review policy"
```

### Task 3: Deterministic risk classifier

**Files:**
- Modify: `review_routing/contracts.py`
- Modify: `review_routing/runtime.toml`
- Create: `review_routing/risk.py`
- Create: `review_routing/adapters/git_cli.py`
- Create: `tests/test_review_routing_risk.py`
- Create: `tests/test_review_routing_git.py`
- Modify: `tests/test_review_routing_architecture.py`

**Interfaces:**
- Consumes: `RoutingConfig`, `DiffSnapshot`, `RiskLevel`, `RiskAssessment`.
- Produces:
  `assess_risk(changes: DiffSnapshot, config: RoutingConfig) -> RiskAssessment`.
- Implements `RiskClassifierPort`.
- Adds `RiskClassifierPort.assess(
      snapshot: DiffSnapshot,
      config: RoutingConfig,
  ) -> RiskAssessment`.
- Adds `PolicySourcePort.read_at_commit(
      repo_path: Path,
      repository: str,
      commit_sha: str,
      policy_path: PurePosixPath,
  ) -> PolicyDocument`.
- Adds `DiffSourcePort.load(
      repo_path: Path,
      repository: str,
      api_base_sha: str,
      head_sha: str,
  ) -> DiffSnapshot`.
- Implements `PolicySourcePort` and `DiffSourcePort` with read-only local Git commands.
- Adds risk/Git factories to `runtime.toml` and proves registry resolution in RED/GREEN tests.

- [ ] **Step 1: Write failing boundary and path tests**

Cover one below/at/above each threshold, maximum-of-signals behavior, critical/high glob markers,
explicit risk escalation, inability to lower, separate `security_relevant`, missing diff data,
invalid negative counts and the closed versioned DiffSnapshot schema. Require `previous_path`
exactly for renamed/copied files and classify old and new paths.

Adapter tests create temporary local repositories and cover complete add/modify/delete
enumeration, binary files, exact full-SHA validation, missing/non-commit objects, policy reads at
the base commit, a policy changed only on head, conflicting Git metadata and sanitized failures.
They also cover advanced/diverged Base-Refs and ambiguous rename/copy candidates, which must be
represented deterministically as delete+add. No test accesses GitHub or a network.

Example:

```python
assessment = assess_risk(
    DiffSnapshot(
        schema_version=1,
        repository="owner/repository",
        api_base_sha="a" * 40,
        merge_base_sha="c" * 40,
        head_sha="b" * 40,
        diff_mode=DiffMode.MERGE_BASE_TO_HEAD,
        rename_detection=DetectionMode.DISABLED,
        copy_detection=DetectionMode.DISABLED,
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
python3 -m unittest tests.test_review_routing_risk tests.test_review_routing_git \
  tests.test_review_routing_architecture -v
```

- [ ] **Step 3: Implement pure maximum-based classification**

Use `fnmatch.fnmatchcase`, deterministic sorted reasons and explicit threshold reason names.
Consume the closed `DiffSnapshot` directly; do not introduce a second reduced change schema.
Normalize paths as relative NFC POSIX paths and reject absolute, `..`, backslash, duplicate and NUL
forms. Missing required data classifies `CRITICAL` with `incomplete_diff_metadata`. Compute the
canonical SHA-256 `diff_digest`.

Implement the Git adapter by full object IDs, not mutable branch names. Verify canonical repo
toplevel and normalized origin against `OWNER/REPO`. Compute `merge_base_sha` from API Base-SHA
and Head-SHA, then diff merge-base→head with `--no-ext-diff --no-textconv --no-renames`.
Reconcile NUL-delimited raw and numstat output fail-closed; record API Base-SHA, merge-base,
Head-SHA and the fixed detection mode in provenance/digest. Never accept caller-supplied file
lists as authoritative. Extend the architecture test so `risk.py` and `git_cli.py` import only
contracts.

- [ ] **Step 4: Run and confirm GREEN**

```bash
python3 -m unittest tests.test_review_routing_risk tests.test_review_routing_git \
  tests.test_review_routing_architecture -v
```

- [x] **Step 5: Commit**

```bash
git add review_routing/contracts.py review_routing/runtime.toml review_routing/risk.py \
  review_routing/adapters/git_cli.py \
  tests/test_review_routing_risk.py tests/test_review_routing_git.py \
  tests/test_review_routing_architecture.py
git commit -m "feat(governance): classify review risk deterministically"
```

### Task 4: GitHub read-only probe adapter

**Files:**
- Modify: `review_routing/contracts.py`
- Modify: `review_routing/runtime.toml`
- Create: `review_routing/adapters/github_gh.py`
- Create: `tests/test_review_routing_github.py`
- Create: `tests/fixtures/review-routing/ai-credits.json`
- Create: `tests/fixtures/review-routing/legacy-premium.json`
- Create: `tests/fixtures/review-routing/status-operational.json`
- Modify: `tests/test_review_routing_architecture.py`

**Interfaces:**
- Adds and implements:
  `CommandPort.run(
      argv: tuple[str, ...],
      timeout_seconds: float,
  ) -> CommandResult`.
- Adds and implements:
  `StatusPort.fetch(timeout_seconds: float) -> StatusSnapshot`.
- Adds and implements:
  `ClockPort.now() -> datetime`.
- Adds and implements:
  `ProbePort.probe(request: ProbeRequest) -> ProbeReport`.
- Adds and implements `CapabilityEvidenceVerifierPort.verify(...)` and
  `BlockEvidenceVerifierPort.verify(...)`. `ProbeRequest` carries only untrusted references;
  verified evidence is reconstructed inside these ports.
- Adds `OperatorEvidenceTrustPort.load(...)`. Only an externally provided `publisher_app` or
  `installed_config` digest pin can verify evidence; no CLI value is trusted as a pin.
- `RuntimeRegistry.bootstrap(CliDependencies(...))` preserves the exact injected
  `OperatorEvidenceTrustPort` instance and supplies it to both verifiers and the resulting probe.
- Adds
  `PullRequestStatePort.load(
      repository: str,
      pull_request_number: int,
  ) -> PullRequestState`
  and the closed `PullRequestState` type to contracts in this task.
- `PullRequestState` contains repository, PR number, base ref, full API base SHA, full head SHA,
  author, observed-at and `source=github_api`.
- `ProbeRequest` contains repository, review mode, optional manual requester, optional PR number,
  optional explicit organization/enterprise/cost-center selector plus untrusted capability/block
  references; the adapter determines the billing model instead of trusting a caller hint.
- `CommandResult` contains return code and raw stdout/stderr bytes only inside the adapter
  boundary. `StatusSnapshot` and all public reports contain only typed/sanitized fields.
- Typed port errors distinguish permission denied, rate limited, provider unavailable, timeout,
  malformed/incomplete response and unknown context.
- Adds the GitHub factory to `runtime.toml` and proves registry resolution in RED/GREEN tests.
- Produces `GitHubGhProbe.probe(request: ProbeRequest) -> ProbeReport`.
- Uses documented API version `2026-03-10`.

- [x] **Step 1: Write failing adapter tests with fake ports**

Cover:

- personal AI credits;
- AI credits without limit;
- legacy premium requests;
- organization seat confirmed;
- organization membership or Seat-404 without seat evidence, without personal fallback;
- manual requester versus automatic PR-author attribution;
- ambiguous organization/enterprise/cost-center principal;
- unknown enterprise/cost-center context;
- usage payloads cannot assert quota/budget blocks;
- externally digest-pinned operator-only explicit quota and budget blocks;
- HTTP 403/permission diagnostics;
- 429/rate headers;
- 503/provider unavailable;
- empty, malformed and incomplete JSON;
- current verified block plus API permission denial, with the technical error taking precedence;
- absent/expired/wrong-principal capability evidence;
- valid recent capability evidence reconstructed only from an externally digest-pinned
  `operator_setting` or `completed_review_context`;
- `completed_review_context` revalidation against GitHub bot, `COMMENTED`, PR, review ID,
  review commit and timestamp only after the external pin matches;
- the API review ID has exactly the integer type; bool, float, string and null fail closed;
- an identical API review cannot verify another principal or review mode;
- API-/provider block sources and bool schema/PR/review IDs fail closed;
- capability/block verifier errors drive routing precedence;
- Actions billing-lock annotations do not assert Copilot blocks;
- `ProbeReport.capability_status` is derived from `CapabilityVerification`; replace-based status,
  trust, evidence, presence and usability mismatches fail closed;
- interim/multiple `gh api --include` HTTP blocks and safe known stderr diagnostics;
- endpoint selection and API version header;
- no raw stderr/header/token material in `ProbeReport.to_dict()`.
- exact repository, PR number, Base-Ref, full Base-SHA and full Head-SHA from PR metadata.

- [x] **Step 2: Run and confirm RED**

```bash
python3 -m unittest tests.test_review_routing_github \
  tests.test_review_routing_architecture -v
```

- [x] **Step 3: Implement the injected clients**

Invoke `gh api --include` without embedding credentials. Parse only HTTP status, selected safe
headers and JSON. Discard raw authorization/cookie headers and raw stderr after classification.
Use `urllib.request` only for the public GitHub Status components endpoint, with timeout and an
injectable client in tests.
Extend the architecture test so `github_gh.py` imports only contracts. Usage endpoints always
carry UTC year/month; organization usage additionally carries the URL-encoded candidate user.
Usage sums `grossQuantity` only and never imports a free response `status` or `limit` into routing.

Fake tests implement the exact port signatures above and assert typed errors are converted to
the declared diagnostic status/exitcode without raw stderr, headers or credentials escaping.

Automatic context rules:

```text
manual -> requester is candidate principal
automatic -> PR author is candidate principal
confirmed personal billing -> personal
organization + confirmed seat/policy attribution -> organization
ambiguous or unpermitted attribution -> unknown/permission_denied
enterprise -> only explicit/API-backed selector
```

- [x] **Step 4: Run and confirm GREEN**

```bash
python3 -m unittest tests.test_review_routing_github \
  tests.test_review_routing_architecture -v
```

- [ ] **Step 5: Commit**

```bash
git add review_routing/contracts.py review_routing/runtime.toml \
  review_routing/adapters/github_gh.py \
  tests/test_review_routing_github.py tests/fixtures/review-routing \
  tests/test_review_routing_architecture.py
git commit -S -m "feat(governance): probe Copilot availability read only"
```

### Task 5: CLI, JSON and exitcode contract

**Files:**
- Create: `review_routing/__main__.py`
- Create: `tests/test_review_routing_cli.py`
- Modify: `tests/test_review_routing_architecture.py`

**Interfaces:**
- Consumes all earlier package interfaces.
- Produces `main(argv: Sequence[str] | None = None) -> int`.
- Produces injectable
  `CliDependencies(
      runtime_trust: RuntimeTrustPort,
      operator_evidence_trust_port: OperatorEvidenceTrustPort,
      probe: ProbePort,
      pull_request_state: PullRequestStatePort,
      reviewer_availability: ReviewerAvailabilityPort,
      config: ConfigPort,
      policy_source: PolicySourcePort,
      diff_source: DiffSourcePort,
      clock: ClockPort,
  )`.
- Commands initially: `probe`, `route`; output is one JSON object on stdout.

- [ ] **Step 1: Write failing CLI tests**

Use `main(..., dependencies=CliDependencies(...), stdout=StringIO())`. Cover valid probe,
permission/rate/provider/unknown/incomplete exitcodes `20`–`24`, every route, blocker `30`, invalid
input `31`, invalid SHA, invalid JSON and no dispatch side effect. Probe tests require
`--review-mode manual --requester USER` or
`--review-mode automatic --pull-request NUMBER`, plus a matching untrusted capability reference
before a verifier may reconstruct routing evidence and `copilot_usable` may become true. The CLI
must expose no Trust-, Issuer-, Source-, Pin-Source- or Digest-Override and no Billing-/Quota-
assertion. `OperatorEvidenceTrustPort` is injected programmatically through `CliDependencies`;
the normal source-checkout CLI has no evidence pins. Route tests provide repository/PR
number and prove the CLI reads
the actual Base-Ref/Base-SHA/Head-SHA through `PullRequestStatePort`, then reads policy from that
Base-SHA and the complete diff through injected ports. A missing Basispolicy, caller-supplied file
list/SHA or policy source from head/worktree must fail with `31`. An explicitly separate offline
diagnostic mode may accept SHAs but must serialize `gate_eligible = false`.
Tests also prove that only an externally pinned matching runtime digest can produce
`runtime_trust=installed`; the normal source-checkout CLI dependency is development-only.
Argparse exposes no runtime-trust/digest override flag, setzt `allow_abbrev=False` am Haupt- und
an jedem Unterparser und akzeptiert keine abgekürzten Langoptionen.

`route` akzeptiert keine Probe-Datei. Es lädt zuerst den PR-State, baut daraus samt Reviewmodus,
Requester/PR, optionalen Selektoren und untrusted Capability-Referenz eine frische
`ProbeRequest`, ruft `ProbePort.probe()` genau einmal auf und verwirft Reports mit abweichendem
Request-Digest, PR, Principal, Modus oder Zeitfenster. `ProbeReport` bindet
`pull_request_number`, `request_digest` und `valid_until` konstruktiv. QA-/SEC-Verfügbarkeit
stammt ausschließlich aus dem programmatisch injizierten, zeit- und Exact-Head-gebundenen
`ReviewerAvailabilityPort`; es gibt keine `--qa-available`-/`--sec-available`-Flags.

- [ ] **Step 2: Run and confirm RED**

```bash
python3 -m unittest tests.test_review_routing_cli \
  tests.test_review_routing_architecture -v
```

- [ ] **Step 3: Implement strict argparse and stable serialization**

The JSON object includes `schema_version`, `observed_at`, repository, context, model, usage,
signals, routing status, binary usability, evidence and warnings. Write diagnostics only inside
the JSON; stdout contains no progress prose. Invalid invocations use exit `31` with a sanitized
JSON error. `route` serializes trusted policy provenance and `diff_digest`. Da Task 5 noch keine
belastbare Coverage und keinen belegten Copilot-Reviewmodus besitzt, serialisiert es immer
`copilot_coverage_complete=null`, `copilot_review_mode=unknown`,
`decision_stage=preliminary`, `gate_status=evidence_validation_pending`,
`gate_eligible=false` und `dispatch_permitted=false`. The Composition Root
resolves every adapter through `RuntimeRegistry` and imports no concrete adapter module; extend
the architecture test accordingly.

- [ ] **Step 4: Run and confirm GREEN**

```bash
python3 -m unittest tests.test_review_routing_cli \
  tests.test_review_routing_architecture -v
```

- [ ] **Step 5: Commit**

```bash
git add review_routing/__main__.py tests/test_review_routing_cli.py \
  tests/test_review_routing_architecture.py
git commit -m "feat(governance): expose review routing CLI"
```

### Task 6: Exact-head evidence validator

**Files:**
- Modify: `review_routing/contracts.py`
- Modify: `review_routing/runtime.toml`
- Create: `review_routing/evidence.py`
- Modify: `review_routing/__main__.py`
- Create: `tests/test_review_routing_evidence.py`
- Modify: `tests/test_review_routing_cli.py`
- Modify: `tests/test_review_routing_architecture.py`

**Interfaces:**
- Produces contract records `ReviewRecord`, `ThreadRecord`, `CheckRecord`, `FileCoverage`,
  `GateSnapshot`, `PreliminaryRoutePlan`, `GateEvaluationContext`, `GateResult` and
  `PublicationReceipt`.
- `PreliminaryRoutePlan` dekodiert das vollständige Task-5-Schema. Nur Repository, PR, Purpose,
  Base-Ref, Base-/Head-/Merge-Base-SHAs, PR-State-Quelle, Risiko/Security sowie
  Policy-/Runtime-/Diff-Provenienz und -Digests sind Vergleichseingaben. Seine Usability,
  Coverage, Reviewmodus, Route, Reviewer und Gatefelder sind explizit `untrusted preliminary`.
- `FileCoverage` enthält die geschlossene `coverage_source`; `GateSnapshot` enthält
  `copilot_review_mode` und die geschlossene `review_mode_source`. Beide Quellen sind an
  Repository, PR, Exact Head und Beobachtungszeit gebunden. Fehlende oder nicht belastbare
  Quellen ergeben `coverage=unverified` beziehungsweise `copilot_review_mode=unknown`, nie einen
  implizit positiven Wert. `GateSnapshot.valid_until` erzwingt gemeinsam mit `observed_at`
  `observed_at <= evaluated_at < valid_until`.
- Produces:
  `GateEvaluationContext(
      preliminary_plan: PreliminaryRoutePlan,
      current_pr_state: PullRequestState,
      probe_request: ProbeRequest,
      fresh_probe: ProbeReport,
      reviewer_availability: ReviewerAvailabilitySnapshot,
      evaluated_at: datetime,
  )`.
- Adds `EvidenceValidatorPort.validate(
      context: GateEvaluationContext,
      evidence: GateSnapshot,
      runtime: RuntimeProvenance,
      trusted_config: RoutingConfig,
      trusted_diff: DiffSnapshot,
      risk_classifier: RiskClassifierPort,
      routing_policy: RoutingPolicyPort,
  ) -> GateResult`.
- Produces:
  `validate_exact_head(
      context: GateEvaluationContext,
      evidence: GateSnapshot,
      runtime: RuntimeProvenance,
      trusted_config: RoutingConfig,
      trusted_diff: DiffSnapshot,
      risk_classifier: RiskClassifierPort,
      routing_policy: RoutingPolicyPort,
  ) -> GateResult`.
- Extends the injectable Task-6 composition root with
  `CliDependencies(
      runtime_trust_port: RuntimeTrustPort,
      operator_evidence_trust_port: OperatorEvidenceTrustPort,
      probe: ProbePort,
      pull_request_state: PullRequestStatePort,
      reviewer_availability: ReviewerAvailabilityPort,
      config: ConfigPort,
      policy_source: PolicySourcePort,
      diff_source: DiffSourcePort,
      clock: ClockPort,
  )`; Validator, Risiko und Policy kommen weiterhin über die Runtime-Registry.
- Extends CLI with:
  `validate --route-file ROUTE.json --evidence-file EVIDENCE.json
  --repo OWNER/REPO --pull-request NUMBER
  --review-mode manual --requester USER
  [--organization ORG] [--enterprise ENTERPRISE] [--cost-center COST_CENTER]
  [--capability-reference CAPABILITY-REFERENCE.json]
  --repo-path /absolute/path/to/checkout --json`.

Bei `automatic` ist `--requester` verboten; bei `manual` ist er Pflicht. `validate` lädt zuerst
den aktuellen `PullRequestState`, baut daraus mit exakt demselben vollständigen Probe-Kontext wie
`route` eine neue `ProbeRequest`, ruft `ProbePort.probe()` genau einmal frisch auf und prüft
Request-Digest, PR, Principal, Modus und TTL. Danach lädt es den
`ReviewerAvailabilityPort` genau einmal für Repository/PR/Head/Purpose. Der serialisierte
`probe_request_digest` aus Task 5 ist nicht rekonstruierbar und keine Autorität.

- [ ] **Step 1: Write failing evidence tests**

Cover valid Copilot `COMMENTED`, wrong bot, wrong SHA, pending/error review, unresolved Copilot
thread, newer pending request, missing QA/SEC, stale QA/SEC, missing/failing/skipped/cancelled CI,
successful exact-head checks, unresolved non-Copilot thread, correction head invalidation,
excluded/unverified files, degraded/unknown Copilot mode, QA coverage replacement, stable check
name, `coverage_source`, `review_mode_source` and deterministic policy/evidence digests. Also
cover a route policy-digest mismatch,
an empty trusted required-check policy, a spoofed same-name check from the wrong app slug and an
attempt to inject required check names through evidence. Cover a policy changed only on head,
missing Basispolicy during bootstrap, missing/extra/changed diff files, rename/copy source-path
evasion, diff-digest mismatch, changed risk/security result and an unzulässiges Entfernen
risiko-/security-/fallback-/correction-bedingter Reviewer. Cover
caller-selected SHAs versus API PR state, changed Base-Ref/Head between route and validate and
offline `gate_eligible = false`.

Task 6 lädt PR-State, Policy, Diff, Risiko und eine frische Probe erneut, erhebt erstmals echte
Coverage sowie den tatsächlichen Reviewmodus und ruft danach die Policy neu auf. Die
Task-5-Reviewer-Menge ist keine finale Sollmenge und wird nicht als Gleichheitsinvariante
übernommen. QA darf nur entfernt werden, wenn sie in Task 5 ausschließlich wegen unbekannter
Coverage beziehungsweise unbekanntem Modus ergänzt wurde und Task 6
`coverage_complete=true` plus `full` positiv belegt; Risiko-, Security-, Fallback- und
Correction-QA bleibt.

Pflicht-Negativtests belegen zusätzlich:

- manipulierte Task-5-Werte für `copilot_usable`, Coverage, Reviewmodus, Route,
  `required_reviewers`, Gate-Status oder Gate-Fähigkeit beeinflussen die finale Entscheidung
  nicht;
- ein fremder, abgelaufener oder digest-/PR-/Principal-/Mode-fremder `fresh_probe` macht das Gate
  rot;
- fremde oder abgelaufene Reviewer-Availability-Evidenz macht das Gate rot;
- fehlende Reviewer-Availability wird als QA/SEC `false` geroutet;
- ein `probe_request_digest` ohne die rekonstruierte `probe_request` genügt nie;
- fremde, fehlende oder stale `coverage_source`/`review_mode_source` kann weder
  `coverage_complete=true` noch `copilot_review_mode=full` belegen.

- [ ] **Step 2: Run and confirm RED**

```bash
python3 -m unittest tests.test_review_routing_evidence \
  tests.test_review_routing_architecture -v
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
Validate `GateEvaluationContext` first. `fresh_probe` must match `probe_request`, current PR state
and `evaluated_at`; Reviewer-Availability must be current and Exact-Context-bound. Derive
`coverage_complete` exclusively by matching every path/status in `trusted_diff` exactly once
against `GateSnapshot.review_file_coverage` with a valid `coverage_source`. Derive
`copilot_review_mode` exclusively from `GateSnapshot` and its valid `review_mode_source`.

Recompute risk and routing from `trusted_diff` and `trusted_config`. From Task 5 compare only
repository, PR, purpose, Base-/Head-/Merge-Base-SHAs, policy/runtime/diff provenance and digests,
risk and security flag. Build the final `ReviewRequest` from recomputed risk,
`fresh_probe.copilot_usable`, derived `coverage_complete`, derived `copilot_review_mode` and the
current `reviewer_availability`, then invoke `RoutingPolicyPort` again. Never read
`preliminary_plan.copilot_usable`, preliminary coverage/mode, route, reviewer set, gate status or
gate eligibility as final authority. Every file from the trusted diff must have positive coverage
by the final route's reviewer set. The result includes repo, PR, base/head, trusted runtime and
policy source/path/digests, diff digest, evidence digest, reviewer sets and observation time.
Define a
`GatePublisherPort.publish(result: GateResult) -> PublicationReceipt` in contracts but provide no
writer in this read-only PR. The receipt and port contract define the deterministic idempotency key
over repository/PR/head/runtime/policy/evidence digests, the dedicated publisher app identity and
mandatory read-only head revalidation immediately before a future write.

Wire the `validate` CLI command. It reloads PR state through `PullRequestStatePort`, executes the
fresh bound probe and programmatic Reviewer-Availability flow above, then loads policy from the
API-erhobenen `base_sha` and diff from the local Git object store via ports, never from
head/worktree or evidence JSON. It constructs `GateEvaluationContext` and passes it to the
validator. Valid evidence returns `0`;
missing, stale or contradictory exact-head evidence returns `32` with sanitized reasons. The
bootstrap case with no Basispolicy returns `31` and cannot emit a successful GateResult.
Extend the architecture test so `evidence.py` imports only contracts.
Add the evidence-validator factory to `runtime.toml` and prove registry resolution in RED/GREEN
tests.

- [ ] **Step 4: Run and confirm GREEN**

```bash
python3 -m unittest tests.test_review_routing_evidence \
  tests.test_review_routing_architecture -v
```

- [ ] **Step 5: Commit**

```bash
git add review_routing/contracts.py review_routing/runtime.toml \
  review_routing/evidence.py review_routing/__main__.py \
  tests/test_review_routing_evidence.py tests/test_review_routing_cli.py \
  tests/test_review_routing_architecture.py
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
python3 -m review_routing route \
  --repo OWNER/REPO \
  --pull-request NUMBER --review-mode manual --requester USER \
  --purpose final_exact_head \
  --repo-path /absolute/path/to/checkout \
  --json
python3 -m unittest discover -s tests -v
```

Document required GitHub permissions, context limits, trusted Basispolicy, the one-time
`trusted_base_policy_missing` bootstrap behavior of PR #5, live-positive-test procedure and
Issue #3.

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
  tests.test_review_routing_git \
  tests.test_review_routing_github \
  tests.test_review_routing_cli \
  tests.test_review_routing_evidence \
  tests.test_review_routing_architecture -v
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
