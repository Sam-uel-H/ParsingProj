import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Container,
  Paper,
  Stack,
  Typography,
} from '@mui/material'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import {
  documentContentUrl,
  documentPagePreviewUrl,
  extractDocument,
  getDocument,
  getDocumentExtraction,
} from '../../api/documents'
import { ApiErrorAlert } from '../../components/ApiErrorAlert'

export function DocumentDetailPage() {
  const { documentId = '' } = useParams()
  const queryClient = useQueryClient()
  const [pageNumber, setPageNumber] = useState(1)
  const [zoom, setZoom] = useState(100)
  const [mode, setMode] = useState<'preview' | 'text'>('preview')
  const document = useQuery({
    queryKey: ['document', documentId],
    queryFn: ({ signal }) => getDocument(documentId, signal),
  })
  const extraction = useQuery({
    queryKey: ['document-extraction', documentId],
    queryFn: ({ signal }) => getDocumentExtraction(documentId, signal),
    enabled: Boolean(document.data?.active_extraction_id),
  })
  const startExtraction = useMutation({
    mutationFn: () => extractDocument(documentId),
    onSuccess: (result) => {
      queryClient.setQueryData(['document-extraction', documentId], result)
      queryClient.invalidateQueries({ queryKey: ['document', documentId] })
      queryClient.invalidateQueries({ queryKey: ['documents'] })
    },
  })
  const currentPage = extraction.data?.pages.find(
    (page) => page.page_number === pageNumber,
  )
  const pageCount = extraction.data?.pages.length ?? 0

  return (
    <Container maxWidth="lg" component="main" sx={{ py: 6 }}>
      <Button component={Link} to="/documents" sx={{ mb: 2 }}>
        Back to documents
      </Button>
      {document.isPending && <CircularProgress aria-label="Loading document" />}
      {document.isError && <ApiErrorAlert error={document.error} />}
      {document.isSuccess && (
        <Stack spacing={3}>
          <Typography
            variant="h3"
            component="h1"
            sx={{ overflowWrap: 'anywhere' }}
          >
            {document.data.original_file_name}
          </Typography>
          <Card variant="outlined">
            <CardContent>
              <Stack spacing={1}>
                <Typography>
                  Type: {document.data.file_type.toUpperCase()}
                </Typography>
                <Typography>
                  Size: {document.data.file_size.toLocaleString()} bytes
                </Typography>
                <Typography>
                  Upload status: {document.data.upload_status}
                </Typography>
                <Typography>
                  Extraction status: {document.data.processing_status}
                </Typography>
                <Typography sx={{ overflowWrap: 'anywhere' }}>
                  SHA-256: {document.data.checksum_sha256}
                </Typography>
              </Stack>
            </CardContent>
          </Card>
          {document.data.processing_status === 'pending' && (
            <Button
              variant="contained"
              disabled={startExtraction.isPending}
              onClick={() => startExtraction.mutate()}
            >
              {startExtraction.isPending ? 'Extracting…' : 'Start extraction'}
            </Button>
          )}
          {startExtraction.error && (
            <ApiErrorAlert error={startExtraction.error} />
          )}
          {extraction.isPending && document.data.active_extraction_id && (
            <CircularProgress aria-label="Loading extraction" />
          )}
          {extraction.data?.status === 'failed' && (
            <Alert severity="error">
              {extraction.data.error_message ?? 'Document extraction failed.'}{' '}
              The original file remains available.
            </Alert>
          )}
          {extraction.data?.status === 'succeeded' && currentPage && (
            <Stack spacing={2}>
              <Stack direction="row" spacing={1} flexWrap="wrap">
                <Button
                  onClick={() => setMode('preview')}
                  variant={mode === 'preview' ? 'contained' : 'outlined'}
                >
                  Page preview
                </Button>
                <Button
                  onClick={() => setMode('text')}
                  variant={mode === 'text' ? 'contained' : 'outlined'}
                >
                  Extracted text
                </Button>
                <Button
                  disabled={pageNumber <= 1}
                  onClick={() => setPageNumber((value) => value - 1)}
                >
                  Previous
                </Button>
                <Typography sx={{ alignSelf: 'center' }}>
                  Page {pageNumber} of {pageCount}
                </Typography>
                <Button
                  disabled={pageNumber >= pageCount}
                  onClick={() => setPageNumber((value) => value + 1)}
                >
                  Next
                </Button>
                <Button
                  disabled={zoom <= 50}
                  onClick={() => setZoom((value) => value - 25)}
                >
                  Zoom out
                </Button>
                <Typography sx={{ alignSelf: 'center' }}>{zoom}%</Typography>
                <Button
                  disabled={zoom >= 200}
                  onClick={() => setZoom((value) => value + 25)}
                >
                  Zoom in
                </Button>
              </Stack>
              <Paper
                variant="outlined"
                sx={{ overflow: 'auto', p: 2, minHeight: 400 }}
              >
                {mode === 'text' ? (
                  <Box component="pre" sx={{ whiteSpace: 'pre-wrap', m: 0 }}>
                    {currentPage.text ||
                      'No machine-readable text was returned for this page.'}
                  </Box>
                ) : currentPage.preview_content_type === 'application/pdf' ? (
                  <iframe
                    title={`Page ${pageNumber} preview`}
                    src={`${documentPagePreviewUrl(documentId, pageNumber)}#page=${pageNumber}&zoom=${zoom}`}
                    style={{ width: '100%', height: 700, border: 0 }}
                  />
                ) : (
                  <img
                    alt={`Page ${pageNumber} preview`}
                    src={documentPagePreviewUrl(documentId, pageNumber)}
                    style={{
                      width: `${zoom}%`,
                      height: 'auto',
                      display: 'block',
                      margin: 'auto',
                    }}
                  />
                )}
              </Paper>
            </Stack>
          )}
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
            <Button
              component="a"
              href={documentContentUrl(document.data.id)}
              variant="outlined"
            >
              Download original
            </Button>
            {document.data.processing_status === 'succeeded' && (
              <Button
                component={Link}
                to={`/parse?document=${document.data.id}`}
                variant="contained"
              >
                Run parsing
              </Button>
            )}
          </Stack>
        </Stack>
      )}
    </Container>
  )
}
