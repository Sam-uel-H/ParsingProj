import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Box,
  Button,
  Card,
  CardActions,
  CardContent,
  Chip,
  Container,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { Archive, Copy, History, Plus, Trash2 } from 'lucide-react'
import { useDeferredValue, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { listDomains } from '../../api/domains'
import {
  archiveTemplate,
  cloneTemplate,
  deleteTemplate,
  listTemplates,
  type TemplateSummary,
} from '../../api/templates'
import { ApiErrorAlert } from '../../components/ApiErrorAlert'
import { EmptyState, LoadingState } from '../../components/AsyncState'

export function TemplatesPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [domainId, setDomainId] = useState('')
  const [author, setAuthor] = useState('')
  const [status, setStatus] = useState<'' | 'draft' | 'published' | 'archived'>(
    '',
  )
  const [cloneSource, setCloneSource] = useState<TemplateSummary | null>(null)
  const [cloneName, setCloneName] = useState('')
  const deferredSearch = useDeferredValue(search.trim())
  const deferredAuthor = useDeferredValue(author.trim())
  const filters = useMemo(
    () => ({
      search: deferredSearch,
      domainId,
      author: deferredAuthor,
      status,
    }),
    [deferredSearch, domainId, deferredAuthor, status],
  )
  const domains = useQuery({
    queryKey: ['domains'],
    queryFn: ({ signal }) => listDomains(signal),
  })
  const templates = useQuery({
    queryKey: ['templates', filters],
    queryFn: ({ signal }) => listTemplates(filters, signal),
  })
  const domainNames = new Map(
    domains.data?.map((domain) => [domain.id, domain.name]) ?? [],
  )
  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: ['templates'] })
  const archiveMutation = useMutation({
    mutationFn: archiveTemplate,
    onSuccess: refresh,
  })
  const deleteMutation = useMutation({
    mutationFn: deleteTemplate,
    onSuccess: refresh,
  })
  const cloneMutation = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) =>
      cloneTemplate(id, name),
    onSuccess: (result) => {
      setCloneSource(null)
      refresh()
      navigate(`/templates/${result.id}`)
    },
  })
  const actionError =
    archiveMutation.error ?? deleteMutation.error ?? cloneMutation.error

  const openClone = (template: TemplateSummary) => {
    setCloneSource(template)
    setCloneName(`${template.name} Copy`)
    cloneMutation.reset()
  }

  return (
    <Container maxWidth="lg" component="main" sx={{ py: 5 }}>
      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        justifyContent="space-between"
        alignItems={{ xs: 'stretch', sm: 'center' }}
        spacing={2}
      >
        <Typography variant="h3" component="h1">
          Templates
        </Typography>
        <Button
          component={Link}
          to="/templates/new"
          variant="contained"
          startIcon={<Plus size={18} />}
        >
          New template
        </Button>
      </Stack>

      <Box
        component="section"
        aria-label="Template filters"
        sx={{
          display: 'grid',
          gridTemplateColumns: {
            xs: '1fr',
            sm: 'minmax(220px, 2fr) minmax(160px, 1fr)',
            md: 'minmax(240px, 2fr) repeat(3, minmax(150px, 1fr))',
          },
          gap: 2,
          py: 3,
        }}
      >
        <TextField
          label="Search name or description"
          value={search}
          size="small"
          onChange={(event) => setSearch(event.target.value)}
        />
        <TextField
          select
          label="Domain"
          value={domainId}
          size="small"
          onChange={(event) => setDomainId(event.target.value)}
        >
          <MenuItem value="">All domains</MenuItem>
          {domains.data?.map((domain) => (
            <MenuItem value={domain.id} key={domain.id}>
              {domain.name}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          label="Author"
          value={author}
          size="small"
          onChange={(event) => setAuthor(event.target.value)}
        />
        <TextField
          select
          label="Status"
          value={status}
          size="small"
          onChange={(event) =>
            setStatus(
              event.target.value as '' | 'draft' | 'published' | 'archived',
            )
          }
        >
          <MenuItem value="">All statuses</MenuItem>
          <MenuItem value="draft">Draft</MenuItem>
          <MenuItem value="published">Published</MenuItem>
          <MenuItem value="archived">Archived</MenuItem>
        </TextField>
      </Box>

      {actionError && <ApiErrorAlert error={actionError} />}
      {templates.isPending && <LoadingState label="Loading templates…" />}
      {templates.isError && <ApiErrorAlert error={templates.error} />}
      {templates.isSuccess && templates.data.length === 0 && (
        <EmptyState
          message={
            search || domainId || author || status
              ? 'No templates match these filters.'
              : 'No templates have been created yet.'
          }
          action={
            !search && !domainId && !author && !status ? (
              <Button component={Link} to="/templates/new" size="small">
                Create one
              </Button>
            ) : undefined
          }
        />
      )}
      {templates.isSuccess && (
        <Stack spacing={2}>
          {templates.data.map((template) => (
            <Card variant="outlined" key={template.id}>
              <CardContent>
                <Stack
                  direction={{ xs: 'column', sm: 'row' }}
                  alignItems={{ xs: 'flex-start', sm: 'center' }}
                  justifyContent="space-between"
                  spacing={1}
                >
                  <Typography variant="h6" component="h2">
                    {template.name}
                  </Typography>
                  <Chip
                    label={`${template.status} v${template.version_number}`}
                    size="small"
                    color={
                      template.status === 'published'
                        ? 'success'
                        : template.status === 'archived'
                          ? 'default'
                          : 'warning'
                    }
                  />
                </Stack>
                <Typography color="text.secondary" sx={{ mt: 0.5 }}>
                  {template.description ?? 'No description'}
                </Typography>
                <Typography
                  variant="body2"
                  color="text.secondary"
                  sx={{ mt: 1 }}
                >
                  {domainNames.get(template.domain_id) ?? 'Unknown domain'} /{' '}
                  {template.created_by_name}
                </Typography>
              </CardContent>
              <CardActions sx={{ px: 2, pb: 2, flexWrap: 'wrap', gap: 0.5 }}>
                <Button component={Link} to={`/templates/${template.id}`}>
                  {template.status === 'draft' ? 'Edit draft' : 'View'}
                </Button>
                <Button
                  component={Link}
                  to={`/templates/${template.id}/history`}
                  startIcon={<History size={17} />}
                >
                  History
                </Button>
                {template.status === 'published' && (
                  <>
                    <Button
                      onClick={() => openClone(template)}
                      startIcon={<Copy size={17} />}
                    >
                      Clone
                    </Button>
                    <Button
                      onClick={() => {
                        if (window.confirm(`Archive ${template.name}?`)) {
                          archiveMutation.mutate(template.id)
                        }
                      }}
                      startIcon={<Archive size={17} />}
                    >
                      Archive
                    </Button>
                    <Button
                      component={Link}
                      to={`/parse?template=${template.id}`}
                    >
                      Use template
                    </Button>
                  </>
                )}
                {template.status !== 'published' && (
                  <Button
                    color="error"
                    onClick={() => {
                      if (window.confirm(`Delete ${template.name}?`)) {
                        deleteMutation.mutate(template.id)
                      }
                    }}
                    startIcon={<Trash2 size={17} />}
                  >
                    Delete
                  </Button>
                )}
              </CardActions>
            </Card>
          ))}
        </Stack>
      )}

      <Dialog
        open={cloneSource !== null}
        onClose={() => setCloneSource(null)}
        fullWidth
        maxWidth="sm"
      >
        <DialogTitle>Clone template</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            fullWidth
            label="New template name"
            value={cloneName}
            margin="dense"
            onChange={(event) => setCloneName(event.target.value)}
          />
          {cloneMutation.error && <ApiErrorAlert error={cloneMutation.error} />}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCloneSource(null)}>Cancel</Button>
          <Button
            variant="contained"
            disabled={!cloneName.trim() || cloneMutation.isPending}
            onClick={() =>
              cloneSource &&
              cloneMutation.mutate({
                id: cloneSource.id,
                name: cloneName.trim(),
              })
            }
          >
            Clone
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  )
}
