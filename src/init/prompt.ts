import {
  autocompleteMultiselect as clackAutocompleteMultiselect,
  cancel as clackCancel,
  confirm as clackConfirm,
  isCancel as clackIsCancel,
  path as clackPath,
  spinner as clackSpinner,
} from "@clack/prompts";
import { isAbsolute, normalize, relative, resolve } from "node:path";

import { resolveCandidateIdentity } from "../discovery/identity.ts";
import type { Candidate } from "../discovery/types.ts";
import { createTerminalTheme, renderCandidate, renderLegend } from "./theme.ts";
import {
  INIT_CANCELLED,
  type InitBindingSelection,
  type InitPlannedTarget,
  type InitPrompt,
  type InitStep,
} from "./types.ts";

const CUSTOM_VALUE = "__custom__";

interface PromptOption {
  readonly value: string;
  readonly label: string;
  readonly hint?: string;
}

interface AutocompleteMultiSelectOptions {
  readonly message: string;
  readonly options: PromptOption[];
  readonly initialValues: string[];
  readonly required: boolean;
}

interface PathOptions {
  readonly message: string;
  readonly root?: string;
  readonly initialValue?: string;
  readonly directory?: boolean;
  readonly validate?: (value: string | undefined) => string | Error | undefined;
}

interface ConfirmOptions {
  readonly message: string;
  readonly active: string;
  readonly inactive: string;
  readonly initialValue: boolean;
}

interface PromptSpinner {
  readonly start: (message?: string) => void;
  readonly stop: (message?: string) => void;
}

export interface ClackPromptOperations {
  readonly autocompleteMultiselect: (options: AutocompleteMultiSelectOptions) => Promise<unknown>;
  readonly path: (options: PathOptions) => Promise<unknown>;
  readonly confirm: (options: ConfirmOptions) => Promise<unknown>;
  readonly spinner: () => PromptSpinner;
  readonly cancel: (message?: string) => void;
  readonly isCancel: (value: unknown) => boolean;
}

export interface ClackPromptIO {
  readonly prompts?: ClackPromptOperations;
  readonly columns?: number;
  readonly environment?: Readonly<Record<string, string | undefined>>;
  readonly color?: boolean;
}

const DEFAULT_OPERATIONS: ClackPromptOperations = Object.freeze({
  autocompleteMultiselect: (options: AutocompleteMultiSelectOptions) => clackAutocompleteMultiselect(options),
  path: (options: PathOptions) => clackPath(options),
  confirm: (options: ConfirmOptions) => clackConfirm(options),
  spinner: () => clackSpinner(),
  cancel: (message?: string) => clackCancel(message),
  isCancel: clackIsCancel,
});

function cancelled(operations: ClackPromptOperations): typeof INIT_CANCELLED {
  operations.cancel("Einrichtung abgebrochen.");
  return INIT_CANCELLED;
}

function validateAbsoluteRoot(value: string | undefined): string | undefined {
  if (value === undefined || value === "" || /[\0\r\n]/u.test(value) || !isAbsolute(value) || resolve(value) !== value) {
    return "Bitte einen kanonischen absoluten Pfad angeben.";
  }
  return undefined;
}

function relativeEntry(root: string, value: string): string {
  const candidate = isAbsolute(value) ? relative(root, value) : value;
  return normalize(candidate);
}

function validateEntry(root: string, value: string | undefined): string | undefined {
  if (value === undefined) return "Bitte eine relative Markdown-Datei innerhalb des Zielroots angeben.";
  const entry = relativeEntry(root, value);
  if (
    entry === ""
    || /[\0\r\n]/u.test(entry)
    || isAbsolute(entry)
    || entry === ".."
    || entry.startsWith("../")
    || entry.includes("\\")
    || !/\.(?:md|markdown)$/iu.test(entry)
  ) {
    return "Bitte eine relative Markdown-Datei innerhalb des Zielroots angeben.";
  }
  return undefined;
}

function assertSelections(value: unknown, candidates: ReadonlyMap<string, Candidate>): string[] {
  if (!Array.isArray(value) || value.some((item) => typeof item !== "string")) {
    throw new Error("prompt returned an invalid target selection");
  }
  const values = value as string[];
  if (new Set(values).size !== values.length || values.some((item) => item !== CUSTOM_VALUE && !candidates.has(item))) {
    throw new Error("prompt returned an unknown or duplicate target selection");
  }
  return values;
}

function assertPath(value: unknown): string {
  if (typeof value !== "string") throw new Error("path prompt returned an invalid value");
  return value;
}

export function createClackPrompt(io: ClackPromptIO = {}): InitPrompt {
  const operations = io.prompts ?? DEFAULT_OPERATIONS;
  const promptColumns = Math.max(20, (io.columns ?? process.stdout.columns ?? 80) - 4);
  const theme = createTerminalTheme({
    columns: promptColumns,
    ...(io.environment === undefined ? {} : { environment: io.environment }),
    ...(io.color === undefined ? {} : { color: io.color }),
  });
  const progress = operations.spinner();
  let progressActive = false;

  const stopProgress = (): void => {
    if (!progressActive) return;
    progress.stop();
    progressActive = false;
  };

  const askPath = async (options: PathOptions): Promise<string | typeof INIT_CANCELLED> => {
    const value = await operations.path(options);
    if (operations.isCancel(value)) return cancelled(operations);
    return assertPath(value);
  };

  return Object.freeze({
    step(step: InitStep): void {
      stopProgress();
      progress.start(`[${step.position}/${step.total}] ${step.title}`);
      progressActive = true;
    },

    async selectTargets(candidates: readonly Candidate[]): Promise<readonly InitBindingSelection[] | typeof INIT_CANCELLED> {
      stopProgress();
      const eligible = candidates.filter((candidate) => candidate.confidence !== "REJECTED");
      const byRoot = new Map(eligible.map((candidate) => [candidate.root, candidate]));
      const options: PromptOption[] = eligible.map((candidate) => ({
        value: candidate.root,
        label: renderCandidate(candidate, { focused: false, selected: false }, theme),
        hint: theme.cyan("[fokus]"),
      }));
      options.push({ value: CUSTOM_VALUE, label: "AI/LLM nicht dabei?", hint: theme.cyan("[fokus]") });
      const result = await operations.autocompleteMultiselect({
        message: `Ziele auswählen\n${renderLegend(theme)}`,
        options,
        initialValues: eligible
          .filter((candidate) => candidate.confidence === "HIGH_CONFIDENCE")
          .map((candidate) => candidate.root),
        required: true,
      });
      if (operations.isCancel(result)) return cancelled(operations);
      const values = assertSelections(result, byRoot);
      const selections: InitBindingSelection[] = [];
      for (const value of values) {
        if (value === CUSTOM_VALUE) {
          const targetRoot = await askPath({
            message: "Absoluter Root des weiteren AI-/LLM-Ziels",
            directory: true,
            validate: validateAbsoluteRoot,
          });
          if (targetRoot === INIT_CANCELLED) return INIT_CANCELLED;
          const entryValue = await askPath({
            message: "Relative Markdown-Entry-Datei",
            root: targetRoot,
            initialValue: `${targetRoot}/`,
            validate: (entry) => validateEntry(targetRoot, entry),
          });
          if (entryValue === INIT_CANCELLED) return INIT_CANCELLED;
          selections.push(Object.freeze({
            manualInput: Object.freeze({ targetRoot, entryFile: relativeEntry(targetRoot, entryValue) }),
          }));
          continue;
        }
        const candidate = byRoot.get(value)!;
        const entryValue = await askPath({
          message: `${resolveCandidateIdentity(candidate).label}: relative Markdown-Entry-Datei`,
          root: candidate.root,
          initialValue: `${candidate.root}/`,
          validate: (entry) => validateEntry(candidate.root, entry),
        });
        if (entryValue === INIT_CANCELLED) return INIT_CANCELLED;
        selections.push(Object.freeze({
          candidate,
          manualInput: Object.freeze({ entryFile: relativeEntry(candidate.root, entryValue) }),
        }));
      }
      return Object.freeze(selections);
    },

    async confirm(plans: readonly InitPlannedTarget[]): Promise<boolean | typeof INIT_CANCELLED> {
      stopProgress();
      const targetCount = plans.length;
      const result = await operations.confirm({
        message: `${targetCount} Ziel${targetCount === 1 ? "" : "e"} jetzt einrichten und anschließend verifizieren?`,
        active: "Einrichten",
        inactive: "Abbrechen",
        initialValue: false,
      });
      if (operations.isCancel(result)) return cancelled(operations);
      if (typeof result !== "boolean") throw new Error("confirm prompt returned an invalid value");
      return result;
    },
  });
}
