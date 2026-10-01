import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Box,
  Button,
  Divider,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { useEffect, useState } from 'react'

import {
  acceptPrompt,
  dryRunPrompt,
  editPrompt,
  generatePrompt,
  listPromptDrafts,
  type DryRunEvidence,
} from '../../api/promptDrafts'
import { ApiErrorAlert } from '../../components/ApiErrorAlert'

interface PromptWorkspaceProps {
  templateId: string
  columnId: string
  documentId: string
  extractionId: string
  lockVersion: number
  hasTag: boolean
  onDirtyChange: (dirty: boolean) => void
  onEvidence: (evidence: DryRunEvidence) => void
}

export function PromptWorkspace({
  templateId,
  columnId,
  documentId,
  extractionId,
  lockVersion,
  hasTag,
  onDirtyChange,
  onEvidence,
}: PromptWorkspaceProps) {
  const queryClient = useQueryClient()
  const queryKey = ['prompt-drafts', templateId, columnId, documentId]
  const drafts = useQuery({
    queryKey,
    queryFn: ({ signal }) =>
      listPromptDrafts(templateId, columnId, documentId, signal),
  })
  const [selectedId, setSelectedId] = useState('')
  const [editor, setEditor] = useState('')
  const available =
    drafts.data?.filter(
      (draft) => draft.document_extraction_id === extractionId,
    ) ?? []
  const selected =
    available.find((draft) => draft.id === selectedId) ?? available[0]
  const dirty = Boolean(selected && editor !== selected.edited_prompt)

  useEffect(() => {
    setEditor(selected?.edited_prompt ?? '')
  }, [selected?.id, selected?.edited_prompt])

  useEffect(() => {
    onDirtyChange(dirty)
    return () => onDirtyChange(false)
  }, [dirty, onDirtyChange])

  const refresh = () => queryClient.invalidateQueries({ queryKey })
  const generate = useMutation({
    mutationFn: () => generatePrompt(templateId, columnId, documentId),
    onSuccess: (draft) => {
      setSelectedId(draft.id)
      setEditor(draft.edited_prompt)
      void refresh()
    },
  })
  const save = useMutation({
    mutationFn: () => editPrompt(templateId, selected!.id, editor),
    onSuccess: () => void refresh(),
  })
  const run = useMutation({
    mutationFn: () => dryRunPrompt(templateId, selected!.id),
    onSuccess: () => void refresh(),
  })
  const accept = useMutation({
    mutationFn: () => acceptPrompt(templateId, selected!.id, lockVersion),
    onSuccess: () => {
      void refresh()
      void queryClient.invalidateQueries({ queryKey: ['template', templateId] })
    },
  })
  const latestRun = selected?.dry_runs.at(-1)

  const switchDraft = (nextId: string) => {
    if (dirty && !window.confirm('Discard unsaved prompt edits?')) return
    setSelectedId(nextId)
  }

  return (
    <Box className="prompt-workspace">
      <Divider sx={{ my: 2 }} />
      <Typography variant="h6" component="h2" sx={{ mb: 1 }}>
        Prompt workspace
      </Typography>
      <Button
        variant="outlined"
        disabled={!hasTag || generate.isPending}
        onClick={() => generate.mutate()}
      >
        Generate prompt
      </Button>
      {drafts.data?.some(
        (draft) => draft.document_extraction_id !== extractionId,
      ) && (
        <Alert severity="info" sx={{ mt: 1 }}>
          Older prompt drafts remain linked to their original extraction.
        </Alert>
      )}
      {available.length > 1 && (
        <TextField
          select
          fullWidth
          size="small"
          label="Saved suggestions"
          value={selected?.id ?? ''}
          onChange={(event) => switchDraft(event.target.value)}
          sx={{ mt: 2 }}
        >
          {available.map((draft, index) => (
            <MenuItem key={draft.id} value={draft.id}>
              Suggestion {available.length - index}
              {draft.accepted ? ' (accepted)' : ''}
            </MenuItem>
          ))}
        </TextField>
      )}
      {selected && (
        <Stack spacing={1.5} sx={{ mt: 2 }}>
          <TextField
            multiline
            minRows={5}
            fullWidth
            label="Prompt"
            value={editor}
            onChange={(event) => setEditor(event.target.value)}
            inputProps={{ maxLength: 10000 }}
          />
          <Typography variant="caption" color="text.secondary">
            {selected.provider_name} / {selected.model_name}
            {selected.accepted ? ' · Accepted' : ''}
          </Typography>
          <Stack direction="row" gap={1} flexWrap="wrap">
            <Button
              variant="outlined"
              disabled={!dirty || !editor.trim() || save.isPending}
              onClick={() => save.mutate()}
            >
              Save draft
            </Button>
            <Button
              disabled={!dirty}
              onClick={() => setEditor(selected.edited_prompt)}
            >
              Discard edits
            </Button>
            <Button
              disabled={dirty || run.isPending}
              onClick={() => run.mutate()}
            >
              Dry run
            </Button>
            <Button
              variant="contained"
              disabled={dirty || accept.isPending || selected.accepted}
              onClick={() => accept.mutate()}
            >
              Accept prompt
            </Button>
          </Stack>
          {latestRun && (
            <Box className="prompt-run-result">
              <Typography variant="subtitle2">Latest dry run</Typography>
              <Typography variant="body2">
                Expected: {latestRun.expected_value}
              </Typography>
              <Typography variant="body2">
                Actual: {latestRun.actual_value ?? 'No valid value'}
              </Typography>
              <Typography variant="body2">
                {latestRun.status === 'provider_error'
                  ? 'Provider error'
                  : latestRun.status === 'invalid'
                    ? 'Validation failed'
                    : latestRun.matches_expected
                      ? 'Matches expected value'
                      : 'Does not match expected value'}
              </Typography>
              {latestRun.validation_message && (
                <Typography variant="body2" color="error">
                  {latestRun.validation_message}
                </Typography>
              )}
              {latestRun.evidence_verified && latestRun.evidence && (
                <Button
                  size="small"
                  onClick={() => onEvidence(latestRun.evidence!)}
                >
                  Show evidence
                </Button>
              )}
            </Box>
          )}
          {selected.dry_runs.length > 1 && (
            <Box>
              <Typography variant="subtitle2">Run history</Typography>
              {selected.dry_runs.map((item, index) => (
                <Typography key={`${item.created_at}-${index}`} variant="body2">
                  {index + 1}. {item.status} · {item.actual_value ?? 'No value'}
                </Typography>
              ))}
            </Box>
          )}
        </Stack>
      )}
      {drafts.error && <ApiErrorAlert error={drafts.error} />}
      {generate.error && <ApiErrorAlert error={generate.error} />}
      {save.error && <ApiErrorAlert error={save.error} />}
      {run.error && <ApiErrorAlert error={run.error} />}
      {accept.error && <ApiErrorAlert error={accept.error} />}
    </Box>
  )
}
