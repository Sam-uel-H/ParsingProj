import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Button,
  Card,
  CardContent,
  Container,
  LinearProgress,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import {
  extractDocument,
  uploadDocuments,
  type DocumentUploadResult,
} from '../../api/documents'
import { listDomains } from '../../api/domains'
import { ApiErrorAlert } from '../../components/ApiErrorAlert'

interface UploadItem {
  key: string
  file: File
  progress: number
  state: 'ready' | 'uploading' | 'complete' | 'failed'
  result?: DocumentUploadResult
  error?: unknown
}

function fileKey(file: File, index: number): string {
  return `${file.name}-${file.size}-${file.lastModified}-${index}`
}

export function DocumentUploadPage() {
  const queryClient = useQueryClient()
  const domains = useQuery({
    queryKey: ['domains'],
    queryFn: ({ signal }) => listDomains(signal),
  })
  const [domainId, setDomainId] = useState('')
  const [items, setItems] = useState<UploadItem[]>([])
  const uploading = items.some((item) => item.state === 'uploading')

  const updateItem = (key: string, change: Partial<UploadItem>) => {
    setItems((current) =>
      current.map((item) => (item.key === key ? { ...item, ...change } : item)),
    )
  }

  const selectFiles = (files: FileList | null) => {
    setItems(
      Array.from(files ?? []).map((file, index) => ({
        key: fileKey(file, index),
        file,
        progress: 0,
        state: 'ready',
      })),
    )
  }

  const uploadAll = async () => {
    const ready = items.filter(
      (item) => item.state === 'ready' || item.state === 'failed',
    )
    await Promise.all(
      ready.map(async (item) => {
        updateItem(item.key, {
          state: 'uploading',
          progress: 0,
          error: undefined,
        })
        try {
          const batch = await uploadDocuments(
            [item.file],
            domainId || null,
            (progress) => updateItem(item.key, { progress }),
          )
          const result = batch.results[0]
          if (result?.success && result.document) {
            try {
              await extractDocument(result.document.id)
            } catch (error) {
              updateItem(item.key, { error })
            }
          }
          updateItem(item.key, {
            state: result?.success ? 'complete' : 'failed',
            progress: 100,
            result,
          })
        } catch (error) {
          updateItem(item.key, { state: 'failed', error })
        }
      }),
    )
    queryClient.invalidateQueries({ queryKey: ['documents'] })
  }

  return (
    <Container maxWidth="md" component="main" sx={{ py: 6 }}>
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="center"
        sx={{ mb: 3 }}
      >
        <Typography variant="h3" component="h1">
          Upload documents
        </Typography>
        <Button component={Link} to="/documents">
          Back to documents
        </Button>
      </Stack>
      <Stack spacing={3}>
        <TextField
          select
          label="Domain (optional)"
          value={domainId}
          disabled={uploading}
          onChange={(event) => setDomainId(event.target.value)}
        >
          <MenuItem value="">Unassigned</MenuItem>
          {domains.data?.map((domain) => (
            <MenuItem value={domain.id} key={domain.id}>
              {domain.name}
            </MenuItem>
          ))}
        </TextField>
        {domains.isError && <ApiErrorAlert error={domains.error} />}
        <Button component="label" variant="outlined" disabled={uploading}>
          Choose files
          <input
            hidden
            type="file"
            multiple
            aria-label="Document files"
            accept=".pdf,.docx,.tif,.tiff,.png,.jpg,.jpeg,.txt"
            onChange={(event) => selectFiles(event.target.files)}
          />
        </Button>
        <Typography color="text.secondary">
          Supported: PDF, DOCX, TIFF, PNG, JPG, and UTF-8 plain text. Maximum
          size is configured by the backend.
        </Typography>
        {items.length === 0 && (
          <Alert severity="info">Choose one or more files.</Alert>
        )}
        {items.map((item) => (
          <Card variant="outlined" key={item.key}>
            <CardContent>
              <Typography sx={{ overflowWrap: 'anywhere' }}>
                {item.file.name}
              </Typography>
              <Typography color="text.secondary" variant="body2">
                {item.state}
              </Typography>
              {(item.state === 'uploading' || item.progress > 0) && (
                <LinearProgress
                  variant="determinate"
                  value={item.progress}
                  aria-label={`${item.file.name} upload progress`}
                  sx={{ my: 1 }}
                />
              )}
              {item.result?.error && (
                <Alert severity="error" sx={{ mt: 1 }}>
                  {item.result.error.message}
                </Alert>
              )}
              {item.error !== undefined && <ApiErrorAlert error={item.error} />}
              {item.result?.success && (
                <Alert
                  severity="success"
                  sx={{ mt: 1 }}
                  action={
                    item.result.document ? (
                      <Button
                        component={Link}
                        to={`/documents/${item.result.document.id}`}
                        size="small"
                      >
                        Open document
                      </Button>
                    ) : undefined
                  }
                >
                  {item.error !== undefined
                    ? 'Upload completed. Extraction could not be queued.'
                    : 'Upload completed. Extraction queued.'}
                </Alert>
              )}
            </CardContent>
          </Card>
        ))}
        <Button
          variant="contained"
          disabled={items.length === 0 || uploading}
          onClick={() => void uploadAll()}
        >
          Upload selected files
        </Button>
      </Stack>
    </Container>
  )
}
