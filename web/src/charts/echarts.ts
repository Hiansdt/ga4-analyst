// Registers only the ECharts pieces the app uses, which keeps the bundle small.
import { BarChart, FunnelChart, LineChart, PieChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import { SVGRenderer } from 'echarts/renderers'

echarts.use([LineChart, BarChart, FunnelChart, PieChart, GridComponent, TooltipComponent, LegendComponent, SVGRenderer])

export { echarts }
