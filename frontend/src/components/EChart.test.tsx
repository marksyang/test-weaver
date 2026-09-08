import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';
import * as echarts from 'echarts';
import EChart from './EChart';

// mock 掉 echarts（jsdom 沒有 canvas）：init 每次回傳全新 instance，避免跨測試累計
vi.mock('echarts', () => ({
  init: vi.fn(() => ({ setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn() })),
}));

const echartsMock = vi.mocked(echarts);

type Inst = { setOption: ReturnType<typeof vi.fn>; resize: ReturnType<typeof vi.fn>; dispose: ReturnType<typeof vi.fn> };
const instanceFrom = (callIndex = 0): Inst => {
  const results = echartsMock.init.mock.results;
  const value = (results[callIndex] ?? results[results.length - 1])?.value;
  return value as Inst;
};

type Option = Parameters<typeof EChart>[0]['option'];

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('EChart', () => {
  it('inits the chart and calls setOption(option, true) on mount', () => {
    const option = {} as Option;
    render(<EChart option={option} height={200} />);
    expect(echartsMock.init).toHaveBeenCalledTimes(1);
    expect(instanceFrom().setOption).toHaveBeenCalledWith(option, true);
  });

  it('disposes the chart on unmount', () => {
    const option = {} as Option;
    const { unmount } = render(<EChart option={option} />);
    unmount();
    expect(instanceFrom().dispose).toHaveBeenCalledTimes(1);
  });

  it('re-applies setOption when the option changes', () => {
    const a = {} as Option;
    const b = { series: [] } as unknown as Option;
    const { rerender } = render(<EChart option={a} />);
    rerender(<EChart option={b} />);
    expect(instanceFrom().setOption).toHaveBeenLastCalledWith(b, true);
  });
});
