export interface Project {
  id: number;
  name: string;
  description?: string | null;
  status: string;
}

export interface SpecFile {
  id: number;
  project_id: number;
  file_name: string;
  format: string;
  status: 'pending' | 'processing' | 'done' | 'error';
  char_count?: number | null;
}

export interface Category {
  id: number;
  name: string;
  code: string;
  description?: string | null;
}

export interface TestItemRow {
  id: number;
  name: string;
  description: string | null;
  is_newly_created: boolean;
  source_spec_file_id: number | null;
  category: { id: number; name: string; code: string } | null;
  matched_by: 'exact' | 'new' | 'embedding' | 'manual' | null;
  similarity: number | null;
}

export interface TaskStatus {
  task_id: string;
  state:
    | 'PENDING'
    | 'RECEIVED'
    | 'STARTED'
    | 'PROGRESS'
    | 'RETRY'
    | 'SUCCESS'
    | 'FAILURE'
    | 'REVOKED';
  result?: unknown;
}
