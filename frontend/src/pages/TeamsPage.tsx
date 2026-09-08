// 多團隊（v1.1 T2）：團隊成員管理 + 建立團隊。
import { useEffect, useState } from 'react';
import {
  App,
  Button,
  Card,
  Input,
  InputNumber,
  Popconfirm,
  Select,
  Space,
  Table,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { PlusOutlined } from '@ant-design/icons';
import { teamsApi, TEAM_ROLES, type Member } from '../api/teams';
import { useAuth } from '../auth/AuthContext';
import { canManageTeam } from '../auth/roles';
import { useTeams } from '../team/TeamContext';

const ROLE_LABELS: Record<string, string> = {
  owner: 'Owner',
  qa_lead: 'QA Lead',
  tester: 'Tester',
};

const err = (e: unknown) => (e instanceof Error ? e.message : String(e));

export default function TeamsPage() {
  const { user } = useAuth();
  const { teams, currentTeamId, setTeam, reload } = useTeams();
  const { message } = App.useApp();

  const [selTeamId, setSelTeamId] = useState<number | null>(currentTeamId);
  const [members, setMembers] = useState<Member[]>([]);
  const [loadingM, setLoadingM] = useState(false);
  const [newUserId, setNewUserId] = useState<number | null>(null);
  const [newRole, setNewRole] = useState('tester');
  const [newName, setNewName] = useState('');

  const selTeam = teams.find((t) => t.id === selTeamId);
  const canEdit = user ? canManageTeam(user.role, selTeam?.my_role) : false;

  const loadMembers = () => {
    if (selTeamId == null) return;
    setLoadingM(true);
    teamsApi
      .listMembers(selTeamId)
      .then(setMembers)
      .catch((e) => message.error(err(e)))
      .finally(() => setLoadingM(false));
  };

  useEffect(() => {
    loadMembers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selTeamId]);

  async function doAdd() {
    if (selTeamId == null || newUserId == null) return;
    try {
      await teamsApi.addMember(selTeamId, { user_id: newUserId, role: newRole });
      setNewUserId(null);
      message.success('已加入成員');
      loadMembers();
    } catch (e) {
      message.error(err(e));
    }
  }

  async function doChangeRole(uid: number, role: string) {
    if (selTeamId == null) return;
    try {
      await teamsApi.setMemberRole(selTeamId, uid, role);
    } catch (e) {
      message.error(err(e)); // 例如最後一個 owner 不可降級（400）
    } finally {
      loadMembers();
    }
  }

  async function doRemove(uid: number) {
    if (selTeamId == null) return;
    try {
      await teamsApi.removeMember(selTeamId, uid);
      message.success('已移除');
    } catch (e) {
      message.error(err(e)); // 例如最後一個 owner 不可移除（400）
    } finally {
      loadMembers();
    }
  }

  async function doCreateTeam() {
    const name = newName.trim();
    if (!name) return;
    try {
      const t = await teamsApi.create({ name });
      setNewName('');
      await reload();
      setSelTeamId(t.id);
      setTeam(t.id);
      message.success('已建立團隊');
    } catch (e) {
      message.error(err(e));
    }
  }

  const columns: ColumnsType<Member> = [
    { title: '使用者', dataIndex: 'username', key: 'u' },
    {
      title: '角色',
      dataIndex: 'role',
      key: 'r',
      render: (role: string, m) =>
        canEdit ? (
          <Select
            size="small"
            value={role}
            style={{ width: 120 }}
            onChange={(v) => doChangeRole(m.user_id, v)}
            options={TEAM_ROLES.map((r) => ({ value: r, label: ROLE_LABELS[r] }))}
          />
        ) : (
          ROLE_LABELS[role] ?? role
        ),
    },
    ...(canEdit
      ? [
          {
            title: '',
            key: 'a',
            render: (_: unknown, m: Member) => (
              <Popconfirm title="移除該成員？" onConfirm={() => doRemove(m.user_id)}>
                <Button size="small" danger>
                  移除
                </Button>
              </Popconfirm>
            ),
          },
        ]
      : []),
  ];

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card title="團隊成員">
        {selTeam == null ? (
          <Typography.Text type="secondary">尚無團隊，請先於下方建立。</Typography.Text>
        ) : (
          <>
            <Space wrap>
              <Select
                value={selTeamId ?? undefined}
                onChange={(v) => {
                  setSelTeamId(v as number);
                  setTeam(v as number);
                }}
                style={{ minWidth: 200 }}
                options={teams.map((t) => ({ value: t.id, label: t.name }))}
                placeholder="選擇團隊"
              />
              <InputNumber
                placeholder="使用者 ID"
                value={newUserId}
                onChange={(v) => setNewUserId(v as number | null)}
                min={1}
                style={{ width: 130 }}
              />
              <Select
                value={newRole}
                onChange={setNewRole}
                style={{ width: 120 }}
                options={TEAM_ROLES.map((r) => ({ value: r, label: ROLE_LABELS[r] }))}
              />
              <Button onClick={doAdd} disabled={!canEdit || newUserId == null}>
                加入成員
              </Button>
            </Space>
            <Typography.Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 12 }}>
              加入成員需填「使用者數值 ID」（管理員可在『設定 → 帳號管理』查詢）。
            </Typography.Paragraph>
            <Table<Member>
              rowKey="user_id"
              loading={loadingM}
              dataSource={members}
              columns={columns}
              pagination={false}
            />
          </>
        )}
      </Card>

      <Card title="建立新團隊">
        <Space>
          <Input
            placeholder="團隊名稱"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            style={{ width: 240 }}
          />
          <Button type="primary" icon={<PlusOutlined />} onClick={doCreateTeam} disabled={!newName.trim()}>
            建立
          </Button>
        </Space>
      </Card>
    </Space>
  );
}
