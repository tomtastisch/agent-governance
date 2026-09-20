# Release-Checkpoint

- Stable ID: `delivery_release_checkpoint`
- Kategorie: `delivery`
- Format: `markdown`
- Registry: [`templates/manifest.toml`](../manifest.toml)

## Verantwortung

Dieser Vertrag standardisiert ausschließlich die Form des Release-Nachweises: Ziel, exakter Stand,
Version, Tag, Artefaktidentität, Prüf- und Publizierzustand sowie die autorisierte nächste Aktion.
Er implementiert keine Releaseengine.

## Pflichtfelder

- `Release target`, `Exact Head`, `Version`, `Tag`, `Tag identity/signature`,
  `Required CI`, `Package artifact identity`, `Publish result`, `Registry read-back`,
  `Release object/read-back`, `Open findings`, `Authorized next action`.

## Optionale Felder

- `Tag identity/signature` und `Registry read-back` dürfen `pending` sein, wenn der Nachweis noch
  aussteht; leere Findings werden als `none` benannt.

## Form

```text
Release target: <repository and artifact>
Exact Head: <Exact-Head-SHA>
Version: <semver>
Tag: <tag-name>
Tag identity/signature: <tag-identity or signature-reference>
Required CI: <required check-id> = <result>
Package artifact identity: <artifact-id or digest>
Publish result: <published|pending|failed>
Registry read-back: <registry-object or read-back-reference>
Release object/read-back: <release-object or read-back-reference>
Open findings: <none or classified list>
Authorized next action: <one authorized continuation>
```

## Nicht verantwortlich

- Version berechnen,
- Tag erzeugen oder signieren,
- Package bauen oder veröffentlichen,
- Release freigeben oder mergen.
