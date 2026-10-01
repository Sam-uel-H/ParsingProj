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
import { runParsingJob } from '../../api/parsing'
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
      }),
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
        <Button
          variant="contained"
          disabled={!documentId || !templateId || job.isPending}
          onClick={() => job.mutate()}
        >
          {job.isPending ? 'Parsing…' : 'Start parsing'}
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
            <ParsingResults job={job.data} />
          </>
        )}
      </Stack>
    </Container>
  )
}
