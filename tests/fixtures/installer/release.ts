import { createHash } from "node:crypto";
import { cp, mkdir, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { dirname, join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

const repositoryRoot = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "..");

async function filesBelow(root: string, directory = root): Promise<string[]> {
  const result: string[] = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const absolute = join(directory, entry.name);
    if (entry.isDirectory()) result.push(...await filesBelow(root, absolute));
    else if (entry.isFile()) result.push(relative(root, absolute).split(sep).join("/"));
  }
  return result;
}

export async function writeInventory(releaseRoot: string): Promise<void> {
  const paths = ["VERSION", ...await filesBelow(releaseRoot, join(releaseRoot, "bundle"))].sort();
  const lines: string[] = [];
  for (const path of paths) {
    const content = await readFile(join(releaseRoot, path));
    lines.push(`${createHash("sha256").update(content).digest("hex")}  ${path}`);
  }
  await writeFile(join(releaseRoot, "release.files.sha256"), `${lines.join("\n")}\n`);
}

export async function createReleaseFixture(releaseRoot: string, version = "1.0.0-rc.1"): Promise<string> {
  await mkdir(releaseRoot, { recursive: true });
  await cp(join(repositoryRoot, "bundle"), join(releaseRoot, "bundle"), { recursive: true });
  await writeFile(join(releaseRoot, "VERSION"), `${version}\n`);
  await writeInventory(releaseRoot);
  return releaseRoot;
}

export async function createPublishedV130ReleaseFixture(releaseRoot: string): Promise<string> {
  await createReleaseFixture(releaseRoot, "1.3.0");
  const manifestRoot = join(releaseRoot, "bundle", "agent-governance");
  const fixtureRoot = join(repositoryRoot, "tests", "fixtures", "installer", "releases", "v1.3.0");
  await rm(join(manifestRoot, "ssot", "work-items"), { recursive: true, force: true });
  await writeFile(join(manifestRoot, "ssot", "manifest.toml"), await readFile(join(fixtureRoot, "ssot-manifest.toml")));
  await writeInventory(releaseRoot);
  const actualInventory = await readFile(join(releaseRoot, "release.files.sha256"));
  const publishedInventory = await readFile(join(fixtureRoot, "release.files.sha256"));
  if (!actualInventory.equals(publishedInventory)) throw new Error("v1.3.0 release fixture differs from the published inventory");
  return releaseRoot;
}

export async function createPublishedV121ReleaseFixture(releaseRoot: string): Promise<string> {
  await createPublishedV130ReleaseFixture(releaseRoot);
  // Overlay the changed files from published tag v1.2.1 (8da3e47b882276ff3012c5a5c4ace1b744fce08a).
  const fixtureRoot = join(repositoryRoot, "tests", "fixtures", "installer", "releases", "v1.2.1");
  await rm(join(releaseRoot, "bundle", "agent-governance", "templates"), { recursive: true });
  await cp(fixtureRoot, releaseRoot, { recursive: true });
  await writeInventory(releaseRoot);
  const actualInventory = await readFile(join(releaseRoot, "release.files.sha256"));
  const publishedInventory = await readFile(join(fixtureRoot, "release.files.sha256"));
  if (!actualInventory.equals(publishedInventory)) throw new Error("v1.2.1 release fixture differs from the published inventory");
  return releaseRoot;
}
