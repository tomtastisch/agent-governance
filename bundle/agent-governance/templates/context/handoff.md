# Kontextübergabe

- Stable ID: `context_handoff`
- Kategorie: `context`
- Format: `markdown`
- Registry: [`templates/manifest.toml`](../manifest.toml)

## Verantwortung

Dieser Vertrag ist die verbindliche Form der Kontextübergabe und hält Ziel, kanonische SSOT,
exakten Zustand, Entscheidungen, Evidenz, offene Findings und den nächsten sicheren Schritt fest.
Er ist der Sitzungsledger- und Checkpoint-Vertrag nach
[CTX-002](../../modules/context.md#ctx-002--sitzungsledger-und-checkpoints).

## Pflichtfelder

- `Ziel und Scope`, `Kanonische SSOT`, `Exact state`, `Entscheidungen`, `Evidenz`,
  `Offene Findings/Blocker`, `Nächster sicherer Schritt`, `Nicht übernehmen`.

## Optionale Felder

- `Entscheidungen` trennt akzeptierte und supersedierte Entscheidungen;
  `Nicht übernehmen` benennt stale, geheime oder out-of-scope Inhalte.

## Form

```text
Ziel und Scope: <current bounded objective>
Kanonische SSOT: <paths/objects and precedence>
Exact state: <branch, head, PR or artifact identity>
Entscheidungen: <accepted decisions and superseded decisions>
Evidenz: <checks/reviews with result and identity>
Offene Findings/Blocker: <classified list>
Nächster sicherer Schritt: <one actionable continuation>
Nicht übernehmen: <stale, secret or out-of-scope context>
```

## Nicht verantwortlich

- Resume-Bindungs- und Invalidation-Logik (dies leistet die domain-spezifische Resume-Capability),
- Secrets oder Rohchats persistieren.
