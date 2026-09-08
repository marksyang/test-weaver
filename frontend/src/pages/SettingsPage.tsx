import { useCallback, useEffect, useState } from 'react';
import {
  App,
  Button,
  Card,
  Form,
  Input,
  Modal,
  Select,
  Switch,
  Table,
  Tabs,
  Typography,
} from 'antd';
import { KeyOutlined, PlusOutlined, ReloadOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { auditApi } from '../api/audit';
import { usersApi } from '../api/users';
import type { AuditLog } from '../types/audit';
import type { ManagedUser } from '../types/user';

const { Text } = Typography;
const errMsg = (e: unknown) => (e instanceof Error ? e.message : String(e));

const ROLE_OPTIONS = [
  { label: 'admin', value: 'admin' },
  { label: 'qa_lead', value: 'qa_lead' },
  { label: 'tester', value: 'tester' },
];

// FR-5 設定頁（admin-only）：帳號管理 + 稽核日誌
export default function SettingsPage() {
  const { message } = App.useApp();

  // ---- 帳號管理 ----
  const [users, setUsers] = useState<ManagedUser[]>([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [resetTarget, setResetTarget] = useState<ManagedUser | null>(null);
  const [createForm] = Form.useForm();
  const [resetForm] = Form.useForm();

  const loadUsers = useCallback(async () => {
    setUsersLoading(true);
    try {
      setUsers(await usersApi.list());
    } catch (e) {
      message.error(errMsg(e));
    } finally {
      setUsersLoading(false);
    }
  }, [message]);

  // ---- 稽核日誌 ----
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const loadLogs = useCallback(async () => {
    setLogsLoading(true);
    try {
      setLogs(await auditApi.logs(100));
    } catch (e) {
      message.error(errMsg(e));
    } finally {
      setLogsLoading(false);
    }
  }, [message]);

  useEffect(() => {
    loadUsers();
    loadLogs();
  }, [loadUsers, loadLogs]);

  const handleCreate = async () => {
    const v = await createForm.validateFields();
    try {
      await usersApi.create(v);
      message.success('已建立帳號');
      setCreateOpen(false);
      createForm.resetFields();
      loadUsers();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const handleRole = async (u: ManagedUser, role: string) => {
    try {
      await usersApi.update(u.id, { role });
      message.success(`已更新 ${u.username} 角色`);
      loadUsers();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const handleToggleActive = async (u: ManagedUser, active: boolean) => {
    try {
      await usersApi.update(u.id, { is_active: active });
      message.success(active ? '已啟用' : '已停用');
      loadUsers();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const handleReset = async () => {
    const v = await resetForm.validateFields();
    if (!resetTarget) return;
    try {
      await usersApi.update(resetTarget.id, { password: v.password });
      message.success(`已重設 ${resetTarget.username} 密碼`);
      setResetTarget(null);
      resetForm.resetFields();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const userColumns: ColumnsType<ManagedUser> = [
    { title: '帳號', dataIndex: 'username', key: 'username' },
    {
      title: '角色',
      dataIndex: 'role',
      key: 'role',
      render: (v, r) => (
        <Select
          size="small"
          style={{ width: 120 }}
          value={v}
          options={ROLE_OPTIONS}
          onChange={(nv) => handleRole(r, nv)}
        />
      ),
    },
    {
      title: '狀態',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (v, r) => <Switch size="small" checked={v} onChange={(nv) => handleToggleActive(r, nv)} />,
    },
    {
      title: '建立時間',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (v) => (v ? new Date(v).toLocaleString() : '-'),
    },
    {
      title: '操作',
      key: 'op',
      render: (_, r) => (
        <Button size="small" icon={<KeyOutlined />} onClick={() => setResetTarget(r)}>
          重設密碼
        </Button>
      ),
    },
  ];

  const logColumns: ColumnsType<AuditLog> = [
    {
      title: '時間',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (v) => (v ? new Date(v).toLocaleString() : '-'),
    },
    { title: '使用者', dataIndex: 'username', key: 'username', render: (v) => v ?? '-' },
    { title: '動作', dataIndex: 'action', key: 'action' },
    { title: 'Method', dataIndex: 'method', key: 'method', render: (v) => <Text code>{v}</Text> },
    { title: 'Path', dataIndex: 'path', key: 'path', render: (v) => <Text code>{v}</Text> },
    { title: 'Status', dataIndex: 'status_code', key: 'status_code', render: (v) => <Text type={v < 400 ? 'success' : 'danger'}>{v}</Text> },
    { title: 'IP', dataIndex: 'ip', key: 'ip', render: (v) => v ?? '-' },
  ];

  return (
    <Card title="系統設定（admin）">
      <Tabs
        items={[
          {
            key: 'users',
            label: '帳號管理',
            children: (
              <>
                <div style={{ marginBottom: 12 }}>
                  <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
                    新增帳號
                  </Button>
                </div>
                <Table
                  rowKey="id"
                  size="small"
                  loading={usersLoading}
                  dataSource={users}
                  columns={userColumns}
                  pagination={{ pageSize: 10 }}
                />
              </>
            ),
          },
          {
            key: 'audit',
            label: '稽核日誌',
            children: (
              <>
                <div style={{ marginBottom: 12 }}>
                  <Button size="small" icon={<ReloadOutlined />} loading={logsLoading} onClick={loadLogs}>
                    重新整理
                  </Button>
                </div>
                <Table
                  rowKey="id"
                  size="small"
                  loading={logsLoading}
                  dataSource={logs}
                  columns={logColumns}
                  pagination={{ pageSize: 10 }}
                />
              </>
            ),
          },
        ]}
      />

      <Modal title="新增帳號" open={createOpen} onOk={handleCreate} onCancel={() => setCreateOpen(false)} okText="建立">
        <Form form={createForm} layout="vertical" initialValues={{ role: 'tester' }}>
          <Form.Item name="username" label="帳號" rules={[{ required: true, message: '請輸入帳號' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="password" label="密碼" rules={[{ required: true, min: 4, message: '至少 4 字' }]}>
            <Input.Password />
          </Form.Item>
          <Form.Item name="role" label="角色" rules={[{ required: true }]}>
            <Select options={ROLE_OPTIONS} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`重設密碼：${resetTarget?.username ?? ''}`}
        open={!!resetTarget}
        onOk={handleReset}
        onCancel={() => setResetTarget(null)}
        okText="重設"
      >
        <Form form={resetForm} layout="vertical">
          <Form.Item name="password" label="新密碼" rules={[{ required: true, min: 4, message: '至少 4 字' }]}>
            <Input.Password />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
