import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { access, lstat, mkdir, readFile, symlink, writeFile } from "node:fs/promises";
import { join } from "node:path";
import test from "node:test";

import { InstallerTransaction } from "../../src/transaction.ts";
import { InstallerFailure } from "../../src/errors.ts";
import { InterruptedFailure } from "../../src/errors.ts";
import type { CatchableSignal, SignalSource } from "../../src/signals.ts";
import { createTestRoot } from "../fixtures/installer/workspace.ts";

class TransactionSignals implements SignalSource {
  private readonly listeners = new Map<CatchableSignal, Set<() => void>>();

  on(signal: CatchableSignal, listener: () => void): void {
    const current = this.listeners.get(signal) ?? new Set();
    current.add(listener);
    this.listeners.set(signal, current);
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

async function fixture(): Promise<{ allowed: string; home: string; release: string; install: string }> {
  const allowed = await createTestRoot("agent-governance-transaction-");
  const home = join(allowed, "codex");
  const release = join(allowed, "release");
  const install = join(home, "governance");
  await mkdir(join(release, "bundle", "agent-governance"), { recursive: true });
  await mkdir(home);
  const files: Record<string, string> = {
    VERSION: "0.6.0\n",
    "bundle/GOVERNANCE.md": "canonical governance\n",
    "bundle/agent-governance/manifest.toml": 'schema_version = 2\nlocal_rules = "local/user-rules.md"\n',
  };
  for (const [path, content] of Object.entries(files)) await writeFile(join(release, path), content);
  const inventory = Object.entries(files)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([path, content]) => `${createHash("sha256").update(content).digest("hex")}  ${path}`)
    .join("\n");
  await writeFile(join(release, "release.files.sha256"), `${inventory}\n`);
  return { allowed, home, release, install };
}

test("fresh transaction backs up absences, stages, activates, and verifies", async () => {
  const f = await fixture();
  const transaction = new InstallerTransaction({
    harness: "codex",
    home: f.home,
    allowedRoot: f.allowed,
    releaseRoot: f.release,
    installRoot: f.install,
    dryRun: false,
  });
  const result = await transaction.install();
  assert.equal(result.outcome, "SUCCESS");
  assert.equal(result.state, "FRESH");
  assert.equal(await readFile(join(f.home, "AGENTS.md"), "utf8"), "canonical governance\n");
  assert.match(await readFile(join(f.home, "hooks.json"), "utf8"), /agent_governance__execute/);
  await access(join(f.install, "bundle", "agent-governance", "manifest.toml"));
});

test("dry run returns plan without productive side effects", async () => {
  const f = await fixture();
  const transaction = new InstallerTransaction({
    harness: "codex", home: f.home, allowedRoot: f.allowed, releaseRoot: f.release,
    installRoot: f.install, dryRun: true,
  });
  const result = await transaction.install();
  assert.equal(result.outcome, "SUCCESS");
  await assert.rejects(access(join(f.home, "AGENTS.md")));
  await assert.rejects(access(f.install));
});

test("verification fault rolls back all previously absent targets", async () => {
  const f = await fixture();
  const transaction = new InstallerTransaction({
    harness: "codex", home: f.home, allowedRoot: f.allowed, releaseRoot: f.release,
    installRoot: f.install, dryRun: false, faultAfter: "activate",
  });
  await assert.rejects(transaction.install(), (error: unknown) => {
    assert.equal(error instanceof InstallerFailure, true);
    const failure = error as InstallerFailure;
    assert.equal(failure.outcome, "VERIFICATION_ROLLED_BACK");
    assert.equal(failure.rollbackStatus, "SUCCEEDED");
    assert.equal(failure.phase, "activate");
    return true;
  });
  await assert.rejects(access(join(f.home, "AGENTS.md")));
  await assert.rejects(access(join(f.home, "hooks.json")));
  await assert.rejects(access(f.install));
});

test("second unchanged install is idempotent", async () => {
  const f = await fixture();
  const request = { harness: "codex" as const, home: f.home, allowedRoot: f.allowed,
    releaseRoot: f.release, installRoot: f.install, dryRun: false };
  await new InstallerTransaction(request).install();
  const before = await readFile(join(f.home, "hooks.json"), "utf8");
  const second = await new InstallerTransaction(request).install();
  assert.equal(second.state, "CURRENT");
  assert.equal(await readFile(join(f.home, "hooks.json"), "utf8"), before);
});

test("legacy migration preserves personal rules at manifest path", async () => {
  const f = await fixture();
  const personal = "Always preserve this personal rule.\n";
  await writeFile(
    join(f.home, "AGENTS.md"),
    `@~/agent-governance/adapters/AGENTS.md\n${personal}`,
  );
  const result = await new InstallerTransaction({
    harness: "codex", home: f.home, allowedRoot: f.allowed, releaseRoot: f.release,
    installRoot: f.install, dryRun: false,
  }).install();
  assert.equal(result.state, "LEGACY");
  assert.equal(
    await readFile(join(f.install, "bundle", "agent-governance", "local", "user-rules.md"), "utf8"),
    personal,
  );
});

test("tampered current binding fails closed instead of reporting CURRENT", async () => {
  const f = await fixture();
  const request = { harness: "codex" as const, home: f.home, allowedRoot: f.allowed,
    releaseRoot: f.release, installRoot: f.install, dryRun: false };
  await new InstallerTransaction(request).install();
  await writeFile(join(f.home, "AGENTS.md"), "tampered\n");
  await assert.rejects(new InstallerTransaction(request).install(), /unsafe install state/);
});

test("preexisting symlink backup directory prevents every productive mutation", async () => {
  const f = await fixture();
  const outside = await createTestRoot("agent-governance-outside-");
  await symlink(outside, join(f.allowed, ".agent-governance-backups"));
  const transaction = new InstallerTransaction({
    harness: "codex", home: f.home, allowedRoot: f.allowed, releaseRoot: f.release,
    installRoot: f.install, dryRun: false,
  });
  await assert.rejects(transaction.install(), /symlink/);
  await assert.rejects(access(join(f.home, "AGENTS.md")));
  await assert.rejects(access(f.install));
});

test("preexisting symlink rollback receipt prevents every productive mutation", async () => {
  const f = await fixture();
  const outside = join(await createTestRoot("agent-governance-outside-"), "receipt.json");
  await writeFile(outside, "private\n");
  await symlink(outside, join(f.home, ".agent-governance-rollback.json"));
  const transaction = new InstallerTransaction({
    harness: "codex", home: f.home, allowedRoot: f.allowed, releaseRoot: f.release,
    installRoot: f.install, dryRun: false,
  });
  await assert.rejects(transaction.install(), /symlink|receipt/);
  assert.equal(await readFile(outside, "utf8"), "private\n");
  await assert.rejects(access(join(f.home, "AGENTS.md")));
});

test("rollback dry run never mutates installed resources or receipt", async () => {
  const f = await fixture();
  const base = { harness: "codex" as const, home: f.home, allowedRoot: f.allowed,
    releaseRoot: f.release, installRoot: f.install };
  await new InstallerTransaction({ ...base, dryRun: false }).install();
  const receipt = await readFile(join(f.home, ".agent-governance-rollback.json"));
  const result = await new InstallerTransaction({ ...base, dryRun: true }).rollback();
  assert.equal(result.phase, "plan");
  assert.equal(await readFile(join(f.home, "AGENTS.md"), "utf8"), "canonical governance\n");
  assert.deepEqual(await readFile(join(f.home, ".agent-governance-rollback.json")), receipt);
});

test("rollback validates receipt targets and backup tree before mutation", async () => {
  const f = await fixture();
  const receipt = join(f.home, ".agent-governance-rollback.json");
  await writeFile(receipt, JSON.stringify({
    schemaVersion: 2,
    backupRoot: join(f.allowed, ".agent-governance-backups", "forged"),
    status: "PREPARED",
    resources: [{ target: join(f.allowed, "unrelated"), existed: false, index: 0 }],
  }));
  await assert.rejects(new InstallerTransaction({
    harness: "codex", home: f.home, allowedRoot: f.allowed, releaseRoot: f.release,
    installRoot: f.install, dryRun: false,
  }).rollback(), /receipt resource|backup/);
  assert.equal((await lstat(receipt)).isFile(), true);
});

for (const [signal, exitCode] of [["SIGINT", 130], ["SIGTERM", 143]] as const) {
  test(`${signal} before the first productive mutation exits without active state`, async () => {
    const f = await fixture();
    const signals = new TransactionSignals();
    const transaction = new InstallerTransaction({
      harness: "codex", home: f.home, allowedRoot: f.allowed, releaseRoot: f.release,
      installRoot: f.install, dryRun: false, signalSource: signals,
      onCheckpoint: (checkpoint) => {
        if (checkpoint === "beforeMutation") signals.emit(signal);
      },
    });
    await assert.rejects(transaction.install(), (error: unknown) => {
      assert.equal(error instanceof InterruptedFailure, true);
      assert.equal((error as InterruptedFailure).signal, signal);
      assert.equal((error as InterruptedFailure).exitCode, exitCode);
      assert.equal((error as InterruptedFailure).rollbackStatus, "NOT_REQUIRED");
      return true;
    });
    assert.equal(signals.count(), 0);
    await assert.rejects(access(join(f.home, "AGENTS.md")));
    await assert.rejects(access(join(f.home, ".agent-governance-rollback.json")));
  });
}

for (const checkpoint of ["afterInstructionBinding", "beforeVerification", "afterCommitReceipt"] as const) {
  test(`SIGTERM at ${checkpoint} performs one rollback and persists recovery evidence`, async () => {
    const f = await fixture();
    const signals = new TransactionSignals();
    let emitted = false;
    const transaction = new InstallerTransaction({
      harness: "codex", home: f.home, allowedRoot: f.allowed, releaseRoot: f.release,
      installRoot: f.install, dryRun: false, signalSource: signals,
      onCheckpoint: (current) => {
        if (!emitted && current === checkpoint) {
          emitted = true;
          signals.emit("SIGTERM");
          signals.emit("SIGINT");
        }
      },
    });
    await assert.rejects(transaction.install(), (error: unknown) => {
      assert.equal(error instanceof InterruptedFailure, true);
      assert.equal((error as InterruptedFailure).signal, "SIGTERM");
      assert.equal((error as InterruptedFailure).exitCode, 143);
      assert.equal((error as InterruptedFailure).rollbackStatus, "SUCCEEDED");
      return true;
    });
    assert.equal(signals.count(), 0);
    await assert.rejects(access(join(f.home, "AGENTS.md")));
    await assert.rejects(access(join(f.home, "hooks.json")));
    await assert.rejects(access(f.install));
    const receipt = JSON.parse(await readFile(join(f.home, ".agent-governance-rollback.json"), "utf8")) as {
      schemaVersion: number; status: string;
    };
    assert.deepEqual({ schemaVersion: receipt.schemaVersion, status: receipt.status }, {
      schemaVersion: 2, status: "ROLLED_BACK",
    });
  });
}

test("a signal received during rollback never starts a competing rollback", async () => {
  const f = await fixture();
  const signals = new TransactionSignals();
  let rollbackCheckpoints = 0;
  const transaction = new InstallerTransaction({
    harness: "codex", home: f.home, allowedRoot: f.allowed, releaseRoot: f.release,
    installRoot: f.install, dryRun: false, signalSource: signals, faultAfter: "activate",
    onCheckpoint: (checkpoint) => {
      if (checkpoint === "duringRollback") {
        rollbackCheckpoints += 1;
        signals.emit("SIGINT");
        signals.emit("SIGTERM");
      }
    },
  });
  await assert.rejects(transaction.install(), (error: unknown) => {
    assert.equal(error instanceof InstallerFailure, true);
    assert.equal((error as InstallerFailure).outcome, "VERIFICATION_ROLLED_BACK");
    return true;
  });
  assert.equal(rollbackCheckpoints, 1);
  assert.equal(signals.count(), 0);
});

test("rollback failure after a signal leaves PREPARED receipt for later idempotent recovery", async () => {
  const f = await fixture();
  const signals = new TransactionSignals();
  let emitted = false;
  const base = {
    harness: "codex" as const, home: f.home, allowedRoot: f.allowed, releaseRoot: f.release,
    installRoot: f.install, dryRun: false,
  };
  await assert.rejects(new InstallerTransaction({
    ...base, signalSource: signals, faultDuringRollback: true,
    onCheckpoint: (checkpoint) => {
      if (!emitted && checkpoint === "afterInstructionBinding") {
        emitted = true;
        signals.emit("SIGINT");
      }
    },
  }).install(), (error: unknown) => {
    assert.equal(error instanceof InstallerFailure, true);
    assert.equal((error as InstallerFailure).outcome, "ROLLBACK_FAILED");
    assert.equal((error as InstallerFailure).rollbackStatus, "FAILED");
    return true;
  });
  const prepared = JSON.parse(await readFile(join(f.home, ".agent-governance-rollback.json"), "utf8")) as {
    status: string;
  };
  assert.equal(prepared.status, "PREPARED");
  assert.equal((await new InstallerTransaction(base).rollback()).rollbackStatus, "SUCCEEDED");
  assert.equal((await new InstallerTransaction(base).rollback()).rollbackStatus, "SUCCEEDED");
  assert.equal((await new InstallerTransaction(base).install()).outcome, "SUCCESS");
});

test("rollback receipt rejects duplicate resources and unknown fields", async () => {
  const f = await fixture();
  const backupRoot = join(f.allowed, ".agent-governance-backups", "forged");
  await mkdir(backupRoot, { recursive: true });
  const resources = [0, 0, 2].map((index) => ({
    target: index === 0 ? join(f.home, "AGENTS.md") : f.install,
    existed: false,
    index,
  }));
  await writeFile(join(f.home, ".agent-governance-rollback.json"), JSON.stringify({
    schemaVersion: 2, backupRoot, status: "PREPARED", resources, injected: true,
  }));
  await assert.rejects(new InstallerTransaction({
    harness: "codex", home: f.home, allowedRoot: f.allowed, releaseRoot: f.release,
    installRoot: f.install, dryRun: false,
  }).rollback(), /unknown field|resource index/);
});
