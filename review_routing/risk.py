"""Reine maximale Risikoklassifikation aus Policy und geschlossenem Diff-Snapshot."""
from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
from typing import Mapping

from review_routing.contracts import (
    AdapterFactory,
    DiffSnapshot,
    RiskAssessment,
    RiskClassifierPort,
    RiskLevel,
    RoutingConfig,
)


_LEVEL_RANK = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.CRITICAL: 3,
}


def _maximum(left: RiskLevel, right: RiskLevel) -> RiskLevel:
    return left if _LEVEL_RANK[left] >= _LEVEL_RANK[right] else right


def _size_level(snapshot: DiffSnapshot, config: RoutingConfig) -> tuple[RiskLevel, str | None]:
    changed_lines = sum(file.additions + file.deletions for file in snapshot.files)
    for level in (RiskLevel.CRITICAL, RiskLevel.HIGH, RiskLevel.MEDIUM):
        threshold = config.thresholds[level.value]
        if changed_lines >= threshold:
            return level, f"size_threshold:{level.value}:{threshold}"
    return RiskLevel.LOW, None


def assess_risk(changes: DiffSnapshot, config: RoutingConfig) -> RiskAssessment:
    """Bildet das Maximum aller autoritativen Signale und erhält Evidenzgründe sortiert."""
    if not changes.files:
        reasons = {"incomplete_diff_metadata"}
        reasons.update(f"evidence:{reason}" for reason in changes.risk_reasons)
        if changes.security_relevant is True:
            reasons.add("explicit_security_relevant")
        return RiskAssessment(
            RiskLevel.CRITICAL,
            changes.security_relevant is True,
            tuple(sorted(reasons)),
        )

    level, size_reason = _size_level(changes, config)
    reasons = {f"evidence:{reason}" for reason in changes.risk_reasons}
    if size_reason is not None:
        reasons.add(size_reason)
    security_relevant = changes.security_relevant is True
    if security_relevant:
        reasons.add("explicit_security_relevant")

    for file in changes.files:
        paths = (file.path,) if file.previous_path is None else (file.path, file.previous_path)
        for path in paths:
            for marker in config.path_markers:
                if not fnmatchcase(path, marker.glob):
                    continue
                marker_level = RiskLevel(marker.level)
                level = _maximum(level, marker_level)
                reasons.add(f"{marker_level.value}_path:{path}")
                security_relevant = security_relevant or marker.security_relevant

    if changes.explicit_risk is not None:
        level = _maximum(level, changes.explicit_risk)
        reasons.add(f"explicit_risk:{changes.explicit_risk.value}")

    return RiskAssessment(level, security_relevant, tuple(sorted(reasons)))


class RiskClassifier(RiskClassifierPort):
    """Port-Adapter für die reine Risikofunktion."""

    def assess(self, snapshot: DiffSnapshot, config: RoutingConfig) -> RiskAssessment:
        return assess_risk(snapshot, config)


@dataclass(frozen=True)
class RiskClassifierFactory:
    provided_ports = (RiskClassifierPort,)
    required_ports: tuple[type[object], ...] = ()

    def build(self, dependencies: Mapping[type[object], object]) -> Mapping[type[object], object]:
        if dependencies:
            raise ValueError("risk classifier expects no dependencies")
        return {RiskClassifierPort: RiskClassifier()}


def factory() -> AdapterFactory:
    """Meldet die reine Risikoklassifikation an der Runtime-Registry an."""
    return RiskClassifierFactory()
