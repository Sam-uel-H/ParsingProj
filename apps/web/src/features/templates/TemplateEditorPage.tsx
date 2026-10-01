import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Container,
  IconButton,
  MenuItem,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material'
import { ArrowDown, ArrowUp, History, Plus, Tags } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { listDomains, type Domain } from '../../api/domains'
import {
  createTemplate,
  createTemplateVersion,
  getTemplate,
  publishTemplate,
  reorderTemplateColumns,
  updateTemplateDraft,
  type ColumnType,
  type TemplateColumnDraft,
  type TemplateDetail,
} from '../../api/templates'
import { ApiErrorAlert } from '../../components/ApiErrorAlert'

interface EditorColumn {
  id?: string
  name: string
  description: string
  columnType: ColumnType
  enumValues: string
  promptText: string
  displayOrder: number
}

interface EditorErrors {
  name?: string
  domain?: string
  columns?: string
  [field: `column-${number}-${string}`]: string | undefined
}

const columnTypes: ColumnType[] = [
  'string',
  'integer',
  'decimal',
  'currency',
  'date',
  'boolean',
  'enum',
]

function toEditorColumn(column: TemplateColumnDraft): EditorColumn {
  return {
    id: column.id,
    name: column.name,
    description: column.description ?? '',
    columnType: column.column_type,
    enumValues: column.enum_values?.join(', ') ?? '',
    promptText: column.prompt_text ?? '',
    displayOrder: column.display_order,
  }
}

function validate(
  name: string,
  domainId: string,
  columns: EditorColumn[],
  forPublish: boolean,
): EditorErrors {
  const errors: EditorErrors = {}
  if (!name.trim()) errors.name = 'Template name is required.'
  if (!domainId) errors.domain = 'Choose a domain.'
  if (forPublish && columns.length === 0) {
    errors.columns = 'Add at least one column before publishing.'
  }

  const names = new Set<string>()
  columns.forEach((column, index) => {
    const normalizedName = column.name.trim().toLowerCase()
    if (!normalizedName) {
      errors[`column-${index}-name`] = 'Column name is required.'
    } else if (names.has(normalizedName)) {
      errors[`column-${index}-name`] = 'Column names must be unique.'
    }
    names.add(normalizedName)

    if (column.columnType === 'enum') {
      const values = parseEnumValues(column.enumValues)
      if (values.length === 0) {
        errors[`column-${index}-enum`] = 'Enter at least one enum value.'
      } else if (new Set(values).size !== values.length) {
        errors[`column-${index}-enum`] = 'Enum values must be unique.'
      }
    }
    if (forPublish && !column.promptText.trim()) {
      errors[`column-${index}-prompt`] = 'A prompt is required to publish.'
    }
  })
  return errors
}

function parseEnumValues(value: string): string[] {
  return value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function toDraftColumn(column: EditorColumn): TemplateColumnDraft {
  return {
    id: column.id,
    name: column.name.trim(),
    description: column.description.trim() || null,
    column_type: column.columnType,
    enum_values:
      column.columnType === 'enum' ? parseEnumValues(column.enumValues) : null,
    prompt_text: column.promptText.trim() || null,
    display_order: column.displayOrder,
  }
}

interface EditorFormProps {
  domains: Domain[]
  detail?: TemplateDetail
}

function EditorForm({ domains, detail }: EditorFormProps) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const version = detail?.current_version
  const [name, setName] = useState(version?.name ?? '')
  const [description, setDescription] = useState(version?.description ?? '')
  const [domainId, setDomainId] = useState(
    detail?.domain_id ?? domains[0]?.id ?? '',
  )
  const [columns, setColumns] = useState<EditorColumn[]>(
    version?.columns.map(toEditorColumn) ?? [],
  )
  const [errors, setErrors] = useState<EditorErrors>({})
  const [dirty, setDirty] = useState(false)
  const published = version?.status === 'published'
  const archived =
    detail?.archived_at !== null && detail?.archived_at !== undefined
  const readOnly = published || archived

  const acceptResult = (result: TemplateDetail) => {
    queryClient.setQueryData(['template', result.id], result)
    queryClient.invalidateQueries({ queryKey: ['templates'] })
    setDirty(false)
    setErrors({})
  }

  const save = useMutation({
    mutationFn: async () => {
      const nextErrors = validate(name, domainId, columns, false)
      setErrors(nextErrors)
      if (Object.keys(nextErrors).length > 0) throw new Error('form-invalid')
      const draftColumns = columns.map(toDraftColumn)
      if (!detail) {
        return createTemplate({
          domain_id: domainId,
          name: name.trim(),
          description: description.trim() || null,
          columns: draftColumns,
        })
      }
      return updateTemplateDraft(detail.id, {
        domain_id: domainId,
        name: name.trim(),
        description: description.trim() || null,
        expected_lock_version: version!.lock_version,
        columns: draftColumns,
      })
    },
    onSuccess: (result) => {
      acceptResult(result)
      if (!detail) navigate(`/templates/${result.id}`, { replace: true })
    },
  })

  const publish = useMutation({
    mutationFn: async () => {
      const nextErrors = validate(name, domainId, columns, true)
      setErrors(nextErrors)
      if (Object.keys(nextErrors).length > 0) throw new Error('form-invalid')
      return publishTemplate(detail!.id, version!.lock_version)
    },
    onSuccess: acceptResult,
  })

  const createVersion = useMutation({
    mutationFn: () => createTemplateVersion(detail!.id),
    onSuccess: acceptResult,
  })

  const reorder = useMutation({
    mutationFn: (orderedColumns: EditorColumn[]) =>
      reorderTemplateColumns(
        detail!.id,
        version!.lock_version,
        orderedColumns.map((column) => column.id!),
      ),
    onSuccess: acceptResult,
  })

  const markChanged = () => setDirty(true)
  const updateColumn = (index: number, change: Partial<EditorColumn>) => {
    setColumns((current) =>
      current.map((column, position) =>
        position === index ? { ...column, ...change } : column,
      ),
    )
    markChanged()
  }

  const addColumn = () => {
    setColumns((current) => [
      ...current,
      {
        name: '',
        description: '',
        columnType: 'string',
        enumValues: '',
        promptText: '',
        displayOrder: current.length,
      },
    ])
    markChanged()
  }

  const removeColumn = (index: number) => {
    if (!window.confirm('Delete this column from the draft?')) return
    setColumns((current) =>
      current
        .filter((_, position) => position !== index)
        .map((column, displayOrder) => ({ ...column, displayOrder })),
    )
    markChanged()
  }

  const moveColumn = (index: number, direction: -1 | 1) => {
    const destination = index + direction
    if (destination < 0 || destination >= columns.length) return
    const next = [...columns]
    ;[next[index], next[destination]] = [next[destination], next[index]]
    const ordered = next.map((column, displayOrder) => ({
      ...column,
      displayOrder,
    }))
    if (detail && !dirty && ordered.every((column) => column.id)) {
      reorder.mutate(ordered)
      return
    }
    setColumns(ordered)
    markChanged()
  }

  const visibleError = (error: Error | null): Error | null =>
    error instanceof Error && error.message === 'form-invalid' ? null : error

  return (
    <Stack spacing={3}>
      {archived && (
        <Alert severity="info">
          This template is archived and remains available only for historical
          jobs and version review.
        </Alert>
      )}
      {published && !archived && (
        <Alert severity="info">
          This published version is immutable. Create a new version to make
          changes.
        </Alert>
      )}
      {visibleError(save.error) && <ApiErrorAlert error={save.error} />}
      {visibleError(publish.error) && <ApiErrorAlert error={publish.error} />}
      {createVersion.error && <ApiErrorAlert error={createVersion.error} />}
      {reorder.error && <ApiErrorAlert error={reorder.error} />}
      {detail && (
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
          <Button
            component={Link}
            to={`/templates/${detail.id}/history`}
            startIcon={<History size={18} />}
          >
            Version history
          </Button>
          {published && !archived && (
            <Button
              variant="contained"
              startIcon={<Plus size={18} />}
              disabled={createVersion.isPending}
              onClick={() => createVersion.mutate()}
            >
              Create new version
            </Button>
          )}
        </Stack>
      )}
      <Card variant="outlined">
        <CardContent>
          <Stack spacing={2}>
            <TextField
              label="Template name"
              value={name}
              disabled={readOnly}
              error={Boolean(errors.name)}
              helperText={errors.name}
              onChange={(event) => {
                setName(event.target.value)
                markChanged()
              }}
            />
            <TextField
              select
              label="Domain"
              value={domainId}
              disabled={readOnly}
              error={Boolean(errors.domain)}
              helperText={errors.domain}
              onChange={(event) => {
                setDomainId(event.target.value)
                markChanged()
              }}
            >
              {domains.map((domain) => (
                <MenuItem value={domain.id} key={domain.id}>
                  {domain.name}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              label="Description"
              value={description}
              disabled={readOnly}
              multiline
              minRows={2}
              onChange={(event) => {
                setDescription(event.target.value)
                markChanged()
              }}
            />
          </Stack>
        </CardContent>
      </Card>

      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Box>
          <Typography variant="h5" component="h2">
            Columns
          </Typography>
          {errors.columns && (
            <Typography color="error" variant="body2">
              {errors.columns}
            </Typography>
          )}
        </Box>
        {!readOnly && <Button onClick={addColumn}>Add column</Button>}
      </Stack>

      {columns.map((column, index) => (
        <Card variant="outlined" key={column.id ?? `new-${index}`}>
          <CardContent>
            <Stack spacing={2}>
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
                <TextField
                  label="Column name"
                  value={column.name}
                  disabled={readOnly}
                  fullWidth
                  error={Boolean(errors[`column-${index}-name`])}
                  helperText={errors[`column-${index}-name`]}
                  onChange={(event) =>
                    updateColumn(index, { name: event.target.value })
                  }
                />
                <TextField
                  select
                  label="Type"
                  value={column.columnType}
                  disabled={readOnly}
                  sx={{ minWidth: 180 }}
                  onChange={(event) =>
                    updateColumn(index, {
                      columnType: event.target.value as ColumnType,
                    })
                  }
                >
                  {columnTypes.map((type) => (
                    <MenuItem value={type} key={type}>
                      {type}
                    </MenuItem>
                  ))}
                </TextField>
              </Stack>
              <TextField
                label="Description"
                value={column.description}
                disabled={readOnly}
                onChange={(event) =>
                  updateColumn(index, { description: event.target.value })
                }
              />
              {column.columnType === 'enum' && (
                <TextField
                  label="Allowed values"
                  value={column.enumValues}
                  disabled={readOnly}
                  error={Boolean(errors[`column-${index}-enum`])}
                  helperText={
                    errors[`column-${index}-enum`] ??
                    'Separate values with commas or new lines.'
                  }
                  onChange={(event) =>
                    updateColumn(index, { enumValues: event.target.value })
                  }
                />
              )}
              <TextField
                label="Extraction prompt"
                value={column.promptText}
                disabled={readOnly}
                multiline
                minRows={2}
                error={Boolean(errors[`column-${index}-prompt`])}
                helperText={
                  errors[`column-${index}-prompt`] ??
                  'Required when the template is published.'
                }
                onChange={(event) =>
                  updateColumn(index, { promptText: event.target.value })
                }
              />
              {detail && column.id && (
                <Button
                  component={Link}
                  to={`/templates/${detail.id}/prompt-helper?column=${column.id}`}
                  startIcon={<Tags size={18} />}
                  disabled={dirty}
                  sx={{ alignSelf: 'flex-start' }}
                >
                  Prompt Helper
                </Button>
              )}
              {!readOnly && (
                <Stack direction="row" spacing={0.5} alignItems="center">
                  <Tooltip title="Move column up">
                    <span>
                      <IconButton
                        aria-label={`Move ${column.name || 'column'} up`}
                        disabled={index === 0 || reorder.isPending}
                        onClick={() => moveColumn(index, -1)}
                      >
                        <ArrowUp size={19} />
                      </IconButton>
                    </span>
                  </Tooltip>
                  <Tooltip title="Move column down">
                    <span>
                      <IconButton
                        aria-label={`Move ${column.name || 'column'} down`}
                        disabled={
                          index === columns.length - 1 || reorder.isPending
                        }
                        onClick={() => moveColumn(index, 1)}
                      >
                        <ArrowDown size={19} />
                      </IconButton>
                    </span>
                  </Tooltip>
                  <Button color="error" onClick={() => removeColumn(index)}>
                    Delete column
                  </Button>
                </Stack>
              )}
            </Stack>
          </CardContent>
        </Card>
      ))}

      {!readOnly && (
        <Stack direction="row" spacing={2}>
          <Button
            variant="contained"
            onClick={() => save.mutate()}
            disabled={save.isPending || publish.isPending}
          >
            Save draft
          </Button>
          <Button
            variant="outlined"
            onClick={() => publish.mutate()}
            disabled={!detail || dirty || save.isPending || publish.isPending}
          >
            Publish
          </Button>
          {detail && dirty && (
            <Typography color="text.secondary" sx={{ alignSelf: 'center' }}>
              Save changes before publishing.
            </Typography>
          )}
        </Stack>
      )}
    </Stack>
  )
}

export function TemplateEditorPage() {
  const { templateId } = useParams()
  const isNew = templateId === undefined
  const domains = useQuery({
    queryKey: ['domains'],
    queryFn: ({ signal }) => listDomains(signal),
  })
  const template = useQuery({
    queryKey: ['template', templateId],
    queryFn: ({ signal }) => getTemplate(templateId!, signal),
    enabled: !isNew,
  })

  const loading = domains.isPending || (!isNew && template.isPending)
  const error = domains.error ?? template.error

  return (
    <Container maxWidth="md" component="main" sx={{ py: 6 }}>
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="center"
        sx={{ mb: 3 }}
      >
        <Typography variant="h3" component="h1">
          {isNew ? 'New template' : 'Template editor'}
        </Typography>
        <Button component={Link} to="/templates">
          Back to templates
        </Button>
      </Stack>
      {loading && <CircularProgress aria-label="Loading template editor" />}
      {error && <ApiErrorAlert error={error} />}
      {domains.isSuccess && domains.data.length === 0 && (
        <Alert severity="warning">
          Create a domain before creating a template.
        </Alert>
      )}
      {!loading && !error && domains.data && domains.data.length > 0 && (
        <EditorForm
          key={template.data?.current_version.lock_version ?? 'new'}
          domains={domains.data}
          detail={template.data}
        />
      )}
    </Container>
  )
}
