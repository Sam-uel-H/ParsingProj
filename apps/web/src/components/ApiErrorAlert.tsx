import { Alert } from '@mui/material'

interface ApiErrorAlertProps {
  error: unknown
}

export function ApiErrorAlert({ error }: ApiErrorAlertProps) {
  const message =
    error instanceof Error ? error.message : 'An unexpected API error occurred.'
  return <Alert severity="error">{message}</Alert>
}
