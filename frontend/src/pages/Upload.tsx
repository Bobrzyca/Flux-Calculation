import { useState, type FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, ApiError } from '@/api/client'
import type { CreateAnalysisInput } from '@/api/types'
import { useAsync } from '@/hooks/useAsync'
import {
  Stepper,
  CardSection,
  Dropzone,
  TextInput,
  NumberInput,
  DateInput,
  Button,
  Banner,
  PipelineProgress,
  type PipelineStep,
} from '@/components'
import {
  DEFAULT_CHAMBER_AREA_M2,
  DEFAULT_CHAMBER_VOLUME_L,
  DEFAULT_TIME_OFFSET_S,
  FILE_ACCEPT,
} from '@/lib/constants'

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

type FileKey = 'concentration' | 'notes' | 'temperature' | 'pressure'
type Files = Record<FileKey, File | null>

export function Upload() {
  const navigate = useNavigate()
  const { id } = useParams()
  const isRerun = !!id

  // Prefill constants when re-running an existing analysis.
  const { data: existing } = useAsync(
    () => (id ? api.getAnalysis(id) : Promise.resolve(null)),
    [id],
  )

  const [name, setName] = useState('')
  // Fallback only — the backend uses the date from the LI-7810 file itself.
  const [workDate, setWorkDate] = useState(() =>
    new Date().toISOString().slice(0, 10),
  )
  const [files, setFiles] = useState<Files>({
    concentration: null,
    notes: null,
    temperature: null,
    pressure: null,
  })
  const [area, setArea] = useState(String(DEFAULT_CHAMBER_AREA_M2))
  const [volume, setVolume] = useState(String(DEFAULT_CHAMBER_VOLUME_L))
  const [offset, setOffset] = useState(String(DEFAULT_TIME_OFFSET_S))

  const [errors, setErrors] = useState<Record<string, string>>({})
  const [banner, setBanner] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const [steps, setSteps] = useState<PipelineStep[]>([])

  // Populate name/constants once the existing analysis loads (re-run).
  const [prefilled, setPrefilled] = useState(false)
  if (existing && !prefilled) {
    setPrefilled(true)
    setName(existing.name)
    setWorkDate(existing.work_date)
    setArea(String(existing.chamber_area_m2))
    setVolume(String(existing.chamber_volume_l))
    setOffset(String(existing.time_offset_seconds))
  }

  const setFile = (key: FileKey) => (file: File | null) =>
    setFiles((f) => ({ ...f, [key]: file }))

  function validate(): boolean {
    const next: Record<string, string> = {}
    if (!name.trim()) next.name = 'Give this analysis a name.'
    // On a re-run, files are optional — an empty dropzone keeps the current
    // file. On a fresh analysis the first three are required.
    if (!isRerun) {
      if (!files.concentration) next.concentration = 'Required file missing.'
      if (!files.notes) next.notes = 'Required file missing.'
      if (!files.temperature) next.temperature = 'Required file missing.'
    }
    // Pressure is optional — the backend falls back to a standard default.
    if (!(Number(area) > 0)) next.area = 'Enter a positive number.'
    if (!(Number(volume) > 0)) next.volume = 'Enter a positive number.'
    if (offset.trim() === '' || Number.isNaN(Number(offset)))
      next.offset = 'Enter a number of seconds (may be negative).'
    setErrors(next)
    return Object.keys(next).length === 0
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setBanner(null)
    if (!validate()) return

    const input: CreateAnalysisInput = {
      name: name.trim(),
      work_date: workDate,
      chamber_area_m2: Number(area),
      chamber_volume_l: Number(volume),
      time_offset_seconds: Number(offset),
      files,
    }

    setRunning(true)
    setSteps([
      { label: 'Uploading your files', status: 'active' },
      { label: 'Parsing field notes with the assistant', status: 'pending' },
    ])
    try {
      await sleep(600)
      setSteps([
        { label: 'Uploading your files', status: 'done' },
        { label: 'Parsing field notes with the assistant', status: 'active' },
      ])
      const analysis = isRerun
        ? await api.updateAnalysis(id!, input)
        : await api.createAnalysis(input)
      setSteps((s) => s.map((x) => ({ ...x, status: 'done' })))
      await sleep(300)
      navigate(`/analyses/${analysis.id}/confirm`)
    } catch (err) {
      setRunning(false)
      if (err instanceof ApiError && err.field) {
        setErrors((prev) => ({ ...prev, [err.field as string]: err.message }))
        if (err.field === 'name') setBanner(err.message)
      } else {
        setBanner(
          err instanceof Error
            ? err.message
            : 'Could not start the analysis. Please try again.',
        )
      }
    }
  }

  if (running) {
    return (
      <div className="flex flex-col gap-8">
        <Stepper current="Upload" />
        <div className="py-8">
          <PipelineProgress steps={steps} title="Starting your analysis…" />
        </div>
      </div>
    )
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-8" noValidate>
      <Stepper current="Upload" furthest="Upload" />

      <div>
        <h1 className="text-2xl font-bold text-text">
          {isRerun ? 'Re-run analysis' : 'New analysis'}
        </h1>
        <p className="mt-1 text-sm text-muted">
          {isRerun
            ? 'Replace any files you want to change (leave a dropzone empty to keep the current file), adjust the constants, then re-run.'
            : 'Upload your field files and set the chamber constants, then run.'}
        </p>
      </div>

      {banner && (
        <Banner tone="warning" onDismiss={() => setBanner(null)}>
          {banner}
        </Banner>
      )}

      <CardSection title="Analysis details">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <TextInput
            label="Analysis name"
            required
            placeholder="e.g. Kampinos — 2 July"
            value={name}
            error={errors.name}
            onChange={(e) => setName(e.target.value)}
          />
          <DateInput
            label="Work date"
            required
            value={workDate}
            helper="Auto-detected from the LI-7810 file; this is only a fallback."
            onChange={(e) => setWorkDate(e.target.value)}
          />
        </div>
      </CardSection>

      <CardSection
        title="Field files"
        description={
          isRerun
            ? 'Leave a dropzone empty to keep the current file. Max 50 MB each.'
            : 'The first three are required; the IMGW pressure file is optional. Max 50 MB each.'
        }
      >
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Dropzone
            label="LI-7810 concentration"
            acceptHint={
              isRerun
                ? '.txt / .xlsx — leave empty to keep current'
                : '.txt or .xlsx'
            }
            accept={FILE_ACCEPT.concentration}
            file={files.concentration}
            onChange={setFile('concentration')}
            error={errors.concentration}
            required={!isRerun}
          />
          <Dropzone
            label="Time-window notes"
            acceptHint={
              isRerun
                ? '.docx, .xlsx, .csv — leave empty to keep current'
                : '.docx, .xlsx, .csv'
            }
            accept={FILE_ACCEPT.notes}
            file={files.notes}
            onChange={setFile('notes')}
            error={errors.notes}
            required={!isRerun}
          />
          <Dropzone
            label="Temperature"
            acceptHint={
              isRerun
                ? '.xlsx, .csv — leave empty to keep current'
                : '.xlsx, .csv'
            }
            accept={FILE_ACCEPT.temperature}
            file={files.temperature}
            onChange={setFile('temperature')}
            error={errors.temperature}
            required={!isRerun}
          />
          <Dropzone
            label="IMGW pressure (optional)"
            acceptHint="any format — optional"
            file={files.pressure}
            onChange={setFile('pressure')}
            error={errors.pressure}
          />
        </div>
      </CardSection>

      <CardSection title="Chamber constants">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <NumberInput
            label="Area (m²)"
            step="0.0001"
            value={area}
            error={errors.area}
            onChange={(e) => setArea(e.target.value)}
          />
          <NumberInput
            label="Volume (L)"
            step="0.001"
            value={volume}
            error={errors.volume}
            onChange={(e) => setVolume(e.target.value)}
          />
          <NumberInput
            label="Time-offset (seconds)"
            step="1"
            value={offset}
            error={errors.offset}
            helper="Add/subtract seconds if the LI-7810 clock drifted from real time."
            onChange={(e) => setOffset(e.target.value)}
          />
        </div>
      </CardSection>

      <div className="flex flex-wrap items-center justify-between gap-4 border-t border-border pt-6">
        <button
          type="button"
          onClick={() => navigate('/')}
          className="text-sm text-muted underline-offset-2 hover:text-text hover:underline"
        >
          Save as draft
        </button>
        <Button type="submit" variant="cta" size="md">
          {isRerun ? 'Re-run analysis' : 'Run analysis'}
        </Button>
      </div>
    </form>
  )
}
