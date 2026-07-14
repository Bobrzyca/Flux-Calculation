import { Routes, Route } from 'react-router-dom'
import { AppLayout } from '@/pages/AppLayout'
import { Home } from '@/pages/Home'
import { Upload } from '@/pages/Upload'
import { ConfirmNotes } from '@/pages/ConfirmNotes'
import { Results } from '@/pages/Results'
import { ProcessingLog } from '@/pages/ProcessingLog'
import { NotFound } from '@/pages/NotFound'

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<Home />} />
        <Route path="/analyses/new" element={<Upload />} />
        <Route path="/analyses/:id/upload" element={<Upload />} />
        <Route path="/analyses/:id/confirm" element={<ConfirmNotes />} />
        <Route path="/analyses/:id/results" element={<Results />} />
        <Route path="/analyses/:id/log" element={<ProcessingLog />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}
