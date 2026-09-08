// FR-5 帳號管理類型
export type Role = 'admin' | 'qa_lead' | 'tester';

export interface ManagedUser {
  id: number;
  username: string;
  role: Role | string;
  is_active: boolean;
  created_at: string | null;
}

export interface UserCreateBody {
  username: string;
  password: string;
  role: string;
}

export interface UserUpdateBody {
  role?: string;
  is_active?: boolean;
  password?: string;
}
