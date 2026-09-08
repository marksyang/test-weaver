import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  Input,
  Row,
  Select,
  Space,
  Spin,
  Table,
  Tabs,
  Tag,
  Typography,
  Upload,
  message,
} from 'antd';
import { InboxOutlined, PlusOutlined } from '@ant-design/icons';
import { m1Api } from '../api/m1';
import type { Project, SpecFile, TestItemRow } from '../types/m1';
import { useTask } from '../hooks/useTask';
import TestPlanTree from './TestPlanTree';

const { Dragger } = Upload;
const errMsg = (e: unknown) => (e instanceof Error ? e.message : String(e));

const STATUS_COLOR: Record<string, string> = {
  done: 'green',
  processing: 'blue',
  pending: 'default',
  error: 'red',
};

const MATCH_COLOR: Record<string, string> = {
  new: 'orange',
  exact: 'green',
  embedding: 'blue',
  manual: 'purple',
};

export default function PlanPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<number | null>(null);
  const [newName, setNewName] = useState('');
  const [specs, setSpecs] = useState<SpecFile[]>([]);
  const [items, setItems] = useState<TestItemRow[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const task = useTask(m1Api.taskStatus);
  const handled = useRef<string | null>(null);

  // 專案列表
  const loadProjects = useCallback(async () => {
    try {
      const ps = await m1Api.listProjects();
      setProjects(ps);
      setProjectId((cur) => cur ?? (ps[0]?.id ?? null));
    } catch (e) {
      setErr(errMsg(e));
    }
  }, []);
  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  // 切換專案時載入規格書與測試項目
  useEffect(() => {
    if (projectId == null) return;
    setErr(null);
    m1Api.listSpecs(projectId).then(setSpecs).catch((e) => setErr(errMsg(e)));
    m1Api.listTestItems(projectId).then(setItems).catch((e) => setErr(errMsg(e)));
  }, [projectId]);

  // 生成任務結束（SUCCESS/FAILURE）→ 刷新測試項目
  useEffect(() => {
    const tid = task.taskId;
    if (!tid || handled.current === tid) return;
    if (task.state === 'SUCCESS') {
      handled.current = tid;
      if (projectId != null)
        m1Api.listTestItems(projectId).then(setItems).catch((e) => setErr(errMsg(e)));
      const gen = (task.result as { generated?: number } | undefined)?.generated;
      message.success(`生成完成${typeof gen === 'number' ? `：${gen} 項` : ''}`);
    } else if (task.state === 'FAILURE') {
      handled.current = tid;
      setErr('生成失敗，請查看後端/worker 日誌');
    }
  }, [task.state, task.result, task.taskId, projectId]);

  const createProject = async () => {
    const name = newName.trim();
    if (!name) {
      message.warning('請輸入專案名稱');
      return;
    }
    try {
      const p = await m1Api.createProject({ name });
      setNewName('');
      const ps = await m1Api.listProjects();
      setProjects(ps);
      setProjectId(p.id);
      message.success('已建立專案');
    } catch (e) {
      setErr(errMsg(e));
    }
  };

  const onUpload = async (file: File) => {
    if (projectId == null) {
      message.warning('請先選擇專案');
      return false;
    }
    setUploading(true);
    setErr(null);
    try {
      const sf = await m1Api.uploadSpec(projectId, file);
      message.success(`已上傳並解析（${sf.char_count ?? 0} 字元，狀態 ${sf.status}）`);
      setSpecs(await m1Api.listSpecs(projectId));
    } catch (e) {
      setErr(errMsg(e));
    } finally {
      setUploading(false);
    }
    return false; // 阻止 antd 預設上傳
  };

  const generate = async (specFileId: number) => {
    if (projectId == null) return;
    try {
      const r = await m1Api.generateItems(projectId, specFileId);
      handled.current = null;
      task.setTaskId(r.task_id);
      message.info('已送出 AI 生成任務');
    } catch (e) {
      setErr(errMsg(e));
    }
  };

  const specColumns = [
    { title: '檔名', dataIndex: 'file_name', key: 'file_name' },
    { title: '格式', dataIndex: 'format', key: 'format' },
    {
      title: '狀態',
      dataIndex: 'status',
      key: 'status',
      render: (v: string) => <Tag color={STATUS_COLOR[v] ?? 'default'}>{v}</Tag>,
    },
    { title: '字元數', dataIndex: 'char_count', key: 'char_count' },
    {
      title: '操作',
      key: 'op',
      render: (_: unknown, r: SpecFile) => (
        <Button
          type="link"
          size="small"
          disabled={r.status !== 'done'}
          onClick={() => generate(r.id)}
        >
          AI 生成測試項目
        </Button>
      ),
    },
  ];

  const itemColumns = [
    { title: '名稱', dataIndex: 'name', key: 'name', render: (v: string) => <b>{v}</b> },
    {
      title: '平台類別',
      key: 'category',
      render: (_: unknown, r: TestItemRow) =>
        r.category ? (
          <Space size={4}>
            {r.category.name}
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {r.category.code}
            </Typography.Text>
          </Space>
        ) : (
          '-'
        ),
    },
    {
      title: '匹配',
      dataIndex: 'matched_by',
      key: 'matched_by',
      render: (v: string | null) =>
        v ? <Tag color={MATCH_COLOR[v] ?? 'default'}>{v}</Tag> : '-',
    },
    {
      title: '相似度',
      dataIndex: 'similarity',
      key: 'similarity',
      render: (v: number | null) => (v == null ? '-' : v.toFixed(3)),
    },
    {
      title: '新建',
      dataIndex: 'is_newly_created',
      key: 'is_newly_created',
      render: (v: boolean) => (v ? <Tag color="orange">新增</Tag> : '-'),
    },
    {
      title: '說明',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
  ];

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Alert
        type="info"
        showIcon
        message="測試計畫工作台"
        description="FR-1：規格書 → AI 生成測試項目（共通類別平台衍生）；FR-2：Test Plan → Function → Case 三層結構與版本。"
      />

      <Card title="專案">
        <Row gutter={12}>
          <Col flex="auto">
            <Select
              style={{ width: '100%', minWidth: 240 }}
              placeholder="選擇專案"
              value={projectId ?? undefined}
              onChange={(v) => setProjectId(v)}
              options={projects.map((p) => ({ value: p.id, label: p.name }))}
            />
          </Col>
          <Col>
            <Input
              placeholder="新專案名稱"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              style={{ width: 200 }}
            />
          </Col>
          <Col>
            <Button type="primary" icon={<PlusOutlined />} onClick={createProject}>
              新增專案
            </Button>
          </Col>
        </Row>
      </Card>

      {projectId == null ? (
        <Alert type="warning" showIcon message="請先選擇或新增專案" />
      ) : (
        <Tabs
          items={[
            {
              key: 'items',
              label: '規格書 → 測試項目',
              children: (
                <Space direction="vertical" size={16} style={{ width: '100%' }}>
                  {err && <Alert type="error" showIcon message={err} />}

                  <Card title="規格書">
                    <Dragger
                      accept=".txt,.md,.docx,.pdf"
                      showUploadList={false}
                      beforeUpload={onUpload}
                      disabled={uploading}
                    >
                      <p className="ant-upload-drag-icon">
                        {uploading ? <Spin /> : <InboxOutlined />}
                      </p>
                      <p className="ant-upload-text">拖曳或點擊上傳規格書</p>
                    </Dragger>

                    <Table
                      rowKey="id"
                      size="middle"
                      style={{ marginTop: 16 }}
                      dataSource={specs}
                      columns={specColumns}
                      pagination={{ pageSize: 5 }}
                      locale={{ emptyText: '尚未上傳規格書' }}
                    />
                  </Card>

                  <Card
                    title="測試項目"
                    extra={
                      task.polling ? (
                        <Space>
                          <Spin size="small" />
                          <Tag color="processing">生成中… {task.state}</Tag>
                        </Space>
                      ) : null
                    }
                  >
                    <Table
                      rowKey="id"
                      size="middle"
                      dataSource={items}
                      columns={itemColumns}
                      pagination={{ pageSize: 10 }}
                      locale={{ emptyText: '尚無測試項目（上傳規格書後點「AI 生成測試項目」）' }}
                    />
                  </Card>
                </Space>
              ),
            },
            {
              key: 'plan',
              label: '測試計畫結構（三層 + 版本）',
              children: <TestPlanTree projectId={projectId} />,
            },
          ]}
        />
      )}
    </Space>
  );
}
