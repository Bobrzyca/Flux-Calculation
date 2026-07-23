import { useMemo } from 'react'
import createPlotlyComponent from 'react-plotly.js/factory'
// Use the smaller dist-min build rather than the full plotly.js bundle.
import Plotly from 'plotly.js-dist-min'
import type { Data, Layout } from 'plotly.js'
import type { GasDetail, Gas } from '@/api/types'
import { VIZ } from '@/lib/constants'
import { useTheme } from '@/theme/ThemeProvider'
import { formatR2 } from '@/lib/format'

const Plot = createPlotlyComponent(Plotly)

/**
 * Interactive scatter of concentration points with the fitted regression line.
 * The fit window (start+30 s → start+5 min 30 s) is shaded; out-of-window
 * points are muted. Zoom/pan enabled. A text summary sits alongside so the fit
 * is not conveyed by the chart alone (a11y).
 */
export function RegressionPlot({
  gas,
  detail,
}: {
  gas: Gas
  detail: GasDetail
}) {
  const { resolved } = useTheme()
  const color = gas === 'CO2' ? VIZ.co2 : VIZ.ch4
  const dark = resolved === 'dark'

  const { data, layout, windowStart, windowEnd } = useMemo(() => {
    const inWin = detail.points.filter((p) => p.in_window)
    const outWin = detail.points.filter((p) => !p.in_window)
    const ws = inWin.length ? inWin[0].t_s : 0
    const we = inWin.length ? inWin[inWin.length - 1].t_s : 0

    const lineX = [ws, we]
    const lineY = [
      detail.fit.intercept + detail.fit.slope * ws,
      detail.fit.intercept + detail.fit.slope * we,
    ]

    // Wider raw record around the spot (display-only) drawn faintly behind the
    // spot's own points, so there's visible context when nudging the window.
    const context = detail.context ?? []
    const spotTs = new Set(detail.points.map((p) => p.t_s))
    const ctx = context.filter((p) => !spotTs.has(p.t_s))

    const traces: Data[] = [
      {
        x: ctx.map((p) => p.t_s),
        y: ctx.map((p) => p.value),
        mode: 'markers',
        type: 'scattergl',
        name: 'Surrounding record',
        marker: { color: VIZ.muted, size: 3, opacity: 0.25 },
        hovertemplate: '%{x}s: %{y}<extra>context</extra>',
      },
      {
        x: outWin.map((p) => p.t_s),
        y: outWin.map((p) => p.value),
        mode: 'markers',
        type: 'scattergl',
        // Recorded points outside the fit window — gas colour (faded), not grey,
        // so the whole line reads as one measurement while you pick the window.
        name: 'Outside window (recorded)',
        marker: { color, size: 4, opacity: 0.35 },
        hovertemplate: '%{x}s: %{y}<extra>outside window</extra>',
      },
      {
        x: inWin.map((p) => p.t_s),
        y: inWin.map((p) => p.value),
        mode: 'markers',
        type: 'scattergl',
        name: 'In fit window',
        marker: { color, size: 5 },
        hovertemplate: '%{x}s: %{y}<extra>in fit window</extra>',
      },
      {
        x: lineX,
        y: lineY,
        mode: 'lines',
        type: 'scatter',
        name: 'Regression',
        line: { color, width: 2.5 },
        hoverinfo: 'skip',
      },
    ]

    const grid = dark ? '#334155' : '#e2e8f0'
    const text = dark ? '#e2e8f0' : '#1e293b'
    const layout: Partial<Layout> = {
      autosize: true,
      height: 340,
      margin: { l: 56, r: 16, t: 8, b: 40 },
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { color: text, size: 12 },
      showlegend: false,
      xaxis: {
        title: { text: 'Time in chamber (s)' },
        gridcolor: grid,
        zeroline: false,
      },
      yaxis: {
        title: { text: `${gas} (${detail.unit})` },
        gridcolor: grid,
        zeroline: false,
      },
      shapes: [
        {
          type: 'rect',
          xref: 'x',
          yref: 'paper',
          x0: ws,
          x1: we,
          y0: 0,
          y1: 1,
          fillcolor: color,
          opacity: 0.06,
          line: { width: 0 },
          layer: 'below',
        },
      ],
    }

    return { data: traces, layout, windowStart: ws, windowEnd: we }
  }, [detail, color, dark, gas])

  return (
    <figure className="m-0">
      <Plot
        data={data}
        layout={layout}
        useResizeHandler
        style={{ width: '100%' }}
        config={{ displaylogo: false, responsive: true }}
        aria-label={`${gas} regression plot`}
      />
      {/* Text alternative — the fit conveyed without the chart. */}
      <figcaption className="sr-only">
        {gas} concentration in {detail.unit} over time. Linear fit over the
        window {windowStart} to {windowEnd} seconds: slope {detail.fit.slope},
        R² {formatR2(detail.fit.r2)}, from {detail.fit.n_points} points (
        {detail.fit.n_dropped_nan} nan dropped).
      </figcaption>
    </figure>
  )
}
