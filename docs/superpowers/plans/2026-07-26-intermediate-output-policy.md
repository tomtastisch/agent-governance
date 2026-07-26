# Intermediate Output Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make voluntary intermediate LLM status messages centrally switchable with a TOML boolean
whose repository default is `false`, while preserving mandatory questions, blockers, approvals,
security/error reporting and final results.

**Architecture:** `core/interaction.toml` is the sole machine-readable source. The shared Python
configuration loader validates it fail-closed and exposes it through a read-only CLI command;
Claude/Codex entry templates load the same file before voluntary communication. Core prose defines
the non-suppressible safety and audit invariants exactly once.

**Tech Stack:** TOML, Python 3.11 stdlib `tomllib`, `unittest`, Markdown harness templates.

## Global Constraints

- Repository default is exactly `intermediate_status = false`.
- `false` suppresses only voluntary progress/status prose.
- Questions needed to proceed, blockers, approval requests, security warnings, errors, material
  findings and final `ERGEBNIS` remain mandatory.
- `true` leaves ordinary harness behavior unchanged.
- Higher-priority system/harness output requirements cannot be disabled by repository governance.
- No duplicated default in adapters or templates; they load/reference the TOML SSOT.
- Invalid/missing/non-boolean configuration fails closed to `false` and emits an actionable error
  at a mandatory output boundary.

---

### Task 1: Interaction SSOT, parser and ADR

**Files:**
- Create: `core/interaction.toml`
- Create: `docs/decisions/0004-configurable-intermediate-output.md`
- Modify: `review_routing/contracts.py`
- Modify: `review_routing/adapters/toml_config.py`
- Create: `tests/test_interaction_policy.py`

**Interfaces:**
- Produces immutable `InteractionConfig(intermediate_status: bool)`.
- Produces:
  `ConfigPort.load_interaction(path: Path) -> InteractionConfig`.
- Produces:
  `decide_output(kind: MessageKind, config: InteractionConfig) -> OutputDecision`.

- [ ] **Step 1: Write failing parser/default tests**

```python
config = load_interaction_config(Path("core/interaction.toml"))
self.assertIs(config.intermediate_status, False)
```

Also cover `true`, missing file, missing table/key, string/integer/null-like values, extra unknown
keys and unsupported schema versions. Unknown/malformed inputs must raise `ConfigurationError`;
callers treat that fail-closed.

- [ ] **Step 2: Run and confirm RED**

```bash
python3 -m unittest tests.test_interaction_policy -v
```

- [ ] **Step 3: Add the SSOT and strict parser**

Exact file:

```toml
schema_version = 1

[output]
intermediate_status = false
```

Do not use Python truthiness; require `type(value) is bool`. Put `InteractionConfig`,
`MessageKind` and `OutputDecision` in the single contracts module. The TOML adapter implements
parsing; a pure decision function preserves `QUESTION`, `BLOCKER`, `APPROVAL`, `SECURITY_WARNING`,
`ERROR`, `MATERIAL_FINDING` and `FINAL_RESULT` regardless of the boolean.

- [ ] **Step 4: Run and confirm GREEN**

```bash
python3 -m unittest tests.test_interaction_policy -v
```

- [ ] **Step 5: Commit**

```bash
git add core/interaction.toml docs/decisions/0004-configurable-intermediate-output.md \
  review_routing/contracts.py review_routing/adapters/toml_config.py \
  tests/test_interaction_policy.py
git commit -m "feat(governance): configure intermediate status output"
```

### Task 2: Read-only CLI exposure

**Files:**
- Modify: `review_routing/__main__.py`
- Modify: `tests/test_review_routing_cli.py`

**Interfaces:**
- Produces command:
  `python3 -m review_routing output-policy --json`.
- Success JSON:
  `{"schema_version": 1, "intermediate_status": false}`.

- [ ] **Step 1: Write failing command tests**

Cover default false, explicit true in a temporary config, malformed config and no stdout progress
prose. Malformed input returns exit `31` with sanitized JSON.

- [ ] **Step 2: Run and confirm RED**

```bash
python3 -m unittest \
  tests.test_review_routing_cli.ReviewRoutingCliTest.test_output_policy -v
```

- [ ] **Step 3: Implement the minimal subcommand**

The command only reads the TOML and serializes its validated value. It must not mutate harness
configuration or home-directory files.

- [ ] **Step 4: Run and confirm GREEN**

```bash
python3 -m unittest tests.test_review_routing_cli -v
```

- [ ] **Step 5: Commit**

```bash
git add review_routing/__main__.py tests/test_review_routing_cli.py
git commit -m "feat(governance): expose output policy read only"
```

### Task 3: Core and harness wiring

**Files:**
- Modify: `core/core.md`
- Modify: `adapters/claude.md`
- Modify: `adapters/codex.md`
- Modify: `templates/CLAUDE.md`
- Modify: `templates/AGENTS.md`
- Modify: `templates/README.md`
- Modify: `INSTALL.md`
- Modify: `README.md`
- Modify: `tests/test_governance.py`

**Interfaces:**
- Consumes `core/interaction.toml`.
- Produces entry wiring that reads the value before the first voluntary intermediate message.

- [ ] **Step 1: Write failing drift/wiring tests**

Require:

```python
self.assertIn("@~/agent-governance/core/interaction.toml", TPL_CLAUDE)
self.assertIn("~/agent-governance/core/interaction.toml", TPL_CODEX)
self.assertIn("intermediate_status", CORE)
```

Parse the TOML in tests and verify the default is `False`. Assert adapters/templates do not contain
a second assignment such as `intermediate_status = true|false`. Add capability-table assertions
for Claude, Codex, MCP/other harnesses and ensure only Claude/Codex are described as
promptbasiert/best-effort until their external acceptance cases are run.

- [ ] **Step 2: Run and confirm RED**

```bash
python3 -m unittest tests.test_governance -v
```

- [ ] **Step 3: Wire the central file**

- Claude template imports the TOML in its existing import list.
- Codex template adds it to the mandatory first-read list.
- Core defines suppressible versus non-suppressible message classes.
- Adapters explain only how the harness reads the file and how native status requirements take
  precedence; they do not copy the boolean.
- INSTALL and templates README include the new file in path/readback verification.

- [ ] **Step 4: Run focused tests**

```bash
python3 -m unittest tests.test_interaction_policy tests.test_governance -v
```

- [ ] **Step 5: Commit**

```bash
git add core/core.md adapters templates INSTALL.md README.md tests/test_governance.py
git commit -m "docs(governance): wire central output policy"
```

### Task 4: Acceptance and limitation proof

**Files:**
- Modify only if verification finds a defect.

**Interfaces:**
- No new interface; verifies default, override and fail-closed behavior.

- [ ] **Step 1: Verify the repository default**

```bash
python3 -m review_routing output-policy --json
```

Expected:

```json
{"intermediate_status": false, "schema_version": 1}
```

- [ ] **Step 2: Verify `true` with an isolated temporary config**

Use a temporary file outside the repository, invoke `--config`, and verify
`intermediate_status = true` is returned without changing the repository default.

- [ ] **Step 3: Verify fail-closed malformed input**

Use `intermediate_status = "false"` and expect exit `31`, sanitized error JSON and no normal
progress prose.

- [ ] **Step 4: Verify full regression**

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q review_routing tests
git diff --check origin/main...HEAD
```

- [ ] **Step 5: Record the enforcement boundary**

PR/README must state that schema/default/wiring are mechanically proven, while actual suppression
inside a foreign harness cannot override higher-priority system requirements and must be verified
after installation in that harness. Do not claim impossible universal enforcement.
