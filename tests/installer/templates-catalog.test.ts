import assert from "node:assert/strict";
import { mkdir, mkdtemp, rm, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { loadTemplateIndex, parseTemplatesManifestText, TEMPLATE_CATEGORIES } from "../../src/templates-catalog.ts";

const VALID = `schema_version = 1

[templates.git_commit]
path = "git/commit.md"
category = "git"
format = "markdown"

[templates.git_branch]
path = "git/branch.md"
category = "git"
format = "markdown"
`;

const CANONICAL_IDS = [
  "git_commit",
  "git_branch",
  "delivery_push_pr_checkpoint",
  "delivery_pull_request",
  "delivery_release_checkpoint",
  "review_finding",
  "context_handoff",
  "communication_status",
  "communication_tool_error_blocker",
  "communication_completion",
  "external_effects_approval_checkpoint",
];

test("templates manifest accepts closed entries", () => {
  const index = parseTemplatesManifestText(VALID);
  assert.equal(index.schemaVersion, 1);
  assert.equal(Object.keys(index.templates).length, 2);
  const commit = index.templates.git_commit;
  assert.ok(commit);
  assert.equal(commit.category, "git");
  assert.equal(commit.path, "git/commit.md");
  assert.equal(commit.format, "markdown");
});

test("template categories form a closed ownership model", () => {
  assert.deepEqual([...TEMPLATE_CATEGORIES].sort(), ["communication", "context", "delivery", "external_effects", "git", "review"]);
});

const rejections: ReadonlyArray<[string, string, RegExp]> = [
  ["an unknown top-level field", VALID.replace("schema_version = 1\n", 'schema_version = 1\nunexpected = "shadow"\n'), /missing or unknown fields/i],
  ["a wrong schema version", VALID.replace("schema_version = 1", "schema_version = 2"), /schema is invalid/i],
  ["an unknown category", VALID.replace('category = "git"', 'category = "future"'), /category is unknown/i],
  ["an unsupported format", VALID.replace('format = "markdown"', 'format = "yaml"'), /format is unsupported/i],
  ["a non-markdown path", VALID.replace('path = "git/commit.md"', 'path = "git/commit.txt"'), /invalid format/i],
  ["a traversal path", VALID.replace('path = "git/commit.md"', 'path = "../commit.md"'), /invalid manifest path/i],
  ["an absolute path", VALID.replace('path = "git/commit.md"', 'path = "/abs/commit.md"'), /invalid manifest path/i],
  ["a duplicate template path", VALID.replace('path = "git/branch.md"', 'path = "git/commit.md"'), /duplicate template paths/i],
];

for (const [label, text, pattern] of rejections) {
  test(`templates manifest fails closed on ${label}`, () => {
    assert.throws(() => parseTemplatesManifestText(text), pattern);
  });
}

test("the canonical template registry registers exactly the real generic templates", () => {
  const { index, templateFile } = loadTemplateIndex();
  assert.deepEqual(Object.keys(index.templates).sort(), [...CANONICAL_IDS].sort());
  for (const id of CANONICAL_IDS) {
    const resolved = templateFile(id);
    assert.match(resolved, /templates\/.+\.md$/);
  }
});

test("runtime template resolution rejects missing and symlinked template files", async () => {
  const root = await mkdtemp(join(tmpdir(), "agent-governance-templates-"));
  try {
    const templatesRoot = join(root, "bundle", "agent-governance", "templates");
    await mkdir(join(templatesRoot, "git"), { recursive: true });
    const manifest = join(templatesRoot, "manifest.toml");
    const writeManifest = (path: string) =>
      writeFile(manifest, `schema_version = 1\n\n[templates.git_commit]\npath = "${path}"\ncategory = "git"\nformat = "markdown"\n`);
    await writeManifest("git/missing.md");
    assert.throws(() => loadTemplateIndex(root), /must reference an existing file/);

    await writeFile(join(root, "outside.md"), "outside\n");
    await writeManifest("git/commit.md");
    await symlink(join(root, "outside.md"), join(templatesRoot, "git", "commit.md"));
    assert.throws(() => loadTemplateIndex(root), /symlink/i);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("runtime template resolution rejects an unknown template id", () => {
  const { templateFile } = loadTemplateIndex();
  assert.throws(() => templateFile("unknown_template"), /does not register template/i);
});

test("runtime template resolution rejects unregistered template files", async () => {
  const root = await mkdtemp(join(tmpdir(), "agent-governance-templates-orphan-"));
  try {
    const templatesRoot = join(root, "bundle", "agent-governance", "templates");
    await mkdir(join(templatesRoot, "git"), { recursive: true });
    await writeFile(join(templatesRoot, "manifest.toml"), `schema_version = 1\n\n[templates.git_commit]\npath = "git/commit.md"\ncategory = "git"\nformat = "markdown"\n`);
    await writeFile(join(templatesRoot, "git", "commit.md"), "# commit\n");
    await writeFile(join(templatesRoot, "git", "orphan.md"), "# orphan\n");
    assert.throws(() => loadTemplateIndex(root), /unregistered/i);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
