import { createTheme } from '@mui/material/styles'

import { color, font, gradient, radius, shadow } from './tokens'

// Dark only. No default MUI blue, no elevation shadows, no white cards.
export const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: { main: color.teal, light: color.turquoise, dark: color.tealDeep, contrastText: color.text },
    secondary: { main: color.turquoise, contrastText: color.bgDeep },
    success: { main: color.mint },
    warning: { main: color.orange },
    error: { main: color.coral },
    info: { main: color.sky },
    background: { default: color.bgMid, paper: color.app },
    text: { primary: color.text, secondary: color.textSecondary, disabled: color.textMuted },
    divider: color.borderSoft,
  },
  shape: { borderRadius: radius.button },
  typography: {
    fontFamily: font.body,
    h1: { fontFamily: font.heading, fontWeight: 800, letterSpacing: '-0.04em' },
    h2: { fontFamily: font.heading, fontWeight: 800, letterSpacing: '-0.035em' },
    h3: { fontFamily: font.heading, fontWeight: 700, letterSpacing: '-0.03em' },
    h4: { fontFamily: font.heading, fontWeight: 700, letterSpacing: '-0.025em' },
    h5: { fontFamily: font.heading, fontWeight: 700, letterSpacing: '-0.02em' },
    h6: { fontFamily: font.heading, fontWeight: 700, letterSpacing: '-0.02em', fontSize: '1.1rem' },
    subtitle2: { fontWeight: 600, color: color.turquoise, opacity: 0.85 },
    body2: { color: color.textSecondary },
    caption: { color: color.textMuted },
    overline: { fontWeight: 700, letterSpacing: '0.08em', lineHeight: 1.6 },
    button: { textTransform: 'none', fontWeight: 600, letterSpacing: 0 },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        // A solid colour under everything, so long pages never show white below the fold.
        html: { backgroundColor: color.bgMid },
        'body, #root': { minHeight: '100%' },
        body: {
          background: gradient.page,
          backgroundColor: color.bgMid,
          backgroundAttachment: 'fixed',
          color: color.text,
          fontVariantNumeric: 'tabular-nums',
          WebkitFontSmoothing: 'antialiased',
        },
        '::selection': { background: 'rgba(64, 224, 208, 0.25)' },
      },
    },
    MuiPaper: {
      defaultProps: { elevation: 0 },
      styleOverrides: { root: { backgroundImage: 'none' } },
    },
    MuiCard: {
      defaultProps: { elevation: 0 },
      styleOverrides: {
        root: {
          background: color.card,
          border: `1px solid ${color.border}`,
          borderRadius: radius.card,
          boxShadow: shadow.card,
        },
      },
    },
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: {
        root: { borderRadius: radius.button, paddingInline: 20 },
        outlined: { borderColor: color.border, color: color.textSecondary },
      },
      variants: [
        {
          props: { variant: 'contained', color: 'primary' },
          style: {
            background: color.teal,
            boxShadow: shadow.tealGlow,
            '&:hover': { background: color.tealDeep, boxShadow: shadow.tealGlow },
          },
        },
      ],
    },
    MuiChip: {
      styleOverrides: {
        root: { borderRadius: radius.pill, fontWeight: 600 },
        sizeSmall: { fontSize: '0.7rem', height: 22 },
      },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          borderRadius: radius.button,
          background: 'rgba(255, 255, 255, 0.04)',
          '& .MuiOutlinedInput-notchedOutline': { borderColor: color.borderSoft },
          '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: color.border },
          '&.Mui-focused .MuiOutlinedInput-notchedOutline': { borderColor: color.turquoise },
        },
      },
    },
    MuiInputLabel: {
      styleOverrides: { root: { color: color.textMuted, '&.Mui-focused': { color: color.turquoise } } },
    },
    MuiTooltip: {
      styleOverrides: {
        tooltip: { background: color.surface1, border: `1px solid ${color.border}`, fontSize: 12 },
      },
    },
  },
})
