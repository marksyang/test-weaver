// 多團隊（v1.1 T2）：header 團隊切換器（>1 個團隊時為下拉）。
import { Select, Tag } from 'antd';
import { TeamOutlined } from '@ant-design/icons';
import { useTeams } from '../team/TeamContext';

export default function TeamSwitcher() {
  const { teams, currentTeamId, setTeam } = useTeams();

  if (teams.length === 0) {
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: '#999' }}>
        <TeamOutlined />
        <Tag>無團隊</Tag>
      </span>
    );
  }

  if (teams.length === 1) {
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: '#555' }}>
        <TeamOutlined />
        <Tag color="blue">{teams[0].name}</Tag>
      </span>
    );
  }

  return (
    <Select
      size="small"
      style={{ minWidth: 180 }}
      value={currentTeamId ?? undefined}
      placeholder="選擇團隊"
      onChange={(v) => setTeam(v as number)}
      options={teams.map((t) => ({ value: t.id, label: t.name }))}
      suffixIcon={<TeamOutlined />}
    />
  );
}
