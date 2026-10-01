import {
  AppBar,
  Box,
  Breadcrumbs,
  Button,
  Container,
  Link as MuiLink,
  Stack,
  Toolbar,
  Typography,
} from '@mui/material'
import { lazy, Suspense } from 'react'
import { Link, Route, Routes, useLocation } from 'react-router-dom'

import { LoadingState } from './components/AsyncState'
import { RouteErrorBoundary } from './components/RouteErrorBoundary'
import { DocumentDetailPage } from './features/documents/DocumentDetailPage'
import { DocumentsPage } from './features/documents/DocumentsPage'
import { DocumentUploadPage } from './features/documents/DocumentUploadPage'
import { DomainsPage } from './features/domains/DomainsPage'
import { ParsingJobPage } from './features/parsing/ParsingJobPage'
import { RunParsingPage } from './features/parsing/RunParsingPage'
import { DashboardPage } from './features/system/DashboardPage'
import { TemplateEditorPage } from './features/templates/TemplateEditorPage'
import { TemplateHistoryPage } from './features/templates/TemplateHistoryPage'
import { TemplatesPage } from './features/templates/TemplatesPage'

const PromptHelperPage = lazy(() =>
  import('./features/templates/PromptHelperPage').then((module) => ({
    default: module.PromptHelperPage,
  })),
)

const navigation = [
  { label: 'Dashboard', to: '/' },
  { label: 'Domains', to: '/domains' },
  { label: 'Templates', to: '/templates' },
  { label: 'Documents', to: '/documents' },
  { label: 'Run parsing', to: '/parse' },
]

function WorkflowBreadcrumbs() {
  const { pathname } = useLocation()
  if (pathname === '/') return null

  let section = ''
  let sectionPath = '/'
  let detail = ''
  if (pathname.startsWith('/domains')) {
    section = 'Domains'
    sectionPath = '/domains'
  }
  if (pathname.startsWith('/templates')) {
    section = 'Templates'
    sectionPath = '/templates'
    if (pathname === '/templates/new') detail = 'New template'
    else if (pathname.endsWith('/history')) detail = 'Version history'
    else if (pathname.endsWith('/prompt-helper')) detail = 'Prompt Helper'
    else if (pathname !== '/templates') detail = 'Template editor'
  }
  if (pathname.startsWith('/documents')) {
    section = 'Documents'
    sectionPath = '/documents'
    if (pathname === '/documents/upload') detail = 'Upload'
    else if (pathname !== '/documents') detail = 'Document detail'
  }
  if (pathname === '/parse') {
    section = 'Run parsing'
    sectionPath = '/parse'
  }
  if (pathname.startsWith('/parsing-jobs/')) {
    section = 'Run parsing'
    sectionPath = '/parse'
    detail = 'Results'
  }

  return (
    <Container maxWidth="lg" sx={{ pt: 2 }}>
      <Breadcrumbs aria-label="Breadcrumbs">
        <MuiLink component={Link} underline="hover" color="inherit" to="/">
          Dashboard
        </MuiLink>
        {detail ? (
          <MuiLink
            component={Link}
            underline="hover"
            color="inherit"
            to={sectionPath}
          >
            {section}
          </MuiLink>
        ) : (
          <Typography color="text.primary">{section || 'Page'}</Typography>
        )}
        {detail && <Typography color="text.primary">{detail}</Typography>}
      </Breadcrumbs>
    </Container>
  )
}

function NotFoundPage() {
  return (
    <Container maxWidth="md" component="main" sx={{ py: 6 }}>
      <Stack spacing={2}>
        <Typography variant="h3" component="h1">
          Page not found
        </Typography>
        <Typography color="text.secondary">
          The requested page does not exist or may have moved.
        </Typography>
        <Button component={Link} to="/" variant="contained">
          Return to dashboard
        </Button>
      </Stack>
    </Container>
  )
}

export default function App() {
  const location = useLocation()
  return (
    <Box sx={{ minHeight: '100vh' }}>
      <AppBar position="static" elevation={0}>
        <Toolbar sx={{ gap: 2, flexWrap: 'wrap', py: 1 }}>
          <Typography variant="h6" sx={{ flexGrow: 1, minWidth: 160 }}>
            Parsing
          </Typography>
          <Stack
            direction="row"
            spacing={0.5}
            component="nav"
            aria-label="Main navigation"
            sx={{ overflowX: 'auto', maxWidth: '100%' }}
          >
            {navigation.map((item) => {
              const active =
                item.to === '/'
                  ? location.pathname === '/'
                  : location.pathname.startsWith(item.to)
              return (
                <Button
                  color="inherit"
                  component={Link}
                  to={item.to}
                  aria-current={active ? 'page' : undefined}
                  key={item.to}
                  sx={{ whiteSpace: 'nowrap' }}
                >
                  {item.label}
                </Button>
              )
            })}
          </Stack>
        </Toolbar>
      </AppBar>
      <WorkflowBreadcrumbs />
      <RouteErrorBoundary key={location.pathname}>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/domains" element={<DomainsPage />} />
          <Route path="/templates" element={<TemplatesPage />} />
          <Route path="/templates/new" element={<TemplateEditorPage />} />
          <Route
            path="/templates/:templateId"
            element={<TemplateEditorPage />}
          />
          <Route
            path="/templates/:templateId/history"
            element={<TemplateHistoryPage />}
          />
          <Route
            path="/templates/:templateId/prompt-helper"
            element={
              <Suspense
                fallback={<LoadingState label="Loading Prompt Helper…" />}
              >
                <PromptHelperPage />
              </Suspense>
            }
          />
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/documents/upload" element={<DocumentUploadPage />} />
          <Route
            path="/documents/:documentId"
            element={<DocumentDetailPage />}
          />
          <Route path="/parse" element={<RunParsingPage />} />
          <Route path="/parsing-jobs/:jobId" element={<ParsingJobPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </RouteErrorBoundary>
    </Box>
  )
}
