import {
  AppBar,
  Box,
  Button,
  Container,
  Stack,
  Toolbar,
  Typography,
} from '@mui/material'
import { Link, Navigate, Route, Routes } from 'react-router-dom'

import { DomainsPage } from './features/domains/DomainsPage'
import { DocumentDetailPage } from './features/documents/DocumentDetailPage'
import { DocumentsPage } from './features/documents/DocumentsPage'
import { DocumentUploadPage } from './features/documents/DocumentUploadPage'
import { HealthStatus } from './features/system/HealthStatus'
import { TemplatesPage } from './features/templates/TemplatesPage'
import { TemplateEditorPage } from './features/templates/TemplateEditorPage'
import { RunParsingPage } from './features/parsing/RunParsingPage'
import { ParsingJobPage } from './features/parsing/ParsingJobPage'

function FoundationPage() {
  return (
    <Container maxWidth="md" component="main" sx={{ py: 8 }}>
      <Typography variant="h3" component="h1" gutterBottom>
        Document Parsing System
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 4 }}>
        Phase 3 template authoring and secure document upload is ready.
      </Typography>
      <HealthStatus />
    </Container>
  )
}

export default function App() {
  return (
    <Box sx={{ minHeight: '100vh' }}>
      <AppBar position="static" elevation={0}>
        <Toolbar>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            Parsing
          </Typography>
          <Stack
            direction="row"
            spacing={1}
            component="nav"
            aria-label="Main navigation"
          >
            <Button color="inherit" component={Link} to="/">
              Home
            </Button>
            <Button color="inherit" component={Link} to="/domains">
              Domains
            </Button>
            <Button color="inherit" component={Link} to="/templates">
              Templates
            </Button>
            <Button color="inherit" component={Link} to="/documents">
              Documents
            </Button>
            <Button color="inherit" component={Link} to="/parse">
              Run parsing
            </Button>
          </Stack>
        </Toolbar>
      </AppBar>
      <Routes>
        <Route path="/" element={<FoundationPage />} />
        <Route path="/domains" element={<DomainsPage />} />
        <Route path="/templates" element={<TemplatesPage />} />
        <Route path="/templates/new" element={<TemplateEditorPage />} />
        <Route path="/templates/:templateId" element={<TemplateEditorPage />} />
        <Route path="/documents" element={<DocumentsPage />} />
        <Route path="/documents/upload" element={<DocumentUploadPage />} />
        <Route path="/documents/:documentId" element={<DocumentDetailPage />} />
        <Route path="/parse" element={<RunParsingPage />} />
        <Route path="/parsing-jobs/:jobId" element={<ParsingJobPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Box>
  )
}
