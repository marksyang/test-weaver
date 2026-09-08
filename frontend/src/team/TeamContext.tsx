// 多團隊（v1.1 T2）：當前團隊 context（載入 /teams、記憶選擇、切換）。
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { teamsApi, type Team } from '../api/teams';
import { useAuth } from '../auth/AuthContext';
import { canManageTeam } from '../auth/roles';

const TEAM_KEY = 'tw_team_id';

interface TeamContextValue {
  teams: Team[];
  currentTeam: Team | null;
  currentTeamId: number | null;
  canManage: boolean; // platform admin 或 當前團隊 owner
  loading: boolean;
  setTeam: (id: number) => void;
  reload: () => Promise<void>;
}

const TeamContext = createContext<TeamContextValue | null>(null);

function readTeamId(): number | null {
  try {
    const v = localStorage.getItem(TEAM_KEY);
    return v ? Number(v) : null;
  } catch {
    return null;
  }
}
function writeTeamId(id: number | null): void {
  try {
    if (id == null) localStorage.removeItem(TEAM_KEY);
    else localStorage.setItem(TEAM_KEY, String(id));
  } catch {
    /* ignore */
  }
}

export function TeamProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [teams, setTeams] = useState<Team[]>([]);
  const [currentTeamId, setCurrentTeamId] = useState<number | null>(() => readTeamId());
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    try {
      const list = await teamsApi.list();
      setTeams(list);
      setCurrentTeamId((prev) => {
        const stored = prev ?? readTeamId();
        if (list.length === 0) {
          writeTeamId(null);
          return null;
        }
        const valid = stored != null && list.some((t) => t.id === stored);
        const id = valid ? (stored as number) : list[0].id;
        writeTeamId(id);
        return id;
      });
    } catch {
      setTeams([]);
      setCurrentTeamId(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload, user?.id]);

  const setTeam = useCallback((id: number) => {
    setCurrentTeamId(id);
    writeTeamId(id);
  }, []);

  const currentTeam = useMemo(
    () => teams.find((t) => t.id === currentTeamId) ?? null,
    [teams, currentTeamId],
  );
  const canManage = useMemo(
    () => (user ? canManageTeam(user.role, currentTeam?.my_role) : false),
    [user, currentTeam],
  );

  const value = useMemo(
    () => ({ teams, currentTeam, currentTeamId, canManage, loading, setTeam, reload }),
    [teams, currentTeam, currentTeamId, canManage, loading, setTeam, reload],
  );
  return <TeamContext.Provider value={value}>{children}</TeamContext.Provider>;
}

export function useTeams(): TeamContextValue {
  const ctx = useContext(TeamContext);
  if (!ctx) throw new Error('useTeams must be used within <TeamProvider>');
  return ctx;
}
