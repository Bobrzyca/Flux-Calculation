/**
 * Type shims for the Plotly packages we use.
 * `@types/plotly.js` covers the API; these map the dist-min build and the
 * react-plotly.js factory subpath onto those types.
 */
declare module 'plotly.js-dist-min' {
  import Plotly from 'plotly.js'
  export = Plotly
}

declare module 'react-plotly.js/factory' {
  import type { PlotParams } from 'react-plotly.js'
  import type { ComponentType } from 'react'
  const createPlotlyComponent: (plotly: unknown) => ComponentType<PlotParams>
  export default createPlotlyComponent
}
