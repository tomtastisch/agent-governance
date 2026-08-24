import assert from "node:assert/strict";
import test from "node:test";

import {
  SignalCoordinator,
  SignalInterruption,
  type CatchableSignal,
  type SignalSource,
} from "../../src/signals.ts";

class FakeSignals implements SignalSource {
  readonly listeners = new Map<CatchableSignal, Set<() => void>>();

  on(signal: CatchableSignal, listener: () => void): void {
    const listeners = this.listeners.get(signal) ?? new Set();
    listeners.add(listener);
    this.listeners.set(signal, listeners);
  }

  off(signal: CatchableSignal, listener: () => void): void {
    this.listeners.get(signal)?.delete(listener);
  }

  emit(signal: CatchableSignal): void {
    for (const listener of this.listeners.get(signal) ?? []) listener();
  }

  count(): number {
    return [...this.listeners.values()].reduce((total, listeners) => total + listeners.size, 0);
  }
}

test("signal coordinator latches the first signal without running asynchronous work", () => {
  const source = new FakeSignals();
  const coordinator = new SignalCoordinator(source);
  coordinator.start();
  source.emit("SIGTERM");
  source.emit("SIGINT");
  assert.throws(() => coordinator.checkpoint("activate"), (error: unknown) => {
    assert.equal(error instanceof SignalInterruption, true);
    assert.equal((error as SignalInterruption).signal, "SIGTERM");
    assert.equal((error as SignalInterruption).phase, "activate");
    return true;
  });
});

test("signal coordinator installs exactly two listeners and always removes them", () => {
  const source = new FakeSignals();
  const first = new SignalCoordinator(source);
  first.start();
  first.start();
  assert.equal(source.count(), 2);
  first.dispose();
  first.dispose();
  assert.equal(source.count(), 0);

  const second = new SignalCoordinator(source);
  second.start();
  assert.equal(source.count(), 2);
  second.dispose();
  assert.equal(source.count(), 0);
});
