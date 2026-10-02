import { useQuery } from '@tanstack/react-query'
import {
  Button,
  Card,
  CardContent,
  Chip,
  Container,
  Stack,
  Typography,
} from '@mui/material'
import { Link } from 'react-router-dom'

import { listDocuments } from '../../api/documents'
import { isJobActive } from '../../api/jobs'
import { listDomains } from '../../api/domains'
import { ApiErrorAlert } from '../../components/ApiErrorAlert'
import { EmptyState, LoadingState } from '../../components/AsyncState'

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function DocumentsPage() {
  const documents = useQuery({
    queryKey: ['documents'],
    queryFn: ({ signal }) => listDocuments(signal),
    refetchInterval: (query) =>
      query.state.data?.some((item) => isJobActive(item.processing_status))
        ? 1000
        : false,
  })
  const domains = useQuery({
    queryKey: ['domains'],
    queryFn: ({ signal }) => listDomains(signal),
  })
  const domainNames = new Map(
    domains.data?.map((domain) => [domain.id, domain.name]),
  )

  return (
    <Container maxWidth="md" component="main" sx={{ py: 6 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Typography variant="h3" component="h1" gutterBottom>
          Documents
        </Typography>
        <Button component={Link} to="/documents/upload" variant="contained">
          Upload documents
        </Button>
      </Stack>
      <Typography color="text.secondary" sx={{ mb: 4 }}>
        Upload source files, inspect extracted text, and continue into parsing.
      </Typography>
      {documents.isPending && <LoadingState label="Loading documents…" />}
      {documents.isError && <ApiErrorAlert error={documents.error} />}
      {documents.isSuccess && documents.data.length === 0 && (
        <EmptyState
          message="No documents have been uploaded yet."
          action={
            <Button component={Link} to="/documents/upload" size="small">
              Upload
            </Button>
          }
        />
      )}
      {documents.isSuccess && (
        <Stack spacing={2}>
          {documents.data.map((document) => (
            <Card variant="outlined" key={document.id}>
              <CardContent>
                <Stack
                  direction="row"
                  justifyContent="space-between"
                  spacing={2}
                >
                  <Typography
                    variant="h6"
                    component="h2"
                    sx={{ overflowWrap: 'anywhere' }}
                  >
                    {document.original_file_name}
                  </Typography>
                  <Chip label={document.processing_status} size="small" />
                </Stack>
                <Typography color="text.secondary">
                  {document.file_type.toUpperCase()} ·{' '}
                  {formatBytes(document.file_size)} ·{' '}
                  {document.domain_id
                    ? (domainNames.get(document.domain_id) ?? 'Unknown domain')
                    : 'Unassigned'}
                </Typography>
                <Button
                  component={Link}
                  to={`/documents/${document.id}`}
                  sx={{ mt: 2 }}
                >
                  View details
                </Button>
                {document.processing_status === 'succeeded' && (
                  <Button
                    component={Link}
                    to={`/parse?document=${document.id}`}
                    sx={{ mt: 2 }}
                  >
                    Run parsing
                  </Button>
                )}
              </CardContent>
            </Card>
          ))}
        </Stack>
      )}
    </Container>
  )
}
