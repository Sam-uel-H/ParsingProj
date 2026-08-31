import { useQuery } from '@tanstack/react-query'
import {
  Button,
  CircularProgress,
  Container,
  Stack,
  Typography,
} from '@mui/material'
import { Link, useParams } from 'react-router-dom'

import { getParsingJob } from '../../api/parsing'
import { ApiErrorAlert } from '../../components/ApiErrorAlert'
import { ParsingResults } from './ParsingResults'

export function ParsingJobPage() {
  const { jobId = '' } = useParams()
  const job = useQuery({
    queryKey: ['parsing-job', jobId],
    queryFn: ({ signal }) => getParsingJob(jobId, signal),
  })
  return (
    <Container maxWidth="md" component="main" sx={{ py: 6 }}>
      <Stack spacing={3}>
        <Button component={Link} to="/parse">
          Run another job
        </Button>
        <Typography variant="h3" component="h1">
          Parsing results
        </Typography>
        {job.isPending && <CircularProgress />}
        {job.isError && <ApiErrorAlert error={job.error} />}
        {job.data && <ParsingResults job={job.data} />}
      </Stack>
    </Container>
  )
}
