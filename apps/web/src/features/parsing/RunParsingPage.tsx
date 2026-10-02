import { useMutation, useQuery } from '@tanstack/react-query'
import {
  Alert,
  Button,
  Checkbox,
  CircularProgress,
  Container,
  FormControlLabel,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { listDocuments } from '../../api/documents'
import {
  getParsingJob,
  listParsingJobs,
  runParsingJob,
} from '../../api/parsing'
import { isJobActive } from '../../api/jobs'
import { listTemplates } from '../../api/templates'
import { ApiErrorAlert } from '../../components/ApiErrorAlert'
import { ParsingResults } from './ParsingResults'

export function RunParsingPage() {
  const [searchParams] = useSearchParams()
  const [documentId, setDocumentId] = useState(
    searchParams.get('document') ?? '',
  )
  const [templateId, setTemplateId] = useState(
    searchParams.get('template') ?? '',
  )
  const [override, setOverride] = useState(false)
  const [strategy, setStrategy] = useState<'per_column' | 'batch'>('per_column')
  const [requestKey, setRequestKey] = useState(() => crypto.randomUUID())
  const documents = useQuery({
    queryKey: ['documents'],
    queryFn: ({ signal }) => listDocuments(signal),
  })
  const templates = useQuery({
    queryKey: ['templates'],
    queryFn: ({ signal }) => listTemplates({ status: 'published' }, signal),
  })
  const job = useMutation({
    mutationFn: () =>
      runParsingJob({
        document_id: documentId,
        template_id: templateId,
        confirm_domain_override: override,
        strategy,
        idempotency_key: requestKey,
      }),
    onSuccess: () => setRequestKey(crypto.randomUUID()),
  })
  const savedJob = useQuery({
    queryKey: ['parsing-job', job.data?.id],
    queryFn: ({ signal }) => getParsingJob(job.data!.id, signal),
    enabled: Boolean(job.data),
    refetchInterval: (query) =>
      isJobActive(query.state.data?.status ?? job.data?.status) ? 1000 : false,
  })
  const recentJobs = useQuery({
    queryKey: ['parsing-jobs', job.data?.id],
    queryFn: ({ signal }) => listParsingJobs(signal),
    refetchInterval: (query) =>
      query.state.data?.some((item) => isJobActive(item.status)) ? 2000 : false,
  })
  const eligibleDocuments =
    documents.data?.filter((item) => item.processing_status === 'succeeded') ??
    []
  const publishedTemplates =
    templates.data?.filter((item) => item.status === 'published') ?? []

  return (
    <Container maxWidth="md" component="main" sx={{ py: 6 }}>
      <Typography variant="h3" component="h1" gutterBottom>
        Run parsing
      </Typography>
      <Stack spacing={3}>
        {documents.isPending || templates.isPending ? (
          <CircularProgress aria-label="Loading parsing options" />
        ) : null}
        {documents.error && <ApiErrorAlert error={documents.error} />}
        {templates.error && <ApiErrorAlert error={templates.error} />}
        {documents.isSuccess && eligibleDocuments.length === 0 && (
          <Alert severity="info">
            No extracted documents are ready.{' '}
            <Link to="/documents/upload">Upload a document</Link> first.
          </Alert>
        )}
        {templates.isSuccess && publishedTemplates.length === 0 && (
          <Alert severity="info">
            No published templates are ready.{' '}
            <Link to="/templates/new">Create a template</Link> first.
          </Alert>
        )}
        <TextField
          select
          label="Extracted document"
          value={documentId}
          disabled={documents.isPending || eligibleDocuments.length === 0}
          onChange={(event) => setDocumentId(event.target.value)}
        >
          {eligibleDocuments.map((item) => (
            <MenuItem value={item.id} key={item.id}>
              {item.original_file_name}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          select
          label="Published template"
          value={templateId}
          disabled={templates.isPending || publishedTemplates.length === 0}
          onChange={(event) => setTemplateId(event.target.value)}
        >
          {publishedTemplates.map((item) => (
            <MenuItem value={item.id} key={item.id}>
              {item.name}
            </MenuItem>
          ))}
        </TextField>
        <FormControlLabel
          control={
            <Checkbox
              checked={override}
              onChange={(event) => setOverride(event.target.checked)}
            />
          }
          label="I confirm use of a template from a different or unassigned domain"
        />
        <TextField
          select
          label="Parsing strategy"
          value={strategy}
          onChange={(event) =>
            setStrategy(event.target.value as 'per_column' | 'batch')
          }
        >
          <MenuItem value="per_column">Per column</MenuItem>
          <MenuItem value="batch">Batched columns</MenuItem>
        </TextField>
        <Button
          variant="contained"
          disabled={!documentId || !templateId || job.isPending}
          onClick={() => job.mutate()}
        >
          {job.isPending ? 'Queuing…' : 'Start parsing'}
        </Button>
        {job.isPending && <CircularProgress aria-label="Parsing document" />}
        {job.error && <ApiErrorAlert error={job.error} />}
        {job.data && (
          <>
            <Alert severity="info">
              <Link to={`/parsing-jobs/${job.data.id}`}>
                Open saved job results
              </Link>
            </Alert>
            {savedJob.error && <ApiErrorAlert error={savedJob.error} />}
            <ParsingResults job={savedJob.data ?? job.data} />
          </>
        )}
        <Typography variant="h6" component="h2">
          Recent jobs
        </Typography>
        {recentJobs.error && <ApiErrorAlert error={recentJobs.error} />}
        {recentJobs.data?.map((item) => (
          <Button
            key={item.id}
            component={Link}
            to={`/parsing-jobs/${item.id}`}
            sx={{ justifyContent: 'space-between' }}
          >
            {new Date(item.started_at).toLocaleString()} · {item.id.slice(0, 8)}{' '}
            · {item.status.replaceAll('_', ' ')}
          </Button>
        ))}
      </Stack>
    </Container>
  )
}
