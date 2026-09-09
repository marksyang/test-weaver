import { useEffect, useRef } from 'react';
import type { EChartsOption, EChartsType } from '../lib/echarts';

interface Props {
  option: EChartsOption;
  height?: number;
}

/**
 * 極簡 ECharts 包裝：**動態 import** `../lib/echarts`（code-split → 獨立 lazy chunk），
 * 初始化解算器、隨 option 更新、隨 window resize。
 */
export default function EChart({ option, height = 280 }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<EChartsType | null>(null);
  const optionRef = useRef(option);
  optionRef.current = option;

  useEffect(() => {
    if (!ref.current) return;
    let disposed = false;
    let resizeHandler: (() => void) | undefined;
    (async () => {
      const { default: echarts } = await import('../lib/echarts');
      if (disposed || !ref.current) return;
      const chart = echarts.init(ref.current);
      chartRef.current = chart;
      resizeHandler = () => {
        if (!disposed) chart.resize();
      };
      window.addEventListener('resize', resizeHandler);
      chart.setOption(optionRef.current, true);
    })();
    return () => {
      disposed = true;
      if (resizeHandler) window.removeEventListener('resize', resizeHandler);
      chartRef.current?.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (chartRef.current) chartRef.current.setOption(option, true);
  }, [option]);

  return <div ref={ref} style={{ width: '100%', height }} />;
}
