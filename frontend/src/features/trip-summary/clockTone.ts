import { color } from '../../theme/tokens'

/** Amber under an hour left, coral when a clock has run out, turquoise otherwise. */
export function clockTone(minutesLeft: number): string {
  if (minutesLeft <= 0) return color.coral
  if (minutesLeft < 60) return color.amber
  return color.turquoise
}
