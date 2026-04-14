import yaml from "js-yaml";

export interface ParseResult {
  data: Record<string, unknown> | null;
  format: "json" | "yaml" | null;
  error: string | null;
}

/**
 * Parse a profile string as JSON or YAML. Auto-detects format by trying JSON first.
 *
 * Returns a structured result with either `data` populated or `error` explaining
 * the failure. Never throws.
 */
export function parseProfile(text: string): ParseResult {
  const trimmed = text.trim();
  if (!trimmed) {
    return { data: null, format: null, error: "Profile is empty" };
  }

  // JSON looks like JSON — try it first
  if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
    try {
      const data = JSON.parse(trimmed);
      if (!data || typeof data !== "object" || Array.isArray(data)) {
        return { data: null, format: "json", error: "Profile must be a JSON object" };
      }
      return { data, format: "json", error: null };
    } catch (e) {
      return {
        data: null,
        format: "json",
        error: e instanceof Error ? `JSON parse error: ${e.message}` : "Invalid JSON",
      };
    }
  }

  // Otherwise treat as YAML
  try {
    const data = yaml.load(trimmed);
    if (!data || typeof data !== "object" || Array.isArray(data)) {
      return { data: null, format: "yaml", error: "Profile must be a YAML mapping" };
    }
    return { data: data as Record<string, unknown>, format: "yaml", error: null };
  } catch (e) {
    if (e instanceof yaml.YAMLException) {
      const line = e.mark?.line != null ? ` (line ${e.mark.line + 1})` : "";
      return { data: null, format: "yaml", error: `YAML parse error${line}: ${e.reason || e.message}` };
    }
    return {
      data: null,
      format: "yaml",
      error: e instanceof Error ? e.message : "Invalid YAML",
    };
  }
}

/** Stringify a profile object as indented JSON. */
export function stringifyProfile(profile: Record<string, unknown>): string {
  return JSON.stringify(profile, null, 2);
}
