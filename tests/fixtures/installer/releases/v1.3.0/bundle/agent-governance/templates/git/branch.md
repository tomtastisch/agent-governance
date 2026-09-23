# Branch-Template

- Stable ID: `git_branch`
- Kategorie: `git`
- Format: `markdown`
- Registry: [`templates/manifest.toml`](../manifest.toml)

## Verantwortung

Dieser Vertrag standardisiert die Form fachlicher Branchnamen, damit ein Branch ohne zusätzliche
Metadaten seinen Änderungstyp, Geltungsbereich und Kurzthema preisgibt.

## Pflichtfelder

- `<type>`: fachlicher Änderungstyp.
- `<scope>`: fachlicher Geltungsbereich.
- `<short-topic>`: kurzes, fachliches Thema.

## Optionale Felder

Keine. Alle drei Segmente sind Pflicht.

## Form

```text
<type>/<scope>/<short-topic>
```

Alle Segmente sind klein geschrieben, kurz und fachlich. Ein ausdrücklich vorgegebener Branchname
hat Vorrang; ein Agentenname ersetzt weder Typ noch Scope.

## Nicht verantwortlich

- Branch anlegen, umbenennen oder löschen,
- Schutzregeln oder Merge-Policies definieren.
