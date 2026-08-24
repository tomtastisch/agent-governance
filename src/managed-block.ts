export interface GovernanceBinding {
  readonly version: string;
  readonly installationRoot: string;
  readonly governancePath: string;
  readonly manifestPath: string;
  readonly governanceDigest: string;
  readonly manifestDigest: string;
  readonly bundleDigest: string;
}

const BEGIN = "<!-- BEGIN AGENT_GOVERNANCE_MANAGED_V1 -->";
const END = "<!-- END AGENT_GOVERNANCE_MANAGED_V1 -->";
const FOREIGN = /<!-- (?:BEGIN|END) AGENT_GOVERNANCE_MANAGED_(?!V1 -->)[^\r\n]*-->/g;

interface ParsedEntry {
  readonly text: string;
  readonly eol: "\n" | "\r\n";
  readonly start?: number;
  readonly end?: number;
  readonly block?: string;
}

function decode(input: Buffer): string {
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(input);
  } catch {
    throw new Error("entry file must be valid UTF-8");
  }
}

function occurrences(text: string, value: string): number[] {
  const indexes: number[] = [];
  let offset = 0;
  while ((offset = text.indexOf(value, offset)) !== -1) {
    indexes.push(offset);
    offset += value.length;
  }
  return indexes;
}

function parse(input: Buffer): ParsedEntry {
  const text = decode(input);
  if (FOREIGN.test(text)) {
    FOREIGN.lastIndex = 0;
    throw new Error("foreign managed marker version");
  }
  FOREIGN.lastIndex = 0;
  const begins = occurrences(text, BEGIN);
  const ends = occurrences(text, END);
  if (begins.length === 0 && ends.length === 0) {
    return { text, eol: text.includes("\r\n") ? "\r\n" : "\n" };
  }
  if (begins.length !== 1 || ends.length !== 1) {
    if (begins.length !== ends.length) throw new Error("incomplete managed block markers");
    throw new Error("duplicate or ambiguous managed block markers");
  }
  const start = begins[0]!;
  const end = ends[0]! + END.length;
  if (ends[0]! < start) throw new Error("incomplete managed block markers");
  const block = text.slice(start, end);
  return { text, eol: block.includes("\r\n") || text.includes("\r\n") ? "\r\n" : "\n", start, end, block };
}

function projection(
  binding: GovernanceBinding,
  eol: "\n" | "\r\n",
  prefixAdded: boolean,
  suffixAdded: boolean,
): string {
  return [
    BEGIN,
    "This is a generated projection; the installed governance bundle is the only normative source.",
    `Governance version: ${binding.version}`,
    `Canonical installation root: ${binding.installationRoot}`,
    `Normative governance entry: ${binding.governancePath}`,
    `Normative manifest: ${binding.manifestPath}`,
    `Expected governance SHA-256: ${binding.governanceDigest}`,
    `Expected manifest SHA-256: ${binding.manifestDigest}`,
    `Expected bundle SHA-256: ${binding.bundleDigest}`,
    "Before every response, load the normative governance entry and manifest from these exact paths.",
    "Keep personal local rules separate and resolve them only through the installed manifest.",
    "If governance is missing, changed, ambiguous, or conflicts with another normative source, fail closed.",
    `Boundary prefix added: ${String(prefixAdded)}`,
    `Boundary suffix added: ${String(suffixAdded)}`,
    END,
  ].join(eol);
}

function boundaryFlags(block: string): { prefixAdded: boolean; suffixAdded: boolean } {
  const prefix = /(?:^|\r?\n)Boundary prefix added: (true|false)(?:\r?\n|$)/.exec(block)?.[1];
  const suffix = /(?:^|\r?\n)Boundary suffix added: (true|false)(?:\r?\n|$)/.exec(block)?.[1];
  if (prefix === undefined || suffix === undefined) throw new Error("managed block is tampered");
  return { prefixAdded: prefix === "true", suffixAdded: suffix === "true" };
}

export function installManagedBlock(input: Buffer, binding: GovernanceBinding): Buffer {
  const parsed = parse(input);
  if (parsed.start !== undefined && parsed.end !== undefined && parsed.block !== undefined) {
    const flags = boundaryFlags(parsed.block);
    const block = projection(binding, parsed.eol, flags.prefixAdded, flags.suffixAdded);
    return Buffer.from(parsed.text.slice(0, parsed.start) + block + parsed.text.slice(parsed.end), "utf8");
  }
  const prefixAdded = parsed.text.length > 0 && !parsed.text.endsWith("\n");
  const prefix = prefixAdded ? parsed.eol : "";
  const suffixAdded = true;
  const block = projection(binding, parsed.eol, prefixAdded, suffixAdded);
  return Buffer.from(parsed.text + prefix + block + parsed.eol, "utf8");
}

export function removeManagedBlock(input: Buffer): Buffer {
  const parsed = parse(input);
  if (parsed.start === undefined || parsed.end === undefined || parsed.block === undefined) return input;
  const flags = boundaryFlags(parsed.block);
  let prefix = parsed.text.slice(0, parsed.start);
  let suffix = parsed.text.slice(parsed.end);
  if (flags.prefixAdded && prefix.endsWith(parsed.eol)) prefix = prefix.slice(0, -parsed.eol.length);
  if (flags.suffixAdded && suffix.startsWith(parsed.eol)) suffix = suffix.slice(parsed.eol.length);
  return Buffer.from(prefix + suffix, "utf8");
}

export function verifyManagedBlock(input: Buffer, binding: GovernanceBinding): void {
  const parsed = parse(input);
  if (parsed.block === undefined) throw new Error("managed block is missing");
  const flags = boundaryFlags(parsed.block);
  const expected = projection(binding, parsed.eol, flags.prefixAdded, flags.suffixAdded);
  if (parsed.block !== expected) throw new Error("managed block mismatch or tampered content");
}
