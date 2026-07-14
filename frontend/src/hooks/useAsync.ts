import { useCallback, useEffect, useRef, useState } from 'react'

export interface AsyncState<T> {
  data: T | null
  loading: boolean
  error: Error | null
  /** Re-run the async function. */
  reload: () => void
}

/**
 * Run an async function on mount (and whenever `deps` change), tracking
 * loading/error/data. Ignores results from stale runs so a fast reload can't be
 * overwritten by a slow earlier request.
 */
export function useAsync<T>(
  fn: () => Promise<T>,
  deps: unknown[] = [],
): AsyncState<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)
  const runId = useRef(0)

  // fn identity is intentionally not a dependency; callers pass `deps`.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(() => {
    const id = ++runId.current
    setLoading(true)
    setError(null)
    fn()
      .then((result) => {
        if (id === runId.current) {
          setData(result)
          setLoading(false)
        }
      })
      .catch((err: unknown) => {
        if (id === runId.current) {
          setError(err instanceof Error ? err : new Error(String(err)))
          setLoading(false)
        }
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(() => {
    run()
  }, [run])

  return { data, loading, error, reload: run }
}
