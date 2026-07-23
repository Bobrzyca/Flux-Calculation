import { useMemo } from 'react'
import createPlotlyComponent from 'react-plotly.js/factory'
// Use the smaller dist-min build rather than the full plotly.js bundle.
import Plotly from 'plotly.js-dist-min'
import type { Data, Layout } from 'plotly.js'
import type { TemperaturePoint } from '@/api/types'
import { VIZ } from '@/lib/constants'
import { useTheme } from '@/theme/ThemeProvider'

const Plot = createPlotlyComponent(Plotly)

/** A simple time series of the parsed temperature log (confirm-before-match). */
export function TemperaturePlot({ points }: { points: TemperaturePoint[] }) {
  const { resolved } = useTheme()
  const dark = resolved === 'dark'

  const { data, layout } = useMemo(() => {
    const data: Data[] = [
      {
        x: points.map((p) => p.t_unix * 1000),
        y: points.map((p) => p.value),
        mode: 'lines',
        type: 'scattergl',
        name: 'Temperature',
        line: { color: VIZ.co2, width: 1.5 },
        hovertemplate: '%{x|%H:%M:%S}: %{y:.2f} °C<extra></extra>',
      },
    ]
    const fg = dark ? '#e2e8f0' : '#0f172a'
    const grid = dark ? '#334155' : '#e2e8f0'
    const layout: Partial<Layout> = {
      autosize: true,
      height: 300,
      margin: { l: 56, r: 16, t: 8, b: 40 },
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { color: fg, size: 12 },
      xaxis: { type: 'date', gridcolor: grid, title: { text: 'Time' } },
      yaxis: { gridcolor: grid, title: { text: '°C' } },
      showlegend: false,
    }
    return { data, layout }
  }, [points, dark])

  return (
    <Plot
      data={data}
      layout={layout}
      useResizeHandler
      style={{ width: '100%', height: '300px' }}
      config={{ displayModeBar: false, responsive: true }}
    />
  )
}
