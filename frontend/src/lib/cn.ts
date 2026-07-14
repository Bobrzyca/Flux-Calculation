/**
 * Tiny classnames joiner. Filters falsy values so conditional classes read
 * cleanly: cn('base', active && 'active', disabled && 'opacity-50').
 */
export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(' ')
}
