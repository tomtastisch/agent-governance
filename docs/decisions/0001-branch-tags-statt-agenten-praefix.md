# ADR 0001 — Branch-/PR-Tag nach Änderungstyp statt Agenten-Präfix

Status: akzeptiert · Datum: 2026-07-25

## Kontext

Branches und PRs trugen bisher einen Präfix, der den erzeugenden Agenten benannte: `claude/…`
bzw. `codex/…`. Realisiert war das als harness-spezifischer Port `vcs.branch_prefix` (je Adapter
ein anderer Wert), deklariert im Port-Vertrag und vom Branch-Schema in Kern §15 referenziert.

Dieser Präfix kodierte Identität („wer hat gearbeitet"), nicht Inhalt („was wurde geändert"). Die
Identität ist jedoch redundant: Autor und Committer stehen ohnehin in den Commit-Metadaten. Wir
behandeln eine LLM wie eine Mitarbeiterin — beurteilt wird die fachliche Arbeit, nicht die Herkunft
am Branchnamen. Damit verschenkte der Branchname seinen Informationswert an eine Angabe, die an
anderer Stelle bereits verlässlich vorliegt.

## Entscheidung

Der Präfix benennt künftig die fachliche **Art** der Änderung, nicht den Agenten. Branch-Schema:
`<tag>/<modul>/<thema>/<name>`.

- `<tag>` stammt aus einer zentralen, harness-agnostischen Quelle: `core/branch-tags.toml`
  (SSOT). Jeder Eintrag trägt `tag`, `name` und `description`.
- Die Tag-Liste ist eine **geschlossene Enumeration** und entspricht den Conventional-Commit-Typen
  (`feat`, `fix`, `docs`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`) — eine Vokabelmenge
  für Branch, PR-Titel und Commit-Präfix.
- Die Zuordnung Arbeit→Tag erfolgt fachlich anhand des `description`-Kriteriums; bei gemischten
  Änderungen gewinnt der dominante Typ. Ist kein Tag eindeutig, gilt der `default` der Datei; bei
  echter Unentscheidbarkeit greift Kern §7 (Blocker/Rückfrage).
- Die Herkunft (Claude/Codex) entfällt aus dem Branchnamen ganz und bleibt über die
  Commit-Metadaten erhalten.

Folge für die Struktur: `vcs.branch_prefix` unterscheidet sich zwischen den Harnessen nicht mehr
und ist damit **kein Port mehr**. Er wurde aus Port-Vertrag (README) und beiden Adaptern entfernt.
Der Tag ist ein Kern-Datenartefakt, das Kern §15 direkt referenziert — der Achsenwechsel
*verkleinert* den Port-Vertrag, statt ihn zu erweitern.

## Begründung

- Aussagekräftiger Branchname: der Präfix trägt jetzt fachliche Information statt redundanter
  Identität.
- SSOT und Drift-Freiheit (Kern §9): eine zentrale, von Entwicklern gepflegte Datei legt die
  gültigen Tags fest; `tests/test_governance.py` erzwingt Eindeutigkeit, ref-sicheren Zeichensatz,
  vollständige Felder, gültigen `default` und den Kern-Verweis — mechanisch geprüft, nicht nur
  Konvention.
- Eine Taxonomie statt zweier: Branch, PR und Commit teilen dieselben Typen; keine divergierenden
  Vokabulare als neue Drift-Quelle.
- Fail-closed: geschlossene Liste plus definierter `default` und §7-Rückfall — kein frei erfundener
  Tag, kein stiller Fehlgriff.
- Kleinere Verdrahtung: ein harness-spezifischer Port weniger.

## Konsequenzen

- Kern §15 (Branch-Schema) und die Dauerfreigabe in §7 verweisen nicht mehr auf
  `[BINDING:vcs.branch_prefix]`, sondern auf das Schema bzw. die Tag-Datei.
- Neue Änderungstypen werden zentral in `core/branch-tags.toml` ergänzt (`[[tags]]`-Eintrag) — nicht
  mehr pro Harness.
- Parallele Agenten teilen sich denselben Tag-Raum; Eindeutigkeit stellen `<thema>/<name>` sicher,
  nicht mehr ein Agenten-Namensraum.
- Bestehende `claude/…`- oder `codex/…`-Branches bleiben gültig, bis sie gemergt/geschlossen sind;
  neue Branches folgen dem Tag-Schema.

## Alternativen (verworfen)

- Agenten-Identität als Sub-Namensraum behalten (`<tag>/<harness>/…`): hält die redundante Identität
  am Namen und erhält den Port teilweise — Aufwand ohne Mehrwert, da die Herkunft in den Metadaten
  steht.
- Freie, projektspezifische Tag-Liste statt Conventional-Commit-Typen: brächte eine zweite
  Taxonomie neben den bereits genutzten Commit-Typen und damit eine neue Drift-Quelle.
