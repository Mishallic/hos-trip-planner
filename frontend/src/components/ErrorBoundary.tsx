import { Box, Button, Typography } from '@mui/material'
import { TriangleAlert } from 'lucide-react'
import { Component, type ErrorInfo, type ReactNode } from 'react'

import { color } from '../theme/tokens'

interface State {
  failed: boolean
}

/**
 * A view that throws while drawing shows this instead of a blank page. The trip is
 * kept in the URL, so reloading brings it back.
 */
export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { failed: false }

  static getDerivedStateFromError(): State {
    return { failed: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('A view failed to draw', error, info.componentStack)
  }

  render() {
    if (!this.state.failed) return this.props.children
    return (
      <Box role="alert" sx={{ height: '100%', display: 'grid', placeItems: 'center', p: 3, textAlign: 'center' }}>
        <Box sx={{ maxWidth: 420 }}>
          <Box sx={{ color: color.amber, display: 'flex', justifyContent: 'center', mb: 1.5 }}>
            <TriangleAlert size={32} strokeWidth={1.7} />
          </Box>
          <Typography variant="h6" component="p">
            This view could not be drawn
          </Typography>
          <Typography variant="body2" sx={{ mt: 0.75, mb: 2 }}>
            Your trip is saved in the link. Reloading the page usually fixes it.
          </Typography>
          <Button variant="contained" onClick={() => window.location.reload()}>
            Reload
          </Button>
        </Box>
      </Box>
    )
  }
}
