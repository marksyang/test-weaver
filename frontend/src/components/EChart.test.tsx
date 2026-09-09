import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, waitFor } from '@testing-library/react';

// mock 掉瘦身 echarts 模組（jsdom 沒有 canvas；動態 import('../lib/echarts') 會拿到這個 mock）
vi.mock('../lib/echarts', () => ({
  default: { init: vi.fn() },
}));

import EChart from './EChart';
import * as slim from '../lib/echarts';

const initMock = vi.mocked(slim.default).init;
type Inst = {
  setOption: ReturnType<typeof vi.fn>;
  resize: ReturnType<typeof vi.fn>;
  dispose: ReturnType<typeof vi.fn>;
};
const makeInstance = (): Inst => ({ setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn() });

type Option = Parameters<typeof EChart>[0]['option'];

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('EChart', () => {
  it('inits the chart and calls setOption(option, true)', async () => {
    const instance = makeInstance();
    initMock.mockReturnValueOnce(instance as unknown as ReturnType<typeof initMock>);
    const option = {} as Option;
    render(<EChart option={option} height={200} />);
    await waitFor(() => expect(initMock).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(instance.setOption).toHaveBeenCalledWith(option, true));
  });

  it('disposes the chart on unmount', async () => {
    const instance = makeInstance();
    initMock.mockReturnValueOnce(instance as unknown as ReturnType<typeof initMock>);
    const { unmount } = render(<EChart option={{} as Option} />);
    await waitFor(() => expect(initMock).toHaveBeenCalledTimes(1));
    unmount();
    expect(instance.dispose).toHaveBeenCalledTimes(1);
  });

  it('re-applies setOption when the option changes', async () => {
    const instance = makeInstance();
    initMock.mockReturnValueOnce(instance as unknown as ReturnType<typeof initMock>);
    const a = {} as Option;
    const b = { series: [] } as unknown as Option;
    const { rerender } = render(<EChart option={a} />);
    await waitFor(() => expect(instance.setOption).toHaveBeenCalledWith(a, true));
    rerender(<EChart option={b} />);
    await waitFor(() => expect(instance.setOption).toHaveBeenLastCalledWith(b, true));
  });
});
