import { Alert, Button, Container, Stack, Typography } from '@mui/material'
import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  failed: boolean
}

export class RouteErrorBoundary extends Component<Props, State> {
  state: State = { failed: false }

  static getDerivedStateFromError(): State {
    return { failed: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Route rendering failed', error.name, info.componentStack)
  }

  render() {
    if (!this.state.failed) return this.props.children
    return (
      <Container maxWidth="md" component="main" sx={{ py: 6 }}>
        <Stack spacing={3}>
          <Typography variant="h4" component="h1">
            This page could not be displayed
          </Typography>
          <Alert severity="error">
            An unexpected browser error occurred. Reload the page to try again.
          </Alert>
          <Button variant="contained" onClick={() => window.location.reload()}>
            Reload page
          </Button>
        </Stack>
      </Container>
    )
  }
}
