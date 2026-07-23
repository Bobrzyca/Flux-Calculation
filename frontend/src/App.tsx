import { useEffect } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
import { AppLayout } from '@/pages/AppLayout'
import { Home } from '@/pages/Home'
import { Upload } from '@/pages/Upload'
import { ConfirmNotes } from '@/pages/ConfirmNotes'
import { ConfirmTemperature } from '@/pages/ConfirmTemperature'
import { Results } from '@/pages/Results'
import { ProcessingLog } from '@/pages/ProcessingLog'
import { NotFound } from '@/pages/NotFound'
import { setRouteContext } from '@/lib/monitoring'

export default function App() {
  // Tag monitoring events with the current route for context (no-op if Sentry
  // is disabled). Uses the route pattern-free pathname; ids in it are opaque.
  const { pathname } = useLocation()
  useEffect(() => {
    setRouteContext(pathname)
  }, [pathname])

  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<Home />} />
        <Route path="/analyses/new" element={<Upload />} />
        <Route path="/analyses/:id/upload" element={<Upload />} />
        <Route path="/analyses/:id/confirm" element={<ConfirmNotes />} />
        <Route
          path="/analyses/:id/confirm-temperature"
          element={<ConfirmTemperature />}
        />
        <Route path="/analyses/:id/results" element={<Results />} />
        <Route path="/analyses/:id/log" element={<ProcessingLog />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}
