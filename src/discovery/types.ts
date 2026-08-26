export const EVIDENCE_FAMILIES = [
  "runtime",
  "state",
  "tooling",
  "ai_metadata",
  "package_metadata",
  "document",
] as const;

export type EvidenceFamily = (typeof EVIDENCE_FAMILIES)[number];
export type EvidenceStrength = "strong" | "corroborating" | "weak";
export type EvidenceSourceKind = "json" | "toml" | "plist" | "sqlite_schema" | "package_metadata";
export type CandidateClass = "DIRECTORY" | "APP_BUNDLE";
export type DiscoveryStatus = "COMPLETE" | "INCOMPLETE";

export interface DiscoveryLimits {
  readonly maxDepth: number;
  readonly maxFiles: number;
  readonly maxEntries: number;
  readonly maxFileBytes: number;
  readonly maxSqliteObjects: number;
  readonly maxSqliteColumns: number;
  readonly maxDurationMs: number;
  readonly maxMetadataLength: number;
}

export interface DiscoveryConfidence {
  readonly highMinimumScore: number;
  readonly highMinimumFamilies: number;
  readonly highMinimumIndependentSources: number;
  readonly highRequiresRuntime: boolean;
  readonly uncertainMinimumScore: number;
}

export interface DiscoverySignal {
  readonly id: string;
  readonly family: EvidenceFamily;
  readonly sourceKinds: readonly EvidenceSourceKind[];
  readonly keys: readonly string[];
  readonly minimumMatches: number;
  readonly strength: EvidenceStrength;
}

export interface EvidenceFamilyDefinition {
  readonly defaultStrength: EvidenceStrength;
  readonly weight: number;
}

export interface CandidateClassDefinition {
  readonly class: CandidateClass;
  readonly label: string;
}

export interface DiscoveryCatalog {
  readonly schemaVersion: 1;
  readonly limits: DiscoveryLimits;
  readonly confidence: DiscoveryConfidence;
  readonly candidateClasses: Readonly<Record<"directory" | "app_bundle", CandidateClassDefinition>>;
  readonly evidenceFamilies: Readonly<Record<EvidenceFamily, EvidenceFamilyDefinition>>;
  readonly signals: readonly DiscoverySignal[];
}

export interface EvidenceRecord {
  readonly family: EvidenceFamily;
  readonly sourceKind: EvidenceSourceKind;
  readonly sourcePath: string;
  readonly signalId: string;
  readonly strength: EvidenceStrength;
  readonly status: DiscoveryStatus;
  readonly metadata: readonly string[];
}

export interface DiscoveryEnvironment {
  readonly home: string;
  readonly xdgConfigHome?: string;
  readonly xdgDataHome?: string;
  readonly platform: NodeJS.Platform;
  readonly macosSystemApplications?: string;
}

export interface DiscoveryZone {
  readonly id: string;
  readonly root: string;
  readonly candidateClass: CandidateClass;
}

export type DiscoveryIssue =
  | "SYMLINK_SKIPPED"
  | "PERMISSION_DENIED"
  | "FILE_SIZE_LIMIT"
  | "FILE_LIMIT"
  | "DEPTH_LIMIT"
  | "ENTRY_LIMIT"
  | "TIME_LIMIT"
  | "IO_ERROR";

export interface DiscoveredCandidate {
  readonly root: string;
  readonly candidateClass: CandidateClass;
  readonly status: DiscoveryStatus;
  readonly files: readonly string[];
  readonly filesVisited: number;
  readonly entriesVisited: number;
  readonly issues: readonly DiscoveryIssue[];
}
