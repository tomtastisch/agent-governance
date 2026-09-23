"""Read-only Messadapter des bestehenden NeutralHarness, keine Routing-Authority."""

from __future__ import annotations

from pathlib import Path
import statistics
import time
from unittest.mock import patch

from tests.support.catalog_validator import load_catalog_contract
from tests.support.neutral_harness import NeutralHarness


def measure_route(bundle: Path, triggers: list[str], repetitions: int = 5) -> dict:
    """Misst echte Inhaltsreads; Pfadvalidierung ist kein geladener Instruktionstext.

    Die semantische Klassifikation ist ein expliziter Testinput. Dieser Adapter
    klassifiziert keine Sprache und entscheidet weder Autorisierung noch Gates.
    Private lokale Nutzerregeln werden nie gelesen oder vermessen.
    """
    bundle = bundle.resolve(strict=True)
    if repetitions < 1:
        raise ValueError("Mindestens eine Messung ist erforderlich")
    elapsed = []
    original_open = Path.open
    for _ in range(repetitions):
        reads = []

        class RecordedFile:
            def __init__(self, path, stream):
                self.path, self.stream = path, stream

            def __enter__(self):
                self.stream.__enter__()
                return self

            def __exit__(self, *args):
                return self.stream.__exit__(*args)

            def read(self, *args):
                value = self.stream.read(*args)
                size = len(value.encode("utf-8")) if isinstance(value, str) else len(value)
                reads.append((self.path.relative_to(bundle).as_posix(), size))
                return value

        def record_open(path, *args, **kwargs):
            return RecordedFile(path, original_open(path, *args, **kwargs))

        started = time.perf_counter_ns()
        with patch.object(Path, "open", record_open):
            (bundle / "GOVERNANCE.md").read_bytes()
            contract = load_catalog_contract(bundle / "agent-governance")
            # _resolve_routes benötigt nur manifest_dir. Kein Provider, Effekt,
            # lokaler Zustand oder alternativer Graphalgorithmus wird angelegt.
            harness = object.__new__(NeutralHarness)
            harness.manifest_dir = bundle / "agent-governance"
            modules, roles, paths = harness._resolve_routes(contract.manifest, contract.triggers, triggers)
            for path in paths:
                path.read_bytes()
        elapsed.append((time.perf_counter_ns() - started) / 1_000_000)
    files = dict(reads)
    return {
        "triggers": list(triggers),
        "modules": list(modules),
        "roles": list(roles),
        "files": files,
        "file_count": len(files),
        "bytes": sum(files.values()),
        "read_calls": len(reads),
        "read_bytes": sum(size for _, size in reads),
        "median_ms": statistics.median(elapsed),
        "repetitions": repetitions,
        "tool_calls": 0,
        "model_cycles": 0,
        "tokens": None,
    }
