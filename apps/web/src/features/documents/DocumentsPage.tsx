import { useQuery } from '@tanstack/react-query'
import {
  Alert,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Container,
  Stack,
  Typography,
} from '@mui/material'
import { Link } from 'react-router-dom'

import { listDocuments } from '../../api/documents'
import { listDomains } from '../../api/domains'
import { ApiErrorAlert } from '../../components/ApiErrorAlert'

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function DocumentsPage() {
  const documents = useQuery({
    queryKey: ['documents'],
    queryFn: ({ signal }) => listDocuments(signal),
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
        Original files are stored safely while extraction remains pending for
        Phase 4.
      </Typography>
      {documents.isPending && (
        <CircularProgress aria-label="Loading documents" />
      )}
      {documents.isError && <ApiErrorAlert error={documents.error} />}
      {documents.isSuccess && documents.data.length === 0 && (
        <Alert severity="info">No documents have been uploaded yet.</Alert>
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
              </CardContent>
            </Card>
          ))}
        </Stack>
      )}
    </Container>
  )
}
