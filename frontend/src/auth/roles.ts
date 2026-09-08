// FR-5 / M8 角色 → 可存取選單路徑（純邏輯，供前端選單過濾 + 測試）
export const ROLE_MENU: Record<string, string[]> = {
  admin: ['/rag', '/plan', '/self-test', '/defect', '/report', '/platform', '/settings', '/teams'],
  qa_lead: ['/rag', '/plan', '/self-test', '/defect', '/report'],
  tester: ['/rag', '/plan', '/self-test', '/defect'],
};

/** 回傳角色可存取的選單路徑；未知角色退化為 tester（最小權限）。 */
export function allowedPathsForRole(role: string): string[] {
  return ROLE_MENU[role] ?? ROLE_MENU.tester;
}

/** 多團隊（v1.1 T2）：能否管理「當前團隊」成員 = platform admin 或 該團隊 owner。 */
export function canManageTeam(
  role: string,
  myRole: string | null | undefined,
): boolean {
  return role === 'admin' || myRole === 'owner';
}
