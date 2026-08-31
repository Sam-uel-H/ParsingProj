import {
  Alert,
  Card,
  CardContent,
  Chip,
  Stack,
  Typography,
} from '@mui/material'

import type { ParsingJob } from '../../api/parsing'

export function ParsingResults({ job }: { job: ParsingJob }) {
  return (
    <Stack spacing={2}>
      <Alert severity={job.status === 'completed' ? 'success' : 'warning'}>
        Job status: {job.status.replaceAll('_', ' ')}
      </Alert>
      {job.results.map((result) => (
        <Card variant="outlined" key={result.id}>
          <CardContent>
            <Stack direction="row" justifyContent="space-between">
              <Typography variant="h6">{result.column_name}</Typography>
              <Chip
                label={result.validation_status.replace('_', ' ')}
                size="small"
              />
            </Stack>
            <Typography>
              Value: {result.canonical_value ?? 'No valid value'}
            </Typography>
            {result.validation_message && (
              <Typography color="error">{result.validation_message}</Typography>
            )}
            <Typography color="text.secondary" variant="body2">
              Retries: {result.retry_count}
            </Typography>
          </CardContent>
        </Card>
      ))}
    </Stack>
  )
}
