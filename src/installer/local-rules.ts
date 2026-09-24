import { constants } from "node:fs";
import { lstat, open, realpath } from "node:fs/promises";
import { isAbsolute } from "node:path";
import { sameFileIdentity, sameFileSnapshot } from "./mutation.ts";

export interface LocalRulesMutation { readonly targetPath: string; readonly source: Buffer; readonly previous?: Buffer; }

function validateLocalRules(content: Buffer): void { let text: string; try { text = new TextDecoder("utf-8", { fatal: true }).decode(content); } catch { throw new Error("local rules contain invalid UTF-8 encoding"); } if (/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/.test(text)) throw new Error("local rules contain a raw control character"); }

export async function readCanonicalLocalRules(path: string, onOpen?: () => void): Promise<Buffer> { if (!isAbsolute(path) || !/\.md$/i.test(path)) throw new Error("local rules must be an absolute canonical Markdown file"); const before = await lstat(path, { bigint: true }); if (before.isSymbolicLink() || !before.isFile() || await realpath(path) !== path) throw new Error("local rules must be an absolute canonical regular non-symlink file"); const handle = await open(path, constants.O_RDONLY | constants.O_NOFOLLOW); try { const opened = await handle.stat({ bigint: true }); if (!opened.isFile() || !sameFileSnapshot(before, opened)) throw new Error("local rules source identity changed"); onOpen?.(); const liveBeforeRead = await lstat(path, { bigint: true }); if (liveBeforeRead.isSymbolicLink() || !liveBeforeRead.isFile() || !sameFileIdentity(opened, liveBeforeRead) || await realpath(path) !== path) throw new Error("local rules source identity changed"); const content = await handle.readFile(); const after = await handle.stat({ bigint: true }); const liveAfterRead = await lstat(path, { bigint: true }); if (!sameFileSnapshot(opened, after) || liveAfterRead.isSymbolicLink() || !liveAfterRead.isFile() || !sameFileIdentity(after, liveAfterRead) || await realpath(path) !== path) throw new Error("local rules source changed while reading"); validateLocalRules(content); return content; } finally { await handle.close(); } }

export async function optionalCanonicalLocalRules(path: string): Promise<Buffer | undefined> { try { return await readCanonicalLocalRules(path); } catch (error) { if ((error as NodeJS.ErrnoException).code === "ENOENT") return undefined; throw error; } }
