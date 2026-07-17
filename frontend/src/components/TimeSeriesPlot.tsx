import { useMemo } from 'react'
import createPlotlyComponent from 'react-plotly.js/factory'
import Plotly from 'plotly.js-dist-min'
import type { Data, Layout } from 'plotly.js'
import type { Gas, TSGas } from '@/api/types'
import { VIZ } from '@/lib/constants'
import { useTheme } from '@/theme/ThemeProvider'

const Plot = createPlotlyComponent(Plotly)

/**
 * Concentration vs. **real clock time** for one spot ("single") or every spot
 * on one axis ("all"). Points inside the fitted window are highlighted; the
 * fitted flux line is drawn per spot. The absolute time axis lets the user
 * verify that each spot's window lands on the right part of the LI-7810 record.
 *
 * `t_unix` is naive local wall-clock stored as unix seconds; Plotly renders a
 * date axis in UTC, so the ticks read as the original local field time.
 */
export function TimeSeriesPlot({
  gas,
  data,
  mode,
  selectedNr,
}: {
  gas: Gas
  data: TSGas
  mode: 'single' | 'all'
  selectedNr: number
}) {
  const { resolved } = useTheme()
  const color = gas === 'CO2' ? VIZ.co2 : VIZ.ch4
  const dark = resolved === 'dark'

  const { traces, layout } = useMemo(() => {
    const spots =
      mode === 'single'
        ? data.spots.filter((s) => s.nr === selectedNr)
        : data.spots

    const inX: number[] = []
    const inY: number[] = []
    const inNr: number[] = []
    const outX: number[] = []
    const outY: number[] = []
    const outNr: number[] = []
    const lineX: (number | null)[] = []
    const lineY: (number | null)[] = []

    // The rest of the raw record (between/around spots) — drawn as a faint
    // background in the all-spots view so the whole record stays visible.
    // In single-spot view it would zoom the axis out to the whole day, so skip.
    const bgX: number[] = []
    const bgY: number[] = []
    if (mode === 'all') {
      for (const p of data.background) {
        bgX.push(p.t_unix * 1000)
        bgY.push(p.value)
      }
    }

    for (const s of spots) {
      for (const p of s.points) {
        const ms = p.t_unix * 1000
        if (p.in_window) {
          inX.push(ms)
          inY.push(p.value)
          inNr.push(s.nr)
        } else {
          outX.push(ms)
          outY.push(p.value)
          outNr.push(s.nr)
        }
      }
      if (s.line.length === 2) {
        lineX.push(s.line[0].t_unix * 1000, s.line[1].t_unix * 1000, null)
        lineY.push(s.line[0].y, s.line[1].y, null)
      }
    }

    const traces: Data[] = [
      {
        x: bgX,
        y: bgY,
        mode: 'markers',
        type: 'scattergl',
        name: 'Between spots',
        marker: { color: VIZ.muted, size: 2, opacity: 0.3 },
        hovertemplate: '%{x|%H:%M:%S}: %{y}<extra>between spots</extra>',
      },
      {
        x: outX,
        y: outY,
        customdata: outNr,
        mode: 'markers',
        type: 'scattergl',
        name: 'Outside fit window',
        marker: { color: VIZ.muted, size: 3, opacity: 0.5 },
        hovertemplate:
          'Spot %{customdata}<br>%{x|%H:%M:%S}: %{y}<extra>excluded</extra>',
      },
      {
        x: inX,
        y: inY,
        customdata: inNr,
        mode: 'markers',
        type: 'scattergl',
        name: 'Fitted points',
        marker: { color, size: 4 },
        hovertemplate:
          'Spot %{customdata}<br>%{x|%H:%M:%S}: %{y}<extra></extra>',
      },
      {
        x: lineX,
        y: lineY,
        mode: 'lines',
        type: 'scatter',
        name: 'Flux fit',
        line: { color, width: 2.5 },
        connectgaps: false,
        hoverinfo: 'skip',
      },
    ]

    const grid = dark ? '#334155' : '#e2e8f0'
    const text = dark ? '#e2e8f0' : '#1e293b'
    const layout: Partial<Layout> = {
      autosize: true,
      height: 380,
      margin: { l: 60, r: 16, t: 8, b: 48 },
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { color: text, size: 12 },
      showlegend: false,
      xaxis: {
        type: 'date',
        title: { text: 'Time (clock)' },
        tickformat: '%H:%M:%S',
        gridcolor: grid,
        zeroline: false,
      },
      yaxis: {
        title: { text: `${gas} (${data.unit})` },
        gridcolor: grid,
        zeroline: false,
      },
    }
    return { traces, layout }
  }, [data, mode, selectedNr, color, dark, gas])

  return (
    <figure className="m-0">
      <Plot
        data={traces}
        layout={layout}
        useResizeHandler
        style={{ width: '100%' }}
        config={{ displaylogo: false, responsive: true }}
        aria-label={`${gas} concentration over time`}
      />
      <figcaption className="sr-only">
        {gas} concentration ({data.unit}) versus clock time,{' '}
        {mode === 'single' ? `spot ${selectedNr}` : 'all spots'}. Points inside
        each fitted window are highlighted with the fitted flux line.
        {mode === 'all' &&
          ' The rest of the raw record between spots is shown faintly.'}
      </figcaption>
    </figure>
  )
}
