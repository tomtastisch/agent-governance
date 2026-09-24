import type { InstallPhase, InstallerRequest } from "../contracts.ts";
import type { SignalSource } from "../signals.ts";

export const architecture = "GLOBAL_EXPLICIT_PATH_MANAGED_BLOCK" as const;

export type TransactionCheckpoint = "beforeMutation" | "afterLocalRulesSourceOpen" | "afterLocalRulesBackup" | "afterBackupWrites" | "afterReleaseStageCreation" | "afterReceipt" | "afterEntry" | "afterCurrent" | "beforeVerification" | "duringRollback" | "beforeRollbackEntry" | "afterRollbackEntryValidation" | "beforeRollbackEntryDetach" | "afterRollbackEntryDetachReservation" | "beforeRollbackEntryDetachMove" | "afterRollbackNativeDirectoriesBound" | "afterRollbackEntryDetach" | "beforeRollbackDetachFinalization" | "afterRollbackEntry" | "afterRollbackCurrent" | "afterCommitTopReceipt" | "afterRollbackBackupReceipt";

export interface TransactionRequest extends InstallerRequest {
  readonly faultAfter?: InstallPhase;
  readonly faultDuringRollback?: boolean;
  readonly signalSource?: SignalSource;
  readonly onCheckpoint?: (checkpoint: TransactionCheckpoint) => void;
}
