import type {
  AsyncQueryRequest,
  IndexRequest,
  LogItem,
  QueryRequest,
  QueryResponse,
  TaskAck,
  TaskStatus,
} from '../types/rag';
import { apiFetch } from './client';

const request = apiFetch;

const post = <T,>(path: string, body: unknown) =>
  request<T>(path, { method: 'POST', body: JSON.stringify(body) });

export const ragApi = {
  index: (body: IndexRequest) => post<TaskAck>('/rag/index', body),
  query: (body: QueryRequest) => post<QueryResponse>('/rag/query', body),
  queryAsync: (body: AsyncQueryRequest) => post<TaskAck>('/rag/query/async', body),
  taskStatus: (taskId: string) => request<TaskStatus>(`/rag/tasks/${encodeURIComponent(taskId)}`),
  queryLogs: (page = 1, pageSize = 20) =>
    request<LogItem[]>(`/rag/query-logs?page=${page}&page_size=${pageSize}`),
};
