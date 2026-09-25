import { ResumeCheckpointStore } from "../../../src/resume-checkpoint.ts";
import { state } from "./state.ts";

const store = await ResumeCheckpointStore.open(process.argv[2]!);
const stage = process.argv[3]!;
const current = await store.read();
process.send?.("ready");
await new Promise<void>((resolve) => process.once("message", () => resolve()));
try {
  await store.materialize({ eventId: process.argv[4]!, trigger: "task_started", expected: current, state: { ...state(), activeTask: process.argv[4]! } }, (point) => {
    if (point === stage) process.kill(process.pid, "SIGKILL");
  });
  process.exit(0);
} catch { process.exit(2); }
