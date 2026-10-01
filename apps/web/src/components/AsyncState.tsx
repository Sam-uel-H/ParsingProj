import { Alert, CircularProgress, Stack, Typography } from '@mui/material'
import type { ReactNode } from 'react'

export function LoadingState({ label }: { label: string }) {
  return (
    <Stack direction="row" spacing={2} alignItems="center" role="status">
      <CircularProgress size={22} aria-hidden="true" />
      <Typography color="text.secondary">{label}</Typography>
    </Stack>
  )
}

export function EmptyState({
  message,
  action,
}: {
  message: string
  action?: ReactNode
}) {
  return (
    <Alert severity="info" action={action} sx={{ alignItems: 'center' }}>
      {message}
    </Alert>
  )
}
