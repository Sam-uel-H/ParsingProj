import { Alert } from '@mui/material'

import { ApiError } from '../api/client'

interface ApiErrorAlertProps {
  error: unknown
}

export function ApiErrorAlert({ error }: ApiErrorAlertProps) {
  const message =
    error instanceof Error ? error.message : 'An unexpected API error occurred.'
  const requestId = error instanceof ApiError ? error.requestId : undefined
  return (
    <Alert severity="error">
      {message}
      {requestId && ` Request ID: ${requestId}`}
    </Alert>
  )
}
