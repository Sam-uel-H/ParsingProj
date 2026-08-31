import {
  Alert,
  Button,
  Card,
  CardContent,
  Stack,
  Typography,
} from '@mui/material'
import { useQuery } from '@tanstack/react-query'

import { getHealth } from '../../api/health'

export function HealthStatus() {
  const health = useQuery({
    queryKey: ['system', 'health'],
    queryFn: ({ signal }) => getHealth(signal),
  })

  return (
    <Card variant="outlined">
      <CardContent>
        <Stack spacing={2}>
          <Typography variant="h5" component="h2">
            Backend connectivity
          </Typography>
          {health.isPending && <Alert severity="info">Checking backend…</Alert>}
          {health.isSuccess && (
            <Alert severity="success">
              Connected to {health.data.service} {health.data.version}
            </Alert>
          )}
          {health.isError && (
            <Alert severity="warning">
              Backend is not reachable. Start the FastAPI server, then retry.
            </Alert>
          )}
          <Button variant="outlined" onClick={() => void health.refetch()}>
            Check again
          </Button>
        </Stack>
      </CardContent>
    </Card>
  )
}
