// Per-person accent hues + avatar tints, from the roundtable design doc.
export const HUES: Record<string, number> = {
  product: 155, engineering: 245, design: 330, security: 30,
  data: 200, architecture: 275, quality: 130, delivery: 70, chair: 275, you: 275,
}

export function hueFor(id: string, fallback = 275): number {
  return HUES[id] ?? fallback
}

export function avatarFill(hue: number): string { return `oklch(0.94 0.04 ${hue})` }
export function avatarText(hue: number): string { return `oklch(0.42 0.15 ${hue})` }

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/)
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

// "Agreed so far" item dot colors by type.
export const AGREED_DOT: Record<string, string> = {
  decision: 'oklch(0.55 0.15 275)',
  constraint: 'oklch(0.68 0.14 65)',
  commitment: 'oklch(0.6 0.13 155)',
}
