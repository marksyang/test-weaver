// FR-5 / M8 認證類型
export type Role = 'admin' | 'qa_lead' | 'tester';

export interface AuthUser {
  id: number;
  username: string;
  role: Role | string;
}

export interface LoginResult {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: AuthUser;
}
