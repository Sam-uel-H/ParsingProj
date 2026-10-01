import { FormEvent, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Button,
  Card,
  CardContent,
  Container,
  Stack,
  TextField,
  Typography,
} from '@mui/material'

import { createDomain, listDomains } from '../../api/domains'
import { ApiErrorAlert } from '../../components/ApiErrorAlert'
import { EmptyState, LoadingState } from '../../components/AsyncState'

export function DomainsPage() {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const domains = useQuery({
    queryKey: ['domains'],
    queryFn: ({ signal }) => listDomains(signal),
  })
  const create = useMutation({
    mutationFn: createDomain,
    onSuccess: async () => {
      setName('')
      setDescription('')
      await queryClient.invalidateQueries({ queryKey: ['domains'] })
    },
  })

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const normalizedName = name.trim()
    if (!normalizedName) return
    create.mutate({
      name: normalizedName,
      description: description.trim() || null,
    })
  }

  return (
    <Container maxWidth="md" component="main" sx={{ py: 6 }}>
      <Typography variant="h3" component="h1" gutterBottom>
        Domains
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 4 }}>
        Domains group related document types and templates.
      </Typography>

      <Card variant="outlined" sx={{ mb: 4 }}>
        <CardContent component="form" onSubmit={submit}>
          <Stack spacing={2}>
            <Typography variant="h5" component="h2">
              Create domain
            </Typography>
            <TextField
              label="Name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
              inputProps={{ maxLength: 200 }}
            />
            <TextField
              label="Description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              multiline
              minRows={2}
              inputProps={{ maxLength: 4000 }}
            />
            {create.isError && <ApiErrorAlert error={create.error} />}
            {create.isSuccess && (
              <Alert severity="success">Domain created successfully.</Alert>
            )}
            <Button
              type="submit"
              variant="contained"
              disabled={create.isPending || !name.trim()}
            >
              {create.isPending ? 'Creating…' : 'Create domain'}
            </Button>
          </Stack>
        </CardContent>
      </Card>

      <Typography variant="h5" component="h2" sx={{ mb: 2 }}>
        Existing domains
      </Typography>
      {domains.isPending && <LoadingState label="Loading domains…" />}
      {domains.isError && <ApiErrorAlert error={domains.error} />}
      {domains.isSuccess && domains.data.length === 0 && (
        <EmptyState message="No domains have been created yet." />
      )}
      {domains.isSuccess && (
        <Stack spacing={2}>
          {domains.data.map((domain) => (
            <Card variant="outlined" key={domain.id}>
              <CardContent>
                <Typography variant="h6" component="h3">
                  {domain.name}
                </Typography>
                <Typography color="text.secondary">
                  {domain.description ?? 'No description'}
                </Typography>
              </CardContent>
            </Card>
          ))}
        </Stack>
      )}
    </Container>
  )
}
