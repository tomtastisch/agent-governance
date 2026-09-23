"""Einmaliger Old-vs-New-Testvergleich für #94; kein Runtime-Router.

Aufruf: python3 -m tests.support.routing_shadow [--baseline-bundle /absolut/bundle]
Die optionale Basis wird erneut mit demselben Messadapter gemessen. Ohne Argument
dient die vor der Änderung erfasste, an Git gebundene Baseline als Vergleich.
"""

import argparse
import json
from pathlib import Path
import subprocess

from tests.support.routing_measurement import measure_route
from tests.test_routing_performance import (
    BASELINE, BUNDLE, CORPUS, KERNEL, LOCAL, PROMOTION, SECURITY, loaded_rules, semantic_text,
)


class ShadowBaselineError(RuntimeError):
    """Fail-closed: die aufgezeichnete Baseline lässt sich nicht an den vorgesehenen Git-Stand binden."""


def verify_baseline_git_binding(baseline_head: str, head: str = "HEAD") -> None:
    """Schlägt fehl, wenn die aufgezeichnete Baseline-SHA kein echter Vorfahre von head ist.

    Eine veraltete oder editierte Baseline darf keinen Vergleich mit Exit 0 erzeugen.
    """
    try:
        subprocess.run(
            ["git", "cat-file", "-e", f"{baseline_head}^{{commit}}"],
            check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError as error:
        raise ShadowBaselineError(f"baseline head is not a valid commit: {baseline_head}") from error
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", baseline_head, head], capture_output=True
    )
    if result.returncode != 0:
        raise ShadowBaselineError(
            f"baseline head {baseline_head} is not an ancestor of {head}; baseline is stale or edited"
        )


def unexplained_semantic_changes(changed, current_rules, expected_changes):
    """Geänderte Regeln sind nur erklärt, wenn sie dem ausdrücklich erwarteten Nach-Änderungs-Vertrag entsprechen.

    Eine weitere inhaltliche Abweichung — auch an GOV-006 oder TOL-004 — ist ungeklärt.
    """
    unexplained = []
    for rule in changed:
        if rule in expected_changes:
            if semantic_text(current_rules[rule]) != semantic_text(expected_changes[rule]):
                unexplained.append(rule)
        else:
            unexplained.append(rule)
    return sorted(unexplained)


def compare_route(name, old, new, rules):
    old_rules = {rule for rule, value in BASELINE["rules"].items() if value["path"] in old["files"]}
    removed_rules = old_rules - rules.keys()
    required = set(KERNEL)
    triggers = set(new["triggers"])
    if triggers & {"implementation", "refactoring", "testing", "documentation"}:
        required |= LOCAL
    if triggers & {"security_sensitive_change", "security_review", "external_effect", "role_security_review"}:
        required |= SECURITY | LOCAL | PROMOTION
    if triggers & {"quality_review", "release", "role_quality_assurance", "role_architecture", "resume_continuation"}:
        required |= LOCAL | PROMOTION
    if "external_effect" in triggers:
        required |= {f"ENF-{i:03}" for i in range(1, 6)}
    # Nur die im Issue explizit untersuchten unnötigen Security-/Delivery-Regeln
    # dürfen entfallen. Erforderliche Regeln sind unabhängig davon verboten.
    permitted = (SECURITY | PROMOTION | {"DEL-001", "DEL-002", "DEL-004", "DEL-006"}) - required
    unexplained = sorted(removed_rules - permitted)
    missing = sorted(required - rules.keys())
    changed = sorted(rule for rule in old_rules & rules.keys()
                     if semantic_text(rules[rule]) != semantic_text(BASELINE["rules"][rule]["text"]))
    unexplained_changes = unexplained_semantic_changes(
        changed, rules, BASELINE.get("expected_changes", {})
    )
    reasons = {}
    for module in set(old["modules"]) - set(new["modules"]):
        if module == "modules/security.md" and not (required & SECURITY):
            reasons[module] = "Kein Security-/External-Effect-Trigger; GOV-006 bleibt aktiv."
        elif module == "modules/delivery.md" and not (required & PROMOTION):
            reasons[module] = "Keine Lieferentscheidung; lokale DEL-Regeln bleiben bei lokalem Auftrag geladen."
        else:
            reasons[module] = "UNGEKLAERT"
            unexplained.append(module)
    return {
        "case": name,
        "old_triggers": old["triggers"], "new_triggers": new["triggers"],
        "old_modules": old["modules"], "new_modules": new["modules"],
        "removed_modules": sorted(set(old["modules"]) - set(new["modules"])),
        "added_modules": sorted(set(new["modules"]) - set(old["modules"])),
        "removal_reasons": reasons,
        "removed_rules": sorted(removed_rules), "changed_rules": changed,
        "security_relevant_divergence": sorted((SECURITY | KERNEL) & (set(missing) | set(unexplained_changes))),
        "required_gate_divergence": sorted((LOCAL | PROMOTION) & (set(missing) | set(unexplained_changes))),
        "unexplained_divergence": sorted(set(unexplained) | set(missing) | set(unexplained_changes)),
        "old_files": old["file_count"], "new_files": new["file_count"],
        "old_bytes": old["bytes"], "new_bytes": new["bytes"],
        "byte_delta": new["bytes"] - old["bytes"],
        "old_median_ms": old["median_ms"], "new_median_ms": new["median_ms"],
        "old_tool_calls": old["tool_calls"], "new_tool_calls": new["tool_calls"],
        "old_model_cycles": old["model_cycles"], "new_model_cycles": new["model_cycles"],
        "measurement": new,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-bundle", type=Path)
    args = parser.parse_args()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    verify_baseline_git_binding(BASELINE["head"], head)
    rows = []
    for name, triggers in CORPUS.items():
        old = BASELINE["cases"][name]
        if args.baseline_bundle:
            repeated = measure_route(args.baseline_bundle, triggers)
            for key in ("triggers", "modules", "roles", "files", "bytes", "read_calls"):
                if repeated[key] != old[key]:
                    raise ValueError(f"Baseline-Drift: {name}/{key}")
            old = repeated
        new = measure_route(BUNDLE, triggers)
        rows.append(compare_route(name, old, new, loaded_rules(BUNDLE, new)))
    print(json.dumps({"baseline_head": BASELINE["head"],
                      "head": head,
                      "dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], text=True)),
                      "cases": rows}, ensure_ascii=False, indent=2))
    return int(any(row["unexplained_divergence"] for row in rows))


if __name__ == "__main__":
    raise SystemExit(main())
