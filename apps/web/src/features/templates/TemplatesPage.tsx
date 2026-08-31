import { useQuery } from '@tanstack/react-query'
import {
  Alert,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Container,
  Button,
  Stack,
  Typography,
} from '@mui/material'
import { Link } from 'react-router-dom'

import { listTemplates } from '../../api/templates'
import { ApiErrorAlert } from '../../components/ApiErrorAlert'

export function TemplatesPage() {
  const templates = useQuery({
    queryKey: ['templates'],
    queryFn: ({ signal }) => listTemplates(signal),
  })

  return (
    <Container maxWidth="md" component="main" sx={{ py: 6 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Typography variant="h3" component="h1" gutterBottom>
          Templates
        </Typography>
        <Button component={Link} to="/templates/new" variant="contained">
          New template
        </Button>
      </Stack>
      <Typography color="text.secondary" sx={{ mb: 4 }}>
        Create draft schemas, add extraction prompts, and publish them when they
        are ready.
      </Typography>
      {templates.isPending && (
        <CircularProgress aria-label="Loading templates" />
      )}
      {templates.isError && <ApiErrorAlert error={templates.error} />}
      {templates.isSuccess && templates.data.length === 0 && (
        <Alert severity="info">No templates have been created yet.</Alert>
      )}
      {templates.isSuccess && (
        <Stack spacing={2}>
          {templates.data.map((template) => (
            <Card variant="outlined" key={template.id}>
              <CardContent>
                <Stack
                  direction="row"
                  alignItems="center"
                  justifyContent="space-between"
                >
                  <Typography variant="h6" component="h2">
                    {template.name}
                  </Typography>
                  <Chip
                    label={`${template.status} v${template.version_number}`}
                    size="small"
                  />
                </Stack>
                <Typography color="text.secondary">
                  {template.description ?? 'No description'}
                </Typography>
                <Button
                  component={Link}
                  to={`/templates/${template.id}`}
                  sx={{ mt: 2 }}
                >
                  {template.status === 'draft' ? 'Edit draft' : 'View'}
                </Button>
              </CardContent>
            </Card>
          ))}
        </Stack>
      )}
    </Container>
  )
}
