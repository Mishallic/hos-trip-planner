import { color } from '../theme/tokens'

/** The product mark: a clock face whose hand is a route line. */
export function BrandMark({ size = 32 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" role="img" aria-label="HOS Trip Planner">
      <rect x="1" y="1" width="30" height="30" rx="9" fill={color.surface1} stroke={color.border} />
      <circle cx="16" cy="16" r="9" fill="none" stroke={color.turquoise} strokeWidth="2" opacity="0.9" />
      <path
        d="M16 16 L16 10.5 M16 16 L20.5 19"
        stroke={color.text}
        strokeWidth="2.2"
        strokeLinecap="round"
      />
      <circle cx="16" cy="16" r="1.8" fill={color.coral} />
    </svg>
  )
}
