import { fileURLToPath } from "node:url";

import { createTerminalTheme } from "./theme.ts";

export const BRANDING_ASSET_PATH = fileURLToPath(
  new URL("../../assets/branding/agent-governance-terminal.png", import.meta.url),
);

export interface BrandingIO {
  readonly write: (value: string) => void;
  readonly columns?: number;
  readonly environment?: Readonly<Record<string, string | undefined>>;
  readonly color?: boolean;
  readonly renderImage?: (path: string, options: { readonly width: 8; readonly height: 4 }) => Promise<string>;
}

export async function renderBranding(io: BrandingIO): Promise<void> {
  if (io.renderImage !== undefined) {
    try {
      const rendered = await io.renderImage(BRANDING_ASSET_PATH, { width: 8, height: 4 });
      if (rendered !== "") io.write(`${rendered}${rendered.endsWith("\n") ? "" : "\n"}`);
      return;
    } catch {
      // Branding is decorative. The semantic text fallback remains sufficient.
    }
  }
  const theme = createTerminalTheme({
    ...(io.columns === undefined ? {} : { columns: io.columns }),
    ...(io.environment === undefined ? {} : { environment: io.environment }),
    ...(io.color === undefined ? {} : { color: io.color }),
  });
  io.write(`${theme.cyan("[AG]")} Agent Governance\n`);
}
