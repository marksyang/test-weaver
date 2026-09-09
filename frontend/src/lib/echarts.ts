// 瘦身 ECharts：只註冊實際用到的組件（bar / pie + grid/legend/title/tooltip + canvas），
// 取代 `import * as echarts from 'echarts'` 的全量 import（大幅縮小 bundle）。
// EChart.tsx 以「動態 import」本模組，讓這段程式碼成為獨立的 lazy chunk（不進首載 bundle）。
import * as echarts from 'echarts/core';
import { BarChart, PieChart } from 'echarts/charts';
import {
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

echarts.use([
  BarChart,
  PieChart,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
  CanvasRenderer,
]);

export default echarts;
export type { EChartsCoreOption as EChartsOption, EChartsType } from 'echarts/core';
