import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Box,
  Button,
  Container,
  IconButton,
  MenuItem,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material'
import {
  ChevronLeft,
  ChevronRight,
  Trash2,
  ZoomIn,
  ZoomOut,
} from 'lucide-react'
import { useEffect, useMemo, useState, type CSSProperties } from 'react'
import { Link, useBlocker, useParams, useSearchParams } from 'react-router-dom'

import {
  getDocumentExtraction,
  listDocuments,
  type DocumentPageRecord,
} from '../../api/documents'
import {
  createTaggedExample,
  deleteTaggedExample,
  listTaggedExamples,
  replaceTaggedExample,
  type SelectionRectangle,
  type TaggedExample,
  type TaggedExampleWrite,
} from '../../api/taggedExamples'
import { getTemplate } from '../../api/templates'
import type { DryRunEvidence } from '../../api/promptDrafts'
import { ApiErrorAlert } from '../../components/ApiErrorAlert'
import { EmptyState, LoadingState } from '../../components/AsyncState'
import { PdfSelectablePage } from './PdfSelectablePage'
import { PromptWorkspace } from './PromptWorkspace'
import './promptHelper.css'

interface CapturedSelection {
  text: string
  rectangles: SelectionRectangle[]
  pageNumber: number
}

function captureSelection(
  element: HTMLElement,
  pageNumber: number,
): CapturedSelection | null {
  const selection = window.getSelection()
  if (!selection || selection.isCollapsed || selection.rangeCount !== 1)
    return null
  const range = selection.getRangeAt(0)
  if (!element.contains(range.commonAncestorContainer)) return null
  const text = selection.toString().trim()
  const bounds = element.getBoundingClientRect()
  if (!text || !bounds.width || !bounds.height) return null
  const rectangles = Array.from(range.getClientRects())
    .map((rect) => {
      const left = Math.max(bounds.left, rect.left)
      const top = Math.max(bounds.top, rect.top)
      const right = Math.min(bounds.right, rect.right)
      const bottom = Math.min(bounds.bottom, rect.bottom)
      return {
        x: (left - bounds.left) / bounds.width,
        y: (top - bounds.top) / bounds.height,
        width: (right - left) / bounds.width,
        height: (bottom - top) / bounds.height,
      }
    })
    .filter((rect) => rect.width > 0 && rect.height > 0)
  if (rectangles.length === 0) return null
  return { text, rectangles, pageNumber }
}

function markedText(
  page: DocumentPageRecord,
  pageStart: number,
  tags: TaggedExample[],
  evidence: DryRunEvidence | null,
) {
  const boundaries = new Set([0, page.text.length])
  const highlights =
    evidence?.page_number === page.page_number ? [...tags, evidence] : tags
  for (const tag of highlights) {
    boundaries.add(
      Math.max(0, Math.min(page.text.length, tag.char_start - pageStart)),
    )
    boundaries.add(
      Math.max(0, Math.min(page.text.length, tag.char_end - pageStart)),
    )
  }
  const positions = [...boundaries].sort((a, b) => a - b)
  return positions.slice(0, -1).map((start, index) => {
    const end = positions[index + 1]
    const value = page.text.slice(start, end)
    const tagged = highlights.some(
      (tag) =>
        tag.char_start - pageStart < end && tag.char_end - pageStart > start,
    )
    return tagged ? (
      <mark key={start}>{value}</mark>
    ) : (
      <span key={start}>{value}</span>
    )
  })
}

export function PromptHelperPage() {
  const { templateId = '' } = useParams()
  const [params, setParams] = useSearchParams()
  const [pageNumber, setPageNumber] = useState(1)
  const [zoom, setZoom] = useState(100)
  const [view, setView] = useState<'document' | 'text'>('document')
  const [split, setSplit] = useState(64)
  const [selection, setSelection] = useState<CapturedSelection | null>(null)
  const [expectedValue, setExpectedValue] = useState('')
  const [promptDirty, setPromptDirty] = useState(false)
  const [evidence, setEvidence] = useState<DryRunEvidence | null>(null)
  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      promptDirty && currentLocation.pathname !== nextLocation.pathname,
  )
  const queryClient = useQueryClient()
  const template = useQuery({
    queryKey: ['template', templateId],
    queryFn: ({ signal }) => getTemplate(templateId, signal),
  })
  const documents = useQuery({
    queryKey: ['documents'],
    queryFn: ({ signal }) => listDocuments(signal),
  })
  const compatibleDocuments = useMemo(
    () =>
      documents.data?.filter(
        (document) =>
          document.domain_id === template.data?.domain_id &&
          document.processing_status === 'succeeded' &&
          document.active_extraction_id,
      ) ?? [],
    [documents.data, template.data?.domain_id],
  )
  const requestedDocumentId = params.get('document')
  const documentId =
    compatibleDocuments.find((item) => item.id === requestedDocumentId)?.id ??
    compatibleDocuments[0]?.id ??
    ''
  const columns = template.data?.current_version.columns ?? []
  const requestedColumnId = params.get('column')
  const columnId =
    columns.find((item) => item.id === requestedColumnId)?.id ??
    columns[0]?.id ??
    ''
  const document = compatibleDocuments.find((item) => item.id === documentId)
  const extraction = useQuery({
    queryKey: ['document-extraction', documentId],
    queryFn: ({ signal }) => getDocumentExtraction(documentId, signal),
    enabled: Boolean(document),
  })
  const tags = useQuery({
    queryKey: ['tagged-examples', templateId, documentId],
    queryFn: ({ signal }) => listTaggedExamples(templateId, documentId, signal),
    enabled: Boolean(document),
  })
  const activeExtractionId = extraction.data?.id
  const currentTags =
    tags.data?.filter(
      (tag) => tag.document_extraction_id === activeExtractionId,
    ) ?? []
  const currentTag = currentTags.find(
    (tag) => tag.template_column_id === columnId,
  )
  const currentPage = extraction.data?.pages.find(
    (page) => page.page_number === pageNumber,
  )
  const pageStart =
    extraction.data?.pages
      .filter((page) => page.page_number < pageNumber)
      .reduce((total, page) => total + page.text.length + 1, 0) ?? 0
  const pageTags = currentTags.filter((tag) => tag.page_number === pageNumber)
  const isPdf = document?.file_type === 'pdf'
  const canTag =
    template.data?.current_version.status === 'draft' &&
    !template.data.archived_at

  useEffect(() => {
    setPageNumber(1)
    setSelection(null)
    setExpectedValue('')
  }, [documentId])

  useEffect(() => {
    if (!promptDirty) return
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [promptDirty])

  useEffect(() => {
    if (blocker.state !== 'blocked') return
    if (window.confirm('Discard unsaved prompt edits?')) blocker.proceed()
    else blocker.reset()
  }, [blocker])

  const refreshTags = () =>
    queryClient.invalidateQueries({
      queryKey: ['tagged-examples', templateId, documentId],
    })
  const saveTag = useMutation({
    mutationFn: (data: TaggedExampleWrite) =>
      currentTag
        ? replaceTaggedExample(templateId, currentTag.id, data)
        : createTaggedExample(templateId, data),
    onSuccess: () => {
      setSelection(null)
      refreshTags()
    },
  })
  const removeTag = useMutation({
    mutationFn: (tagId: string) => deleteTaggedExample(templateId, tagId),
    onSuccess: refreshTags,
  })

  const changeParams = (key: 'document' | 'column', value: string) => {
    if (promptDirty && !window.confirm('Discard unsaved prompt edits?')) return
    const next = new URLSearchParams(params)
    next.set(key, value)
    setParams(next)
    setSelection(null)
    setEvidence(null)
    saveTag.reset()
  }
  const acceptSelection = (element: HTMLElement) => {
    if (!canTag) return
    const captured = captureSelection(element, pageNumber)
    if (!captured) return
    setSelection(captured)
    setExpectedValue(captured.text)
  }
  const submitTag = () => {
    if (!selection || !activeExtractionId || !documentId || !columnId) return
    saveTag.mutate({
      template_column_id: columnId,
      document_id: documentId,
      document_extraction_id: activeExtractionId,
      page_number: selection.pageNumber,
      selected_text: selection.text,
      expected_value: expectedValue.trim(),
      rectangles: selection.rectangles,
    })
  }
  const resize = (clientX: number, container: HTMLElement) => {
    const bounds = container.getBoundingClientRect()
    setSplit(
      Math.min(
        80,
        Math.max(35, ((clientX - bounds.left) / bounds.width) * 100),
      ),
    )
  }

  return (
    <Container
      maxWidth={false}
      component="main"
      sx={{ py: 3, px: { xs: 2, md: 3 } }}
    >
      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        justifyContent="space-between"
        spacing={1}
        sx={{ mb: 2 }}
      >
        <div>
          <Typography variant="h4" component="h1">
            Prompt Helper
          </Typography>
          <Typography color="text.secondary">
            {template.data?.current_version.name}
          </Typography>
        </div>
        <Button component={Link} to={`/templates/${templateId}`}>
          Back to template
        </Button>
      </Stack>
      {template.isPending && <LoadingState label="Loading template…" />}
      {template.error && <ApiErrorAlert error={template.error} />}
      {documents.error && <ApiErrorAlert error={documents.error} />}
      {template.isSuccess &&
        documents.isSuccess &&
        compatibleDocuments.length === 0 && (
          <EmptyState
            message="No extracted documents match this template domain."
            action={
              <Button component={Link} to="/documents/upload">
                Upload document
              </Button>
            }
          />
        )}
      {template.isSuccess && compatibleDocuments.length > 0 && (
        <>
          {!canTag && (
            <Alert severity="info" sx={{ mb: 2 }}>
              This template version is read-only.
            </Alert>
          )}
          <Box
            className="prompt-helper-layout"
            style={{ '--split': `${split}%` } as CSSProperties}
          >
            <Box className="prompt-helper-source">
              <Stack
                direction="row"
                spacing={1}
                alignItems="center"
                flexWrap="wrap"
                useFlexGap
                sx={{ mb: 2 }}
              >
                <TextField
                  select
                  label="Sample document"
                  size="small"
                  value={documentId}
                  onChange={(event) =>
                    changeParams('document', event.target.value)
                  }
                  sx={{ minWidth: 210, flexGrow: 1, maxWidth: 420 }}
                >
                  {compatibleDocuments.map((item) => (
                    <MenuItem key={item.id} value={item.id}>
                      {item.original_file_name}
                    </MenuItem>
                  ))}
                </TextField>
                {isPdf && (
                  <Stack direction="row" spacing={0.5}>
                    <Button
                      variant={view === 'document' ? 'contained' : 'outlined'}
                      onClick={() => setView('document')}
                    >
                      PDF
                    </Button>
                    <Button
                      variant={view === 'text' ? 'contained' : 'outlined'}
                      onClick={() => setView('text')}
                    >
                      Extracted text
                    </Button>
                  </Stack>
                )}
              </Stack>
              {extraction.isPending && (
                <LoadingState label="Loading extraction…" />
              )}
              {extraction.error && <ApiErrorAlert error={extraction.error} />}
              {extraction.data && currentPage && (
                <>
                  <Stack
                    direction="row"
                    spacing={0.5}
                    alignItems="center"
                    sx={{ mb: 1 }}
                  >
                    <Tooltip title="Previous page">
                      <span>
                        <IconButton
                          aria-label="Previous page"
                          disabled={pageNumber <= 1}
                          onClick={() => {
                            setPageNumber(pageNumber - 1)
                            setSelection(null)
                          }}
                        >
                          <ChevronLeft size={18} />
                        </IconButton>
                      </span>
                    </Tooltip>
                    <Typography sx={{ minWidth: 90, textAlign: 'center' }}>
                      Page {pageNumber} / {extraction.data.pages.length}
                    </Typography>
                    <Tooltip title="Next page">
                      <span>
                        <IconButton
                          aria-label="Next page"
                          disabled={pageNumber >= extraction.data.pages.length}
                          onClick={() => {
                            setPageNumber(pageNumber + 1)
                            setSelection(null)
                          }}
                        >
                          <ChevronRight size={18} />
                        </IconButton>
                      </span>
                    </Tooltip>
                    {isPdf && view === 'document' && (
                      <>
                        <Tooltip title="Zoom out">
                          <span>
                            <IconButton
                              aria-label="Zoom out"
                              disabled={zoom <= 75}
                              onClick={() => setZoom(zoom - 25)}
                            >
                              <ZoomOut size={18} />
                            </IconButton>
                          </span>
                        </Tooltip>
                        <Typography>{zoom}%</Typography>
                        <Tooltip title="Zoom in">
                          <span>
                            <IconButton
                              aria-label="Zoom in"
                              disabled={zoom >= 175}
                              onClick={() => setZoom(zoom + 25)}
                            >
                              <ZoomIn size={18} />
                            </IconButton>
                          </span>
                        </Tooltip>
                      </>
                    )}
                  </Stack>
                  <Box className="prompt-helper-page-scroll">
                    {isPdf && view === 'document' ? (
                      <PdfSelectablePage
                        documentId={documentId}
                        pageNumber={pageNumber}
                        zoom={zoom}
                        onSelection={acceptSelection}
                        highlights={[
                          ...pageTags.flatMap((tag) => tag.rectangles),
                          ...(evidence?.page_number === pageNumber
                            ? evidence.rectangles
                            : []),
                        ]}
                      />
                    ) : (
                      <Box
                        component="pre"
                        className="prompt-helper-text-page"
                        aria-label={`Selectable extracted text page ${pageNumber}`}
                        onMouseUp={(event) =>
                          acceptSelection(event.currentTarget)
                        }
                        onKeyUp={(event) =>
                          acceptSelection(event.currentTarget)
                        }
                      >
                        {markedText(currentPage, pageStart, pageTags, evidence)}
                      </Box>
                    )}
                  </Box>
                </>
              )}
            </Box>
            <Box
              className="prompt-helper-divider"
              role="separator"
              aria-label="Resize document and columns"
              aria-orientation="vertical"
              aria-valuenow={split}
              aria-valuemin={35}
              aria-valuemax={80}
              tabIndex={0}
              onPointerDown={(event) =>
                event.currentTarget.setPointerCapture(event.pointerId)
              }
              onPointerMove={(event) => {
                if (event.currentTarget.hasPointerCapture(event.pointerId)) {
                  resize(event.clientX, event.currentTarget.parentElement!)
                }
              }}
              onKeyDown={(event) => {
                if (event.key === 'ArrowLeft') setSplit(Math.max(35, split - 5))
                if (event.key === 'ArrowRight')
                  setSplit(Math.min(80, split + 5))
              }}
            />
            <Box className="prompt-helper-columns">
              <Typography variant="h6" component="h2" sx={{ mb: 1 }}>
                Columns
              </Typography>
              <TextField
                select
                fullWidth
                size="small"
                label="Active column"
                value={columnId}
                onChange={(event) => changeParams('column', event.target.value)}
              >
                {columns.map((column) => (
                  <MenuItem key={column.id} value={column.id}>
                    {column.name}
                  </MenuItem>
                ))}
              </TextField>
              <Stack spacing={1} sx={{ mt: 2 }}>
                {columns.map((column) => {
                  const tag = currentTags.find(
                    (item) => item.template_column_id === column.id,
                  )
                  return (
                    <Button
                      key={column.id}
                      variant={column.id === columnId ? 'contained' : 'text'}
                      onClick={() => {
                        changeParams('column', column.id)
                        if (tag) setPageNumber(tag.page_number)
                      }}
                      sx={{
                        justifyContent: 'space-between',
                        gap: 1,
                        textTransform: 'none',
                        textAlign: 'left',
                      }}
                    >
                      <span>{column.name}</span>
                      {tag && <span>Page {tag.page_number}</span>}
                    </Button>
                  )
                })}
              </Stack>
              {selection && (
                <Box className="prompt-helper-selection">
                  <Typography variant="subtitle2">Selected text</Typography>
                  <Typography sx={{ overflowWrap: 'anywhere', mb: 1 }}>
                    {selection.text}
                  </Typography>
                  <TextField
                    fullWidth
                    label="Expected value"
                    value={expectedValue}
                    onChange={(event) => setExpectedValue(event.target.value)}
                  />
                  <Button
                    variant="contained"
                    sx={{ mt: 1 }}
                    disabled={
                      !canTag || !expectedValue.trim() || saveTag.isPending
                    }
                    onClick={submitTag}
                  >
                    {currentTag ? 'Replace tag' : 'Save tag'}
                  </Button>
                </Box>
              )}
              {currentTag && (
                <Box className="prompt-helper-current-tag">
                  <Typography variant="subtitle2">Saved tag</Typography>
                  <Typography sx={{ overflowWrap: 'anywhere' }}>
                    {currentTag.tagged_value}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Expected: {currentTag.expected_value}
                  </Typography>
                  <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                    <Button
                      onClick={() => setPageNumber(currentTag.page_number)}
                    >
                      Page {currentTag.page_number}
                    </Button>
                    {canTag && (
                      <Tooltip title="Delete saved tag">
                        <IconButton
                          aria-label="Delete saved tag"
                          color="error"
                          disabled={removeTag.isPending}
                          onClick={() => removeTag.mutate(currentTag.id)}
                        >
                          <Trash2 size={18} />
                        </IconButton>
                      </Tooltip>
                    )}
                  </Stack>
                </Box>
              )}
              {tags.data?.some(
                (tag) => tag.document_extraction_id !== activeExtractionId,
              ) && (
                <Alert severity="info" sx={{ mt: 2 }}>
                  Tags from an older extraction remain linked to that extraction
                  and are not shown on this page.
                </Alert>
              )}
              {canTag && activeExtractionId && columnId && (
                <PromptWorkspace
                  templateId={templateId}
                  columnId={columnId}
                  documentId={documentId}
                  extractionId={activeExtractionId}
                  lockVersion={template.data.current_version.lock_version}
                  hasTag={Boolean(currentTag)}
                  onDirtyChange={setPromptDirty}
                  onEvidence={(result) => {
                    setEvidence(result)
                    setPageNumber(result.page_number)
                  }}
                />
              )}
              {saveTag.error && <ApiErrorAlert error={saveTag.error} />}
              {removeTag.error && <ApiErrorAlert error={removeTag.error} />}
              {tags.error && <ApiErrorAlert error={tags.error} />}
            </Box>
          </Box>
        </>
      )}
    </Container>
  )
}
