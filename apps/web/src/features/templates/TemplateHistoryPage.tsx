import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Button,
  Chip,
  Container,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material'
import { ChevronDown, Plus } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import {
  createTemplateVersion,
  getTemplate,
  listTemplateVersions,
} from '../../api/templates'
import { ApiErrorAlert } from '../../components/ApiErrorAlert'
import { EmptyState, LoadingState } from '../../components/AsyncState'

function formatDate(value: string | null): string {
  return value ? new Date(value).toLocaleString() : 'Not published'
}

export function TemplateHistoryPage() {
  const { templateId = '' } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const template = useQuery({
    queryKey: ['template', templateId],
    queryFn: ({ signal }) => getTemplate(templateId, signal),
  })
  const versions = useQuery({
    queryKey: ['template-versions', templateId],
    queryFn: ({ signal }) => listTemplateVersions(templateId, signal),
  })
  const createVersion = useMutation({
    mutationFn: () => createTemplateVersion(templateId),
    onSuccess: (result) => {
      queryClient.setQueryData(['template', templateId], result)
      queryClient.invalidateQueries({ queryKey: ['templates'] })
      queryClient.invalidateQueries({
        queryKey: ['template-versions', templateId],
      })
      navigate(`/templates/${templateId}`)
    },
  })
  const current = template.data?.current_version
  const canCreateVersion =
    template.data?.archived_at === null && current?.status === 'published'

  return (
    <Container maxWidth="lg" component="main" sx={{ py: 5 }}>
      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        justifyContent="space-between"
        alignItems={{ xs: 'stretch', sm: 'center' }}
        spacing={2}
        sx={{ mb: 3 }}
      >
        <div>
          <Typography variant="h3" component="h1">
            Version history
          </Typography>
          {current && (
            <Typography color="text.secondary">{current.name}</Typography>
          )}
        </div>
        <Stack direction="row" spacing={1}>
          <Button component={Link} to={`/templates/${templateId}`}>
            Open template
          </Button>
          {canCreateVersion && (
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
      </Stack>

      {template.data?.archived_at && (
        <Alert severity="info" sx={{ mb: 2 }}>
          This template is archived. Its version history remains available for
          historical jobs.
        </Alert>
      )}
      {createVersion.error && <ApiErrorAlert error={createVersion.error} />}
      {(template.isPending || versions.isPending) && (
        <LoadingState label="Loading version history…" />
      )}
      {template.error && <ApiErrorAlert error={template.error} />}
      {versions.error && <ApiErrorAlert error={versions.error} />}
      {versions.isSuccess && versions.data.length === 0 && (
        <EmptyState message="This template does not have any versions." />
      )}
      {versions.isSuccess && (
        <Stack spacing={1.5}>
          {versions.data.map((version, index) => (
            <Accordion
              key={version.id}
              defaultExpanded={index === 0}
              disableGutters
            >
              <AccordionSummary expandIcon={<ChevronDown size={19} />}>
                <Stack
                  direction={{ xs: 'column', sm: 'row' }}
                  spacing={1.5}
                  alignItems={{ xs: 'flex-start', sm: 'center' }}
                  sx={{ width: '100%', pr: 2 }}
                >
                  <Typography sx={{ flexGrow: 1, fontWeight: 600 }}>
                    Version {version.version_number}: {version.name}
                  </Typography>
                  <Chip
                    size="small"
                    label={version.status}
                    color={
                      version.status === 'published' ? 'success' : 'warning'
                    }
                  />
                  <Typography variant="body2" color="text.secondary">
                    {formatDate(version.published_at)}
                  </Typography>
                </Stack>
              </AccordionSummary>
              <AccordionDetails>
                <Typography color="text.secondary" sx={{ mb: 2 }}>
                  {version.description ?? 'No description'}
                </Typography>
                <Table
                  size="small"
                  aria-label={`Version ${version.version_number} columns`}
                >
                  <TableHead>
                    <TableRow>
                      <TableCell>Order</TableCell>
                      <TableCell>Column</TableCell>
                      <TableCell>Type</TableCell>
                      <TableCell>Prompt</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {version.columns.map((column) => (
                      <TableRow key={column.id}>
                        <TableCell>{column.display_order + 1}</TableCell>
                        <TableCell>{column.name}</TableCell>
                        <TableCell>{column.column_type}</TableCell>
                        <TableCell>
                          {column.prompt_text ?? 'No prompt'}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </AccordionDetails>
            </Accordion>
          ))}
        </Stack>
      )}
    </Container>
  )
}
