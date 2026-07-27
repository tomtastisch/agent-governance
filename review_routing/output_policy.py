"""Reine Entscheidung für zentral klassifizierte LLM-Ausgaben."""
from __future__ import annotations

from typing import Mapping

from review_routing.contracts import (
    AdapterFactory,
    InteractionConfig,
    MessageKind,
    OutputDecision,
    OutputPolicyPort,
)


def decide_output(kind: MessageKind, config: InteractionConfig) -> OutputDecision:
    """Unterdrückt ausschließlich freiwillige Zwischenstände bei deaktivierter Ausgabe."""
    if not isinstance(kind, MessageKind):
        raise ValueError("kind must be a MessageKind")
    if not isinstance(config, InteractionConfig):
        raise ValueError("config must be an InteractionConfig")
    emit = (
        config.intermediate_status
        if kind is MessageKind.VOLUNTARY_INTERMEDIATE
        else True
    )
    return OutputDecision(kind=kind, emit=emit)


class OutputPolicy(OutputPolicyPort):
    """Port-Implementierung der reinen Ausgabentscheidung."""

    def decide(
        self,
        kind: MessageKind,
        config: InteractionConfig,
    ) -> OutputDecision:
        return decide_output(kind, config)


class OutputPolicyFactory:
    provided_ports = (OutputPolicyPort,)
    required_ports: tuple[type[object], ...] = ()

    def build(
        self,
        dependencies: Mapping[type[object], object],
    ) -> Mapping[type[object], object]:
        if dependencies:
            raise ValueError("Die Ausgabepolicy erwartet keine Abhängigkeiten")
        return {OutputPolicyPort: OutputPolicy()}


def factory() -> AdapterFactory:
    """Meldet die reine Ausgabepolicy an der Runtime-Registry an."""
    return OutputPolicyFactory()
