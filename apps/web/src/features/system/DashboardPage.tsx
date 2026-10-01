import { Box, Button, Container, Stack, Typography } from '@mui/material'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { listDocuments } from '../../api/documents'
import { listDomains } from '../../api/domains'
import { listTemplates } from '../../api/templates'
import { ApiErrorAlert } from '../../components/ApiErrorAlert'
import { LoadingState } from '../../components/AsyncState'
import { HealthStatus } from './HealthStatus'

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <Box sx={{ minWidth: 140 }}>
      <Typography variant="h4" component="p">
        {value}
      </Typography>
      <Typography color="text.secondary">{label}</Typography>
    </Box>
  )
}

export function DashboardPage() {
  const domains = useQuery({
    queryKey: ['domains'],
    queryFn: ({ signal }) => listDomains(signal),
  })
  const templates = useQuery({
    queryKey: ['templates'],
    queryFn: ({ signal }) => listTemplates({}, signal),
  })
  const documents = useQuery({
    queryKey: ['documents'],
    queryFn: ({ signal }) => listDocuments(signal),
  })
  const loading =
    domains.isPending || templates.isPending || documents.isPending
  const error = domains.error ?? templates.error ?? documents.error

  return (
    <Container maxWidth="lg" component="main" sx={{ py: 5 }}>
      <Stack spacing={4}>
        <Box>
          <Typography variant="h3" component="h1" gutterBottom>
            Document Parsing
          </Typography>
          <Typography color="text.secondary">
            Build a template, process a document, review the extracted values,
            and export the result.
          </Typography>
        </Box>

        {loading && <LoadingState label="Loading workspace summary…" />}
        {error && <ApiErrorAlert error={error} />}
        {!loading && !error && (
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={5}>
            <Metric label="Domains" value={domains.data?.length ?? 0} />
            <Metric
              label="Published templates"
              value={
                templates.data?.filter((item) => item.status === 'published')
                  .length ?? 0
              }
            />
            <Metric label="Documents" value={documents.data?.length ?? 0} />
          </Stack>
        )}

        <Box sx={{ borderTop: 1, borderColor: 'divider', pt: 3 }}>
          <Typography variant="h5" component="h2" gutterBottom>
            MVP workflow
          </Typography>
          <Stack
            direction={{ xs: 'column', sm: 'row' }}
            spacing={1}
            flexWrap="wrap"
          >
            <Button component={Link} to="/domains" variant="outlined">
              1. Domains
            </Button>
            <Button component={Link} to="/templates" variant="outlined">
              2. Templates
            </Button>
            <Button component={Link} to="/documents" variant="outlined">
              3. Documents
            </Button>
            <Button component={Link} to="/parse" variant="contained">
              4. Parse and review
            </Button>
          </Stack>
        </Box>

        <HealthStatus />
      </Stack>
    </Container>
  )
}
