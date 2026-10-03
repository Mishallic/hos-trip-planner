// Design tokens for the dark product UI. Every colour in the app comes from here.

export const color = {
  // Page and surfaces, darkest to lightest.
  bgDeep: '#05060F',
  bgMid: '#0A1220',
  bgHigh: '#101E2E',
  app: '#0D1E2D',
  surface1: '#04283C',
  surface2: '#043344',
  surface3: '#0B3D52',

  // Accents.
  turquoise: '#40E0D0',
  teal: '#008B8B',
  tealDeep: '#008080',
  mint: '#14D29B',
  coral: '#F8485F',
  orange: '#FB923C',
  amber: '#FEAE37',
  sky: '#93E2EE',
  negative: '#FF7979',

  // Text.
  text: '#FFFFFF',
  textSecondary: '#C4D0D4',
  textMuted: 'rgba(255, 255, 255, 0.45)',

  // Lines and fills derived from the turquoise accent.
  border: 'rgba(64, 224, 208, 0.30)',
  borderSoft: 'rgba(64, 224, 208, 0.14)',
  chip: 'rgba(64, 224, 208, 0.10)',
  card: 'rgba(255, 255, 255, 0.03)',

  // Paper log sheets are light, like the printed form.
  paper: '#F7F5EF',
  paperInk: '#14202B',
} as const

export const gradient = {
  page: `linear-gradient(160deg, ${color.bgDeep} 0%, ${color.bgMid} 45%, ${color.bgHigh} 100%)`,
}

export const shadow = {
  card: '0 16px 48px rgba(0, 0, 0, 0.35), 0 0 28px rgba(64, 224, 208, 0.06)',
  tealGlow: '0 8px 28px rgba(0, 128, 128, 0.35)',
  paper: '0 18px 40px rgba(0, 0, 0, 0.45)',
}

export const radius = {
  button: 10,
  chip: 13,
  card: 16,
  panel: 22,
  pill: 999,
}

export const font = {
  heading: '"Manrope Variable", "DM Sans Variable", system-ui, sans-serif',
  body: '"DM Sans Variable", system-ui, sans-serif',
}

// One colour per stop kind, used by the map pins, stop list and timeline strip.
export const stopColor: Record<string, string> = {
  pre_trip: color.textSecondary,
  pickup: color.mint,
  dropoff: color.coral,
  fuel: color.orange,
  break: color.turquoise,
  rest: color.sky,
  restart: color.amber,
}

export const layout = {
  rail: 64,
  topBar: 64,
  bottomNav: 64,
  sidebar: 400,
  mobile: 768,
}
