import { appendFile, readFile } from "node:fs/promises";
import { ResumeCheckpointStore } from "../../../src/resume-checkpoint.ts";

const store = await ResumeCheckpointStore.open(process.argv[2]!);
const target = process.argv[3]!;
const stage = process.argv[4]!;
const cp = (await store.read())!;
process.send?.("ready");
await new Promise<void>(resolve => process.once("message", () => resolve()));
await store.executeEffect(cp, "op-1", async () => {
  if (stage === "beforeEffect") process.kill(process.pid, "SIGKILL");
  await appendFile(target, "effect\n");
  if (stage === "afterEffect") process.kill(process.pid, "SIGKILL");
}, async operation => {
  await readFile(target);
  if (stage === "afterReadback") process.kill(process.pid, "SIGKILL");
  return { operationId: operation.operationId, target: operation.target, action: operation.action, inputBindings: operation.inputBindings, outcome: "APPLIED", reference: "fixture:effect-readback" };
});
process.exit(0);
