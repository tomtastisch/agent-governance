# External-Effect-Approval-Checkpoint

- Stable ID: `external_effects_approval_checkpoint`
- Kategorie: `external_effects`
- Format: `markdown`
- Registry: [`templates/manifest.toml`](../manifest.toml)

## Verantwortung

Dieser Vertrag dokumentiert die Form einer bestehenden oder einzuholenden Freigabe für eine
externe Wirkung. Er erzeugt keine Autorisierung; er hält ausschließlich die bereits vorhandene
beziehungsweise erforderliche Autorisierungsgrenze nach
[GOV-003](../../GOVERNANCE.md#gov-003--externe-wirkung) fest.

## Pflichtfelder

- `Requested effect`, `Target`, `Expected mutation`, `Authority/source of approval`,
  `Authorized scope`, `Explicit exclusions`, `Precondition evidence`,
  `Rollback/recovery relevance`, `Read-back requirement`.

## Optionale Felder

- `Explicit exclusions` darf `none` sein; `Rollback/recovery relevance` darf `none` sein, wenn
  keine Rückgängigmachung vorgesehen ist.

## Form

```text
Requested effect: <effect>
Target: <target>
Expected mutation: <mutation>
Authority/source of approval: <authority-or-source>
Authorized scope: <scope>
Explicit exclusions: <none or precise exclusions>
Precondition evidence: <evidence>
Rollback/recovery relevance: <none or precise relevance>
Read-back requirement: <required read-back>
```

## Nicht verantwortlich

- Autorisierung erzeugen,
- Berechtigung prüfen,
- die externe Mutation ausführen.
