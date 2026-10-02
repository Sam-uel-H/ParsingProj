import { Alert, LinearProgress, Stack, Typography } from '@mui/material'
import { isJobActive, type TaskProgress } from '../api/jobs'

export function JobProgress({
  progress,
  status,
}: {
  progress?: TaskProgress | null
  status: string
}) {
  return (
    <Stack spacing={1} aria-live="polite">
      <Alert severity={status === 'failed' ? 'error' : 'info'}>
        Job status: {status.replaceAll('_', ' ')}
        {progress?.error_message && ` - ${progress.error_message}`}
        {status === 'queued' &&
          progress?.retryable &&
          ` Retrying after ${new Date(progress.available_at).toLocaleTimeString()}.`}
      </Alert>
      {isJobActive(status) && (
        <LinearProgress
          aria-label="Job progress"
          variant={progress?.total_units ? 'determinate' : 'indeterminate'}
          value={
            progress?.total_units
              ? (100 * progress.completed_units) / progress.total_units
              : 0
          }
        />
      )}
      {progress && (
        <Typography variant="body2" color="text.secondary">
          {progress.completed_units} of {progress.total_units} completed ·
          Attempt {progress.attempts} of {progress.max_attempts}
        </Typography>
      )}
    </Stack>
  )
}
