import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import * as Sentry from '@sentry/react'
import './index.css'
import App from './App.tsx'
import { ThemeProvider } from '@/theme/ThemeProvider'
import { ToastProvider } from '@/components'
import { initMonitoring } from '@/lib/monitoring'

// Start error/performance monitoring before rendering so early errors are caught.
// No-op unless VITE_SENTRY_DSN is set (the app runs fine without it).
initMonitoring()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Sentry.ErrorBoundary
      fallback={
        <div style={{ padding: '2rem', fontFamily: 'sans-serif' }}>
          <h1>Something went wrong.</h1>
          <p>The error has been reported. Please reload the page.</p>
        </div>
      }
    >
      <ThemeProvider>
        <ToastProvider>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </ToastProvider>
      </ThemeProvider>
    </Sentry.ErrorBoundary>
  </StrictMode>,
)
