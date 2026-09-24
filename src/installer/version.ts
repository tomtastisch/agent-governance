export const SEMVER = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$/;

export function compareSemver(left: string, right: string): number {
  const a = SEMVER.exec(left); const b = SEMVER.exec(right); if (a === null || b === null) throw new Error("invalid release version in current metadata");
  for (let index = 1; index <= 3; index += 1) { const difference = Number(a[index]) - Number(b[index]); if (difference !== 0) return Math.sign(difference); }
  const leftPre = a[4]; const rightPre = b[4]; if (leftPre === undefined) return rightPre === undefined ? 0 : 1; if (rightPre === undefined) return -1;
  const leftParts = leftPre.split("."); const rightParts = rightPre.split(".");
  for (let index = 0; index < Math.max(leftParts.length, rightParts.length); index += 1) { const x = leftParts[index]; const y = rightParts[index]; if (x === undefined) return -1; if (y === undefined) return 1; if (x === y) continue; const xn = /^\d+$/.test(x); const yn = /^\d+$/.test(y); if (xn && yn) return Number(x) < Number(y) ? -1 : 1; if (xn !== yn) return xn ? -1 : 1; return x < y ? -1 : 1; }
  return 0;
}
