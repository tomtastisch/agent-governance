import {
  autocompleteMultiselect as clackAutocompleteMultiselect,
  cancel as clackCancel,
  confirm as clackConfirm,
  isCancel as clackIsCancel,
  path as clackPath,
  spinner as clackSpinner,
  text as clackText,
} from "@clack/prompts";
import { isAbsolute, normalize, relative, resolve } from "node:path";

import { sanitizeDisplay } from "../terminal/theme.ts";
import { renderHarnessRow, renderLegend, createTerminalTheme } from "./theme.ts";
import type { HarnessRow } from "./types.ts";
import {
  INIT_CANCELLED,
  type InitPlannedTarget,
  type InitPrompt,
  type InitSelection,
  type InitStep,
} from "./types.ts";

const CUSTOM_VALUE = "__custom__";

interface PromptOption {
  readonly value: string;
  readonly label: string;
  readonly hint?: string;
  readonly disabled?: boolean;
}

interface PromptFilterOption {
  readonly value: string;
  readonly label?: string;
  readonly hint?: string;
  readonly disabled?: boolean;
}

interface AutocompleteMultiSelectOptions {
  readonly message: string;
  readonly options: PromptOption[];
  readonly initialValues: string[];
  readonly required: boolean;
  readonly filter: (search: string, option: PromptFilterOption) => boolean;
}

interface PathOptions {
  readonly message: string;
  readonly root?: string;
  readonly initialValue?: string;
  readonly directory?: boolean;
  readonly validate?: (value: string | undefined) => string | Error | undefined;
}

interface TextOptions {
  readonly message: string;
  readonly placeholder?: string;
  readonly initialValue?: string;
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
  readonly text: (options: TextOptions) => Promise<unknown>;
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
  text: (options: TextOptions) => clackText(options),
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

function assertSelections(value: unknown, rows: ReadonlyMap<string, HarnessRow>): string[] {
  if (!Array.isArray(value) || value.some((item) => typeof item !== "string")) {
    throw new Error("prompt returned an invalid target selection");
  }
  const values = value as string[];
  if (new Set(values).size !== values.length || values.some((item) => item !== CUSTOM_VALUE && !rows.has(item))) {
    throw new Error("prompt returned an unknown or duplicate target selection");
  }
  return values;
}

function assertPath(value: unknown): string {
  if (typeof value !== "string") throw new Error("path prompt returned an invalid value");
  return value;
}

function filterTargetOption(search: string, option: PromptFilterOption): boolean {
  if (option.value === CUSTOM_VALUE) return true;
  if (search === "?") return false;
  const normalizedSearch = search.toLowerCase();
  return (option.label ?? option.value).toLowerCase().includes(normalizedSearch)
    || (option.hint ?? "").toLowerCase().includes(normalizedSearch)
    || option.value.toLowerCase().includes(normalizedSearch);
}

function renderApprovalPlan(plans: readonly InitPlannedTarget[]): string {
  return plans.map(({ target, status, plan, displayName }, index) => {
    if (plan.plan === undefined) throw new Error("init approval requires a concrete installation plan");
    const resources = plan.plan.resources.map(({ id, operation, target: resourceTarget }) =>
      `- ${id}: ${operation} -> ${sanitizeDisplay(resourceTarget, 1024)}`
    );
    return [
      `Ziel ${index + 1}`,
      `Harness: ${sanitizeDisplay(displayName, 96)}`,
      `Target Root: ${sanitizeDisplay(target.targetRoot, 1024)}`,
      `Entry File: ${sanitizeDisplay(target.entryFile, 1024)}`,
      `Aktueller Zustand: ${status.state}`,
      `Mutation: ${plan.plan.command}`,
      "Ressourcen:",
      ...resources,
    ].join("\n");
  }).join("\n\n");
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
  let activeStep: InitStep | undefined;

  const stopProgress = (): void => {
    if (!progressActive) return;
    progress.stop(activeStep === undefined ? undefined : `[${activeStep.position}/${activeStep.total}] ${activeStep.title}`);
    progressActive = false;
    activeStep = undefined;
  };

  const askPath = async (options: PathOptions): Promise<string | typeof INIT_CANCELLED> => {
    const value = await operations.path(options);
    if (operations.isCancel(value)) return cancelled(operations);
    return assertPath(value);
  };

  const askEntry = async (message: string, root: string): Promise<string | typeof INIT_CANCELLED> => {
    const value = await operations.text({
      message,
      placeholder: "AGENTS.md",
      validate: (entry) => validateEntry(root, entry),
    });
    if (operations.isCancel(value)) return cancelled(operations);
    return assertPath(value);
  };

  return Object.freeze({
    dispose(): void {
      stopProgress();
    },

    step(step: InitStep): void {
      stopProgress();
      progress.start(`[${step.position}/${step.total}] ${step.title}`);
      progressActive = true;
      activeStep = step;
    },

    async selectTargets(rows: readonly HarnessRow[]): Promise<readonly InitSelection[] | typeof INIT_CANCELLED> {
      stopProgress();
      const byId = new Map(rows.map((row) => [row.id, row]));
      const options: PromptOption[] = [
        { value: CUSTOM_VALUE, label: "Coding-Harness nicht dabei?", hint: theme.cyan("[fokus]") },
        ...rows.map((row) => ({
          value: row.id,
          label: renderHarnessRow(row, { focused: false, selected: false }, theme),
          hint: theme.cyan("[fokus]"),
          ...(row.supported ? {} : { disabled: true }),
        })),
      ];
      const result = await operations.autocompleteMultiselect({
        message: `Coding-Harnesses auswählen\nCoding-Harness nicht dabei? — ? tippen, Tab wählen\n${renderLegend(theme)}`,
        options,
        initialValues: rows
          .filter((row) => row.supported)
          .map((row) => row.id),
        required: true,
        filter: filterTargetOption,
      });
      if (operations.isCancel(result)) return cancelled(operations);
      const values = assertSelections(result, byId);
      const selections: InitSelection[] = [];
      for (const value of values) {
        if (value === CUSTOM_VALUE) {
          const targetRoot = await askPath({
            message: "Absoluter Root des weiteren Coding-Harness",
            directory: true,
            validate: validateAbsoluteRoot,
          });
          if (targetRoot === INIT_CANCELLED) return INIT_CANCELLED;
          const entryValue = await askEntry("Relative Markdown-Entry-Datei", targetRoot);
          if (entryValue === INIT_CANCELLED) return INIT_CANCELLED;
          selections.push(Object.freeze({
            manualInput: Object.freeze({ targetRoot, entryFile: relativeEntry(targetRoot, entryValue) }),
          }));
          continue;
        }
        const row = byId.get(value)!;
        selections.push(Object.freeze({
          harness: Object.freeze({ id: row.id, displayName: row.displayName }),
        }));
      }
      return Object.freeze(selections);
    },

    async confirm(plans: readonly InitPlannedTarget[]): Promise<boolean | typeof INIT_CANCELLED> {
      stopProgress();
      const targetCount = plans.length;
      const renderedPlan = renderApprovalPlan(plans);
      const result = await operations.confirm({
        message: [
          ...(renderedPlan === "" ? [] : ["Geplanter Ablauf:", renderedPlan, ""]),
          `${targetCount} Ziel${targetCount === 1 ? "" : "e"} jetzt einrichten und anschließend verifizieren?`,
        ].join("\n"),
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
