# Templates und Interaktionsverträge

### TPL-001 — Auswahlprinzip

Eine strikte Vorlage ist nur für wiederkehrende Vorgänge verbindlich, bei denen freie Form
Identität, Evidenz oder Übergabeinformation regelmäßig verliert. Alle anderen Interaktionen
folgen einem strukturierten Mindestvertrag. Semantische Regeln bleiben in ihren Fachmodulen;
die atomaren Template-Dateien unter `templates/` sind — registriert über
[`templates/manifest.toml`](../templates/manifest.toml) — die alleinige SSOT für Form und
Pflichtfelder.

## Kanonische Registry

Genau eine geschlossene Registry registriert jeden wiederverwendbaren generischen Formvertrag
genau einmal: [`templates/manifest.toml`](../templates/manifest.toml). Jeder Eintrag trägt eine
stabile Template-ID, einen relativen Pfad, eine semantische Kategorie und ein Format. Konsumenten
lösen Templates bevorzugt über die stabile ID auf, nicht über den Dateipfad.

## Kategorien und atomare Templates

### git

- [`git_commit`](../templates/git/commit.md) — atomare Commitform
- [`git_branch`](../templates/git/branch.md) — Branchnamenform

### delivery

- [`delivery_push_pr_checkpoint`](../templates/delivery/push-pr-checkpoint.md) — Push-/PR-Checkpoint
- [`delivery_pull_request`](../templates/delivery/pull-request.md) — PR-Beschreibung und Reviewevidenz
- [`delivery_release_checkpoint`](../templates/delivery/release-checkpoint.md) — Release-Nachweisform

### review

- [`review_finding`](../templates/review/finding.md) — generisches QA-/SEC-/ARCH-Finding

### context

- [`context_handoff`](../templates/context/handoff.md) — Kontextübergabe

### communication

- [`communication_status`](../templates/communication/status.md) — Antwort und Status
- [`communication_tool_error_blocker`](../templates/communication/tool-error-blocker.md) — Toolfehler und Blocker
- [`communication_completion`](../templates/communication/completion.md) — Abschlussaussage

### external_effects

- [`external_effects_approval_checkpoint`](../templates/external-effects/approval-checkpoint.md) — Freigabe-/Autorisierungscheckpoint

## Domain-spezifische Templates

Domain-spezifische Formverträge gehören ihren Fachdomains und sind nicht Teil der generischen
Registry. Der domain-spezifische Resume-Checkpoint liegt im
[Resume-Modul](resume.md#resume-checkpoint).
