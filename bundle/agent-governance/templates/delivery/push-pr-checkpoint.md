# Push-/PR-Checkpoint

- Stable ID: `delivery_push_pr_checkpoint`
- Kategorie: `delivery`
- Format: `markdown`
- Registry: [`templates/manifest.toml`](../manifest.toml)

## Verantwortung

Dieser Vertrag hält den Liefer- und Reviewzustand eines Push-/PR-Schritts als einen exakten,
überprüfbaren Checkpoint fest. Er erzwingt die Gleichheit der drei relevanten SHAs, bevor eine
Exact-Head-Aussage zulässig ist (siehe [DEL-002](../../modules/verification.md#del-002--exakter-stand)).

## Pflichtfelder

- `Branch`, `Local HEAD`, `Remote branch HEAD`, `PR`, `PR head`, `Checks`,
  `Review role`, `Review provider`, `Review reference`, `Review Exact Head`, `Review result`,
  `Open findings`.

## Optionale Felder

Keine zusätzlichen Felder; leere Prüfstände werden als `pending` oder `none` benannt.

## Form

```text
Branch: <branch>
Local HEAD: <Exact-Head-SHA>
Remote branch HEAD: <Exact-Head-SHA>
PR: <repository>#<number> -> <base>
PR head: <Exact-Head-SHA>
Checks: <command-or-check-id> = <result>
Review role: <QA|SEC|ARCH>
Review provider: <provider>
Review reference: <review-id-or-object>
Review Exact Head: <Exact-Head-SHA>
Review result: <state>
Open findings: <count and classifications>
```

Die drei SHAs müssen vor einer Exact-Head-Aussage gleich sein.

## Nicht verantwortlich

- Push-, PR- oder Merge-Ausführung,
- Review durchführen oder Findings klassifizieren (dies leistet
  [DEL-009](../../modules/delivery.md#del-009--finding-lifecycle)).
