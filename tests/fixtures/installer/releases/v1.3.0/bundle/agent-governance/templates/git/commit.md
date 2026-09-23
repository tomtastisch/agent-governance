# Commit-Template

- Stable ID: `git_commit`
- Kategorie: `git`
- Format: `markdown`
- Registry: [`templates/manifest.toml`](../manifest.toml)

## Verantwortung

Dieser Vertrag standardisiert die atomare Commitform, damit eine einzelne fachlich kohärente
Änderung eine stabile, maschinell prüfbare Zusammenfassung erhält. Er beschreibt ausschließlich
die Form des Commit, nicht die Historie- oder Signaturregeln (siehe
[DEL-004](../../modules/delivery.md#del-004--atomare-historie)).

## Pflichtfelder

- `<type>`: fachlicher Änderungstyp (`feat`, `fix`, `refactor`, `docs`, `test`, `chore`).
- `<scope>`: fachlicher Geltungsbereich.
- `<imperative summary>`: imperative Zusammenfassung.

## Optionale Felder

- `<body>`: erklärender Rumpf mit Kontext, Breaking-/Security-Auswirkung oder nicht offensichtlicher
  Entscheidung. Er entfällt, wenn der Header die atomare Änderung bereits vollständig erklärt.

## Form

```text
<type>(<scope>): <imperative summary>

<optional body: context, breaking/security impact, non-obvious decision>
```

Eine Agentenmarke ist kein Änderungstyp.

## Nicht verantwortlich

- Commit-Historie umschreiben,
- Signatur-/Signieranforderungen prüfen,
- atomare Änderungsgrenzen durchsetzen (dies leistet [DEL-004](../../modules/delivery.md#del-004--atomare-historie)).
