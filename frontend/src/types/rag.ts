// 對應後端 backend/app/api/v1/rag.py 的 Pydantic schemas
export type SourceType = 'spec' | 'plan' | 'case' | 'defect' | 'report';

export interface IndexRequest {
  source_type: SourceType;
  source_id: number;
  text: string;
  section_title?: string;
  metadata?: Record<string, unknown>;
}

export interface QueryRequest {
  question: string;
  top_k?: number;
  source_types?: SourceType[];
  filters?: Record<string, unknown>;
}

export interface AsyncQueryRequest extends QueryRequest {
  answer?: boolean;
  user_id?: number | null;
}

export interface TaskAck {
  task_id: string;
  status: string;
}

export interface Hit {
  vector_store_id: string;
  score: number;
  source_type: SourceType;
  source_id: number;
  content: string;
  section_title: string | null;
  metadata: Record<string, unknown>;
}

export interface QueryResponse {
  question: string;
  hits: Hit[];
  context: string[];
  answer: string | null;
}

export interface TaskStatus {
  task_id: string;
  state: string;
  result?: unknown;
}

export interface LogItem {
  id: number;
  question: string;
  top_k: number;
  answer: string | null;
  created_at: string;
}
