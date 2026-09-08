import { useEffect, useRef, useState } from 'react';
import { ragApi } from '../api/rag';

const TERMINAL = ['SUCCESS', 'FAILURE', 'REVOKED'];

type StatusFn = (id: string) => Promise<{ state: string; result?: unknown }>;

const defaultFetch: StatusFn = (id) => ragApi.taskStatus(id);

/** 輪詢 Celery 任務狀態，回傳 taskId / state / result。
 *  `fetchStatus` 可注入（M1 傳 m1Api.taskStatus），預設使用 rag 端點。 */
export function useTask(fetchStatus: StatusFn = defaultFetch) {
  const [taskId, setTaskId] = useState<string | null>(null);
  const [state, setState] = useState<string>('');
  const [result, setResult] = useState<unknown>(null);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    if (!taskId) return;
    setState('PENDING');
    setResult(null);

    const poll = async () => {
      try {
        const s = await fetchStatus(taskId);
        setState(s.state);
        if (TERMINAL.includes(s.state)) {
          setResult(s.result ?? null);
          if (timer.current) window.clearInterval(timer.current);
        }
      } catch {
        setState('ERROR');
        if (timer.current) window.clearInterval(timer.current);
      }
    };

    poll();
    timer.current = window.setInterval(poll, 1500);
    return () => {
      if (timer.current) window.clearInterval(timer.current);
    };
  }, [taskId, fetchStatus]);

  const stopped = TERMINAL.includes(state) || state === 'ERROR';
  return {
    taskId,
    setTaskId,
    state,
    result,
    polling: Boolean(taskId) && !stopped,
  };
}
