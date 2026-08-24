import { mkdtemp, realpath } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

export async function createTestRoot(prefix: string): Promise<string> {
  const canonicalTemporaryRoot = await realpath(tmpdir());
  return mkdtemp(join(canonicalTemporaryRoot, prefix));
}
