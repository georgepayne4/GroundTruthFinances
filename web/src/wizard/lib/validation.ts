/** Validate a numeric field against optional bounds. Returns an error string or undefined. */
export function validateNumber(
  value: number | null | undefined,
  opts: { min?: number; max?: number; label?: string } = {},
): string | undefined {
  if (value == null) return undefined;
  if (Number.isNaN(value)) return `${opts.label ?? "Value"} must be a number`;
  if (opts.min != null && value < opts.min) return `${opts.label ?? "Value"} must be at least ${opts.min}`;
  if (opts.max != null && value > opts.max) return `${opts.label ?? "Value"} must be at most ${opts.max}`;
  return undefined;
}

/** Returns true if the errors object has any truthy entry. */
export function hasErrors(errors: Record<string, string | undefined>): boolean {
  return Object.values(errors).some((e) => !!e);
}
