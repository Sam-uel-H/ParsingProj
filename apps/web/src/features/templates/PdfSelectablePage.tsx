import { Alert, CircularProgress } from '@mui/material'
import { GlobalWorkerOptions, getDocument, TextLayer } from 'pdfjs-dist'
import type { RenderTask } from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { useEffect, useRef, useState } from 'react'

import { documentContentUrl } from '../../api/documents'

GlobalWorkerOptions.workerSrc = workerUrl

interface PdfSelectablePageProps {
  documentId: string
  pageNumber: number
  zoom: number
  onSelection: (element: HTMLElement) => void
  highlights: { x: number; y: number; width: number; height: number }[]
}

export function PdfSelectablePage({
  documentId,
  pageNumber,
  zoom,
  onSelection,
  highlights,
}: PdfSelectablePageProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const textLayerRef = useRef<HTMLDivElement>(null)
  const pageRef = useRef<HTMLDivElement>(null)
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading')

  useEffect(() => {
    let cancelled = false
    let textLayer: TextLayer | undefined
    let renderTask: RenderTask | undefined
    const loadingTask = getDocument({ url: documentContentUrl(documentId) })
    const render = async () => {
      setState('loading')
      const pdf = await loadingTask.promise
      const page = await pdf.getPage(pageNumber)
      if (cancelled) return
      const viewport = page.getViewport({ scale: zoom / 100 })
      const canvas = canvasRef.current
      const layerElement = textLayerRef.current
      const container = pageRef.current
      if (!canvas || !layerElement || !container) return
      canvas.width = Math.ceil(viewport.width)
      canvas.height = Math.ceil(viewport.height)
      canvas.style.width = `${viewport.width}px`
      canvas.style.height = `${viewport.height}px`
      container.style.width = `${viewport.width}px`
      container.style.height = `${viewport.height}px`
      container.style.setProperty(
        '--total-scale-factor',
        String(viewport.scale),
      )
      layerElement.replaceChildren()
      const context = canvas.getContext('2d')
      if (!context) throw new Error('Canvas is unavailable.')
      renderTask = page.render({ canvas, canvasContext: context, viewport })
      await renderTask.promise
      if (cancelled) return
      textLayer = new TextLayer({
        textContentSource: await page.getTextContent(),
        container: layerElement,
        viewport,
      })
      await textLayer.render()
      if (!cancelled) setState('ready')
    }
    void render().catch(() => {
      if (!cancelled) setState('error')
    })
    return () => {
      cancelled = true
      textLayer?.cancel()
      renderTask?.cancel()
      void loadingTask.destroy()
    }
  }, [documentId, pageNumber, zoom])

  return (
    <>
      {state === 'loading' && (
        <CircularProgress aria-label="Rendering PDF page" />
      )}
      {state === 'error' && (
        <Alert severity="error">The PDF page could not be rendered.</Alert>
      )}
      <div
        className="prompt-pdf-page"
        ref={pageRef}
        aria-label={`Selectable PDF page ${pageNumber}`}
        onMouseUp={() => pageRef.current && onSelection(pageRef.current)}
        onKeyUp={() => pageRef.current && onSelection(pageRef.current)}
      >
        <canvas ref={canvasRef} />
        <div ref={textLayerRef} className="textLayer prompt-pdf-text-layer" />
        {highlights.map((rect, index) => (
          <div
            className="prompt-tag-highlight"
            key={index}
            style={{
              left: `${rect.x * 100}%`,
              top: `${rect.y * 100}%`,
              width: `${rect.width * 100}%`,
              height: `${rect.height * 100}%`,
            }}
          />
        ))}
      </div>
    </>
  )
}
