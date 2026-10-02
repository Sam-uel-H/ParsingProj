import { useMutation } from '@tanstack/react-query'
import {
  Alert,
  Box,
  Button,
  Chip,
  MenuItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material'
import { useEffect, useState } from 'react'

import {
  correctParsingResult,
  parsingExportUrl,
  type ParsingJob,
  type ParsingResult,
} from '../../api/parsing'
import { ApiErrorAlert } from '../../components/ApiErrorAlert'
import { isJobActive } from '../../api/jobs'
import { JobProgress } from '../../components/JobProgress'

function initialDrafts(results: ParsingResult[]): Record<string, string> {
  return Object.fromEntries(
    results.map((result) => [result.id, result.current_value ?? '']),
  )
}

function inputType(result: ParsingResult): string {
  if (result.column_type === 'date') {
    return 'date'
  }
  if (['integer', 'decimal', 'currency'].includes(result.column_type)) {
    return 'number'
  }
  return 'text'
}

function ResultEditor({
  result,
  value,
  onChange,
}: {
  result: ParsingResult
  value: string
  onChange: (value: string) => void
}) {
  if (result.column_type === 'boolean') {
    return (
      <TextField
        select
        label="Reviewed value"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        size="small"
        fullWidth
      >
        <MenuItem value="true">True</MenuItem>
        <MenuItem value="false">False</MenuItem>
      </TextField>
    )
  }
  if (result.column_type === 'enum') {
    return (
      <TextField
        select
        label="Reviewed value"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        size="small"
        fullWidth
      >
        {(result.enum_values ?? []).map((item) => (
          <MenuItem value={item} key={item}>
            {item}
          </MenuItem>
        ))}
      </TextField>
    )
  }
  return (
    <TextField
      label="Reviewed value"
      value={value}
      type={inputType(result)}
      onChange={(event) => onChange(event.target.value)}
      size="small"
      fullWidth
      inputProps={result.column_type === 'integer' ? { step: 1 } : undefined}
    />
  )
}

export function ParsingResults({ job }: { job: ParsingJob }) {
  const [results, setResults] = useState(job.results)
  const [drafts, setDrafts] = useState(() => initialDrafts(job.results))
  const correction = useMutation({
    mutationFn: ({ resultId, value }: { resultId: string; value: string }) =>
      correctParsingResult(job.id, resultId, value),
    onSuccess: (updated) => {
      setResults((current) =>
        current.map((result) => (result.id === updated.id ? updated : result)),
      )
      setDrafts((current) => ({
        ...current,
        [updated.id]: updated.current_value ?? '',
      }))
    },
  })

  useEffect(() => {
    setResults(job.results)
    setDrafts(initialDrafts(job.results))
  }, [job.results])

  const displayedStatus =
    job.status === 'completed_with_warnings' &&
    results.every((result) => result.validation_status === 'valid')
      ? 'completed'
      : job.status

  if (isJobActive(job.status) || job.status === 'failed') {
    return <JobProgress progress={job.progress} status={job.status} />
  }

  return (
    <Stack spacing={2}>
      <Stack direction="row" spacing={1} alignItems="center">
        <Alert
          severity={displayedStatus === 'completed' ? 'success' : 'warning'}
          sx={{ flexGrow: 1 }}
        >
          Job status: {displayedStatus.replaceAll('_', ' ')}
        </Alert>
        <Button component="a" href={parsingExportUrl(job.id, 'csv')}>
          Export CSV
        </Button>
        <Button component="a" href={parsingExportUrl(job.id, 'json')}>
          Export JSON
        </Button>
      </Stack>
      {correction.error && <ApiErrorAlert error={correction.error} />}
      <Box sx={{ overflowX: 'auto' }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Column</TableCell>
              <TableCell>Type</TableCell>
              <TableCell>Original</TableCell>
              <TableCell>Reviewed</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Confidence</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {results.map((result) => {
              const draft = drafts[result.id] ?? ''
              const savedValue = result.current_value ?? ''
              const changed = draft !== savedValue
              return (
                <TableRow
                  key={result.id}
                  sx={
                    result.validation_status === 'needs_review'
                      ? { bgcolor: 'warning.light' }
                      : undefined
                  }
                >
                  <TableCell>
                    <Typography fontWeight={600}>
                      {result.column_name}
                    </Typography>
                  </TableCell>
                  <TableCell>{result.column_type}</TableCell>
                  <TableCell>
                    {result.canonical_value ?? 'No valid value'}
                  </TableCell>
                  <TableCell sx={{ minWidth: 220 }}>
                    <ResultEditor
                      result={result}
                      value={draft}
                      onChange={(value) =>
                        setDrafts((current) => ({
                          ...current,
                          [result.id]: value,
                        }))
                      }
                    />
                  </TableCell>
                  <TableCell>
                    <Stack spacing={0.5}>
                      <Box>
                        <Chip
                          label={result.validation_status.replace('_', ' ')}
                          color={
                            result.validation_status === 'valid'
                              ? 'success'
                              : 'warning'
                          }
                          size="small"
                        />
                      </Box>
                      <Typography variant="caption" color="text.secondary">
                        {result.human_verified ? 'Human verified' : 'Original'}
                      </Typography>
                      {result.validation_message && (
                        <Typography variant="caption" color="error">
                          {result.validation_message}
                        </Typography>
                      )}
                      {result.retry_count > 0 && (
                        <Typography variant="caption" color="text.secondary">
                          Retried {result.retry_count}{' '}
                          {result.retry_count === 1 ? 'time' : 'times'}
                        </Typography>
                      )}
                    </Stack>
                  </TableCell>
                  <TableCell>
                    {result.confidence === null
                      ? 'n/a'
                      : `${Math.round(result.confidence * 100)}%`}
                  </TableCell>
                  <TableCell align="right">
                    <Stack
                      direction="row"
                      spacing={1}
                      justifyContent="flex-end"
                    >
                      <Button
                        size="small"
                        disabled={!changed || correction.isPending}
                        onClick={() =>
                          correction.mutate({
                            resultId: result.id,
                            value: draft,
                          })
                        }
                      >
                        Save
                      </Button>
                      <Button
                        size="small"
                        disabled={!changed || correction.isPending}
                        onClick={() =>
                          setDrafts((current) => ({
                            ...current,
                            [result.id]: savedValue,
                          }))
                        }
                      >
                        Cancel
                      </Button>
                    </Stack>
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </Box>
    </Stack>
  )
}
