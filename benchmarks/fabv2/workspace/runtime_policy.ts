import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { readFileSync } from "node:fs";
import { join } from "node:path";

type TextPart = { type: string; text?: string; [key: string]: unknown };
type ToolOutputPolicy = {
  enabled: boolean;
  max_chars: number;
  tail_chars: number;
  tools: string[];
};

function loadPolicy(): ToolOutputPolicy | null {
  try {
    const payload = JSON.parse(
      readFileSync(join(process.cwd(), "runtime_policy.json"), "utf8"),
    );
    const policy = payload.tool_output;
    if (!policy?.enabled) return null;
    return policy as ToolOutputPolicy;
  } catch {
    return null;
  }
}

function truncate(text: string, maxChars: number, tailChars: number): string {
  if (text.length <= maxChars) return text;
  const marker = `\n\n[Machine policy truncated ${text.length - maxChars} characters]\n\n`;
  const tail = Math.min(tailChars, Math.max(0, maxChars - marker.length));
  const head = Math.max(0, maxChars - marker.length - tail);
  return `${text.slice(0, head)}${marker}${tail ? text.slice(-tail) : ""}`;
}

export default function (pi: ExtensionAPI) {
  const policy = loadPolicy();
  if (!policy) return;
  const selected = new Set(policy.tools);
  pi.on("tool_result", async (event) => {
    if (!selected.has(event.toolName) || !Array.isArray(event.content)) return;
    const content = event.content.map((part: TextPart) =>
      part.type === "text" && typeof part.text === "string"
        ? { ...part, text: truncate(part.text, policy.max_chars, policy.tail_chars) }
        : part,
    );
    return { content };
  });
}
