import { useEffect, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  message,
  Select,
  Space,
  Spin,
  Table,
  Tabs,
  Tag,
  Typography,
} from 'antd';
import {
  PlusCircleOutlined,
  ReloadOutlined,
  SearchOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import { ragApi } from '../api/rag';
import type {
  Hit,
  IndexRequest,
  LogItem,
  QueryRequest,
  QueryResponse,
  SourceType,
} from '../types/rag';
import { useTask } from '../hooks/useTask';

const SOURCE_TYPES: { value: SourceType; label: string }[] = [
  { value: 'spec', label: 'spec（規格書）' },
  { value: 'plan', label: 'plan（測試計畫）' },
  { value: 'case', label: 'case（測試案例）' },
  { value: 'defect', label: 'defect（缺陷）' },
  { value: 'report', label: 'report（報表）' },
];

const sourceTypeLabel = (v: string) =>
  SOURCE_TYPES.find((s) => s.value === v)?.label ?? v;

const hitColumns = [
  { title: '相似度', dataIndex: 'score', width: 100, render: (v: number) => v.toFixed(3) },
  {
    title: '來源',
    dataIndex: 'source_type',
    width: 160,
    render: (v: string, r: Hit) => (
      <Tag color="blue">
        {sourceTypeLabel(v)} #{r.source_id}
      </Tag>
    ),
  },
  {
    title: '章節',
    dataIndex: 'section_title',
    width: 140,
    render: (v: string | null) => v ?? '-',
  },
  { title: '內容', dataIndex: 'content' },
];

// ── Tab 1：建立索引 ─────────────────────────────────────────────
function IndexTab() {
  const [form] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);
  const task = useTask();

  const onSubmit = async (values: IndexRequest) => {
    setSubmitting(true);
    try {
      const ack = await ragApi.index(values);
      message.success(`已送出索引任務：${ack.task_id}`);
      task.setTaskId(ack.task_id);
    } catch (e) {
      message.error(String(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card title="建立 / 更新向量索引（非同步）" size="small">
        <Form form={form} layout="vertical" onFinish={onSubmit} initialValues={{ source_type: 'spec' }}>
          <Space wrap>
            <Form.Item name="source_type" label="來源類型" rules={[{ required: true }]}>
              <Select style={{ width: 200 }} options={SOURCE_TYPES} />
            </Form.Item>
            <Form.Item name="source_id" label="來源 ID" rules={[{ required: true }]}>
              <InputNumber min={1} style={{ width: 140 }} placeholder="例：1001" />
            </Form.Item>
            <Form.Item name="section_title" label="章節標題（可選）">
              <Input style={{ width: 200 }} placeholder="例：功能規格" />
            </Form.Item>
          </Space>
          <Form.Item name="text" label="文字內容" rules={[{ required: true }]}>
            <Input.TextArea rows={6} placeholder="貼上規格書 / 計畫 / 缺陷文字，將切塊並建立向量索引" />
          </Form.Item>
          <Button type="primary" htmlType="submit" icon={<PlusCircleOutlined />} loading={submitting}>
            建立索引
          </Button>
        </Form>
      </Card>

      {task.taskId && (
        <Card size="small" title={`索引任務狀態：${task.state}`}>
          <Space>
            {task.polling && <Spin size="small" />}
            <Typography.Text code>{task.taskId}</Typography.Text>
          </Space>
          {task.state === 'SUCCESS' && task.result !== null && (
            <Alert type="success" style={{ marginTop: 12 }} message={`完成：${JSON.stringify(task.result)}`} />
          )}
          {(task.state === 'FAILURE' || task.state === 'ERROR') && (
            <Alert type="error" style={{ marginTop: 12 }} message={JSON.stringify(task.result)} />
          )}
        </Card>
      )}
    </Space>
  );
}

// ── Tab 2：同步查詢 ─────────────────────────────────────────────
function QueryTab() {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<QueryResponse | null>(null);

  const onSubmit = async (values: QueryRequest) => {
    setLoading(true);
    try {
      setData(await ragApi.query(values));
    } catch (e) {
      message.error(String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card title="同步檢索（快速路徑，無 LLM）" size="small">
        <Form form={form} layout="vertical" onFinish={onSubmit} initialValues={{ top_k: 5 }}>
          <Space wrap>
            <Form.Item name="question" label="問題" rules={[{ required: true }]}>
              <Input style={{ width: 360 }} placeholder="例：登入如何驗證" />
            </Form.Item>
            <Form.Item name="top_k" label="Top-K">
              <InputNumber min={1} max={50} />
            </Form.Item>
            <Form.Item name="source_types" label="來源篩選（可選）">
              <Select
                mode="multiple"
                allowClear
                style={{ minWidth: 200 }}
                options={SOURCE_TYPES}
                placeholder="全部"
              />
            </Form.Item>
          </Space>
          <Button type="primary" htmlType="submit" icon={<SearchOutlined />} loading={loading}>
            查詢
          </Button>
        </Form>
      </Card>

      {data && (
        <Card size="small" title={`檢索結果（${data.hits.length} 段）`}>
          <Table rowKey="vector_store_id" size="small" columns={hitColumns} dataSource={data.hits} />
          {data.context.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <Typography.Text strong>組入 prompt 的 context：</Typography.Text>
              <pre style={{ background: '#fafafa', padding: 12, marginTop: 8, whiteSpace: 'pre-wrap' }}>
                {data.context.join('\n\n')}
              </pre>
            </div>
          )}
        </Card>
      )}
    </Space>
  );
}

// ── Tab 3：AI 查詢（非同步）─────────────────────────────────────
function AsyncTab() {
  const [form] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);
  const task = useTask();
  const result = task.result as QueryResponse | undefined;

  const onSubmit = async (values: QueryRequest) => {
    setSubmitting(true);
    try {
      const ack = await ragApi.queryAsync({ ...values, answer: true });
      task.setTaskId(ack.task_id);
    } catch (e) {
      message.error(String(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card title="AI 查詢（非同步：檢索 + LLM 答案）" size="small">
        <Form form={form} layout="vertical" onFinish={onSubmit} initialValues={{ top_k: 5 }}>
          <Space wrap>
            <Form.Item name="question" label="問題" rules={[{ required: true }]}>
              <Input style={{ width: 360 }} placeholder="例：登入失敗常見原因" />
            </Form.Item>
            <Form.Item name="top_k" label="Top-K">
              <InputNumber min={1} max={50} />
            </Form.Item>
          </Space>
          <Button type="primary" htmlType="submit" icon={<ThunderboltOutlined />} loading={submitting}>
            送出查詢
          </Button>
          <Typography.Text type="secondary" style={{ marginLeft: 12 }}>
            需後端設定 LLM_API_KEY；未設時回 fallback 文字。
          </Typography.Text>
        </Form>
      </Card>

      {task.taskId && (
        <Card size="small" title={`任務狀態：${task.state}`}>
          <Space>
            {task.polling && <Spin size="small" />}
            <Typography.Text code>{task.taskId}</Typography.Text>
          </Space>
          {task.state === 'SUCCESS' && result && (
            <div style={{ marginTop: 12 }}>
              <Typography.Title level={5}>AI 答案</Typography.Title>
              <Typography.Paragraph>{result.answer}</Typography.Paragraph>
              <Table rowKey="vector_store_id" size="small" columns={hitColumns} dataSource={result.hits ?? []} />
            </div>
          )}
          {(task.state === 'FAILURE' || task.state === 'ERROR') && (
            <Alert type="error" style={{ marginTop: 12 }} message={JSON.stringify(task.result)} />
          )}
        </Card>
      )}
    </Space>
  );
}

// ── Tab 4：查詢紀錄 ─────────────────────────────────────────────
function LogsTab() {
  const [rows, setRows] = useState<LogItem[]>([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      setRows(await ragApi.queryLogs());
    } catch (e) {
      message.error(String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '問題', dataIndex: 'question' },
    { title: 'Top-K', dataIndex: 'top_k', width: 80 },
    { title: '答案', dataIndex: 'answer', ellipsis: true, render: (v: string | null) => v ?? '-' },
    {
      title: '時間',
      dataIndex: 'created_at',
      width: 180,
      render: (v: string) => (v ? dayjs(v).format('YYYY-MM-DD HH:mm:ss') : '-'),
    },
  ];

  return (
    <Card
      size="small"
      title="查詢紀錄"
      extra={
        <Button icon={<ReloadOutlined />} onClick={load} loading={loading}>
          刷新
        </Button>
      }
    >
      <Table rowKey="id" size="small" columns={columns} dataSource={rows} loading={loading} />
    </Card>
  );
}

// ── Page ───────────────────────────────────────────────────────
export default function RagPage() {
  return (
    <Card>
      <Tabs
        items={[
          { key: 'query', label: '查詢', children: <QueryTab /> },
          { key: 'index', label: '建立索引', children: <IndexTab /> },
          { key: 'async', label: 'AI 查詢', children: <AsyncTab /> },
          { key: 'logs', label: '查詢紀錄', children: <LogsTab /> },
        ]}
      />
    </Card>
  );
}
