import { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import { m1Api } from '../api/m1';
import type { Category } from '../types/m1';

const errMsg = (e: unknown) => (e instanceof Error ? e.message : String(e));

export default function PlatformPage() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const [form] = Form.useForm<{ name: string; code?: string; description?: string }>();

  const load = useCallback(() => {
    setLoading(true);
    setErr(null);
    m1Api
      .listCategories()
      .then(setCategories)
      .catch((e) => setErr(errMsg(e)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(load, [load]);

  const create = async () => {
    const values = await form.validateFields();
    setSaving(true);
    setErr(null);
    try {
      await m1Api.createCategory({
        name: values.name,
        code: values.code?.trim() || undefined,
        description: values.description?.trim() || undefined,
      });
      message.success('已建立類別');
      form.resetFields();
      load();
    } catch (e) {
      setErr(errMsg(e));
    } finally {
      setSaving(false);
    }
  };

  const columns = [
    { title: '名稱', dataIndex: 'name', key: 'name', render: (v: string) => <b>{v}</b> },
    {
      title: 'code',
      dataIndex: 'code',
      key: 'code',
      render: (v: string) => <span style={{ fontFamily: 'monospace' }}>{v}</span>,
    },
    { title: '說明', dataIndex: 'description', key: 'description' },
  ];

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card title="共通類別平台">
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="測試項目必須由此平台衍生（FR-1a）"
          description="AI 生成測試項目時會盡可能對應到既有類別；找不到對應時，會自動在此新建類別並標記 is_newly_created。"
        />
        {err && <Alert type="error" showIcon message={err} style={{ marginBottom: 16 }} />}
        <Table
          rowKey="id"
          size="middle"
          loading={loading}
          dataSource={categories}
          columns={columns}
          pagination={{ pageSize: 10 }}
          locale={{ emptyText: '尚無類別（可先手動建立，或於測試項目生成時自動建立）' }}
        />
      </Card>

      <Card title="新增類別">
        <Form
          form={form}
          layout="vertical"
          style={{ maxWidth: 560 }}
          initialValues={{ name: '', code: '', description: '' }}
        >
          <Form.Item
            label="類別名稱"
            name="name"
            rules={[{ required: true, message: '請輸入類別名稱' }]}
          >
            <Input placeholder="例：登入 / 報表 / 權限" />
          </Form.Item>
          <Form.Item label="code（選填）" name="code">
            <Input placeholder="留空則自動產生" />
          </Form.Item>
          <Form.Item label="說明（選填）" name="description">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Button type="primary" loading={saving} onClick={create}>
            建立類別
          </Button>
        </Form>
      </Card>

      <Typography.Text type="secondary">
        平台類別計 {categories.length} 筆。此頁對應計劃書 M7（platform）。
      </Typography.Text>
    </Space>
  );
}
