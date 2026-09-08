import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, renderHook } from '@testing-library/react';
import { useTask } from './useTask';

afterEach(() => cleanup());

describe('useTask', () => {
  it('initial: no task, not polling, empty state', () => {
    const { result } = renderHook(() => useTask());
    expect(result.current.taskId).toBeNull();
    expect(result.current.state).toBe('');
    expect(result.current.result).toBeNull();
    expect(result.current.polling).toBe(false);
  });

  it('resolves terminal SUCCESS with result, then stops polling', async () => {
    const fetchStatus = vi.fn().mockResolvedValue({ state: 'SUCCESS', result: { id: 5 } });
    const { result } = renderHook(() => useTask(fetchStatus));
    await act(async () => {
      result.current.setTaskId('t1');
    });
    await act(async () => {}); // flush the initial poll microtask
    expect(fetchStatus).toHaveBeenCalledWith('t1');
    expect(result.current.state).toBe('SUCCESS');
    expect(result.current.result).toEqual({ id: 5 });
    expect(result.current.polling).toBe(false);
  });

  it('keeps polling while PENDING', async () => {
    const fetchStatus = vi.fn().mockResolvedValue({ state: 'PENDING' });
    const { result } = renderHook(() => useTask(fetchStatus));
    await act(async () => {
      result.current.setTaskId('t2');
    });
    await act(async () => {});
    expect(result.current.state).toBe('PENDING');
    expect(result.current.polling).toBe(true);
  });

  it('marks ERROR when the status fetch rejects', async () => {
    const fetchStatus = vi.fn().mockRejectedValue(new Error('boom'));
    const { result } = renderHook(() => useTask(fetchStatus));
    await act(async () => {
      result.current.setTaskId('t3');
    });
    await act(async () => {});
    expect(result.current.state).toBe('ERROR');
    expect(result.current.polling).toBe(false);
  });
});
