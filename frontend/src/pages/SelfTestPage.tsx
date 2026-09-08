import { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  Form,
  Input,
  Radio,
  Row,
  Select,
  Space,
  Table,
  Tag,
  message,
} from 'antd';
import { m1Api } from '../api/m1';
import { m2Api } from '../api/m2';
import { m3Api } from '../api/m3';
import type { Project } from '../types/m1';
import type { PlanTree, TestPlan } from '../types/m2';
import type { SelfTest } from '../types/m3';

const errMsg = (e: unknown) => (e instanceof Error ? e.message : String(e));
const RESULT_COLOR: Record<string, string> = { pass: 'green', fail: 'red' };

export default function SelfTestPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<number | null>(null);
  const [plans, setPlans] = useState<TestPlan[]>([]);
  const [planId, setPlanId] = useState<number | null>(null);
  const [tree, setTree] = useState<PlanTree | null>(null);
  const [selfTests, setSelfTests] = useState<SelfTest[]>([]);
  const [resultFilter, setResultFilter] = useState<string | undefined>(undefined);
  const [err, setErr] = useState<string | null>(null);
  const [form] = Form.useForm();

  // 專案
  useEffect(() => {
    m1Api
      .listProjects()
      .then((ps) => {
        setProjects(ps);
        setProjectId((cur) => cur ?? (ps[0]?.id ?? null));
      })
      .catch((e) => setErr(errMsg(e)));
  }, []);

  // 切換專案：載入計畫、重置 plan / self-tests
  useEffect(() => {
    if (projectId == null) return;
    setErr(null);
    setPlanId(null);
    setTree(null);
    m2Api.listPlans(projectId).then(setPlans).catch((e) => setErr(errMsg(e)));
  }, [projectId]);

  // 切換計畫：載入三層樹（供 Function/Case 選項）
  useEffect(() => {
    if (planId == null) {
      setTree(null);
      return;
    }
    m2Api.tree(planId).then(setTree).catch((e) => setErr(errMsg(e)));
  }, [planId]);

  // 自測列表（隨專案 / 篩選條件）
  const loadSelfTests = useCallback(() => {
    if (projectId == null) return;
    m3Api
      .listSelfTests(projectId, resultFilter ? { result: resultFilter } : {})
      .then(setSelfTests)
      .catch((e) => setErr(errMsg(e)));
  }, [projectId, resultFilter]);
  useEffect(() => {
    loadSelfTests();
  }, [loadSelfTests]);

  const selectedFunctionId = Form.useWatch('test_function_id', form);
  const functionOptions = (tree?.functions ?? []).map((f) => ({ value: f.id, label: f.name }));
  const caseOptions = (
    tree?.functions.find((f) => f.id === selectedFunctionId)?.cases ?? []
  ).map((c) => ({ value: c.id, label: c.name }));

  const submit = async () => {
    let values;
    try {
      values = await form.validateFields();
    } catch {
      return; // 表單驗證失敗（缺 Function / Case）
    }
    try {
      await m3Api.createSelfTest({
        project_id: projectId!,
        test_function_id: values.test_function_id,
        test_case_id: values.test_case_id,
        result: values.result,
        tester: values.tester?.trim() || undefined,
        notes: values.notes?.trim() || undefined,
      });
      message.success('自測已記錄');
      form.resetFields();
      loadSelfTests();
    } catch (e) {
      setErr(errMsg(e));
    }
  };

  const columns = [
    { title: 'Function', dataIndex: 'function_name', key: 'fn', render: (v: string) => <b>{v ?? '-'}</b> },
    { title: 'Case', dataIndex: 'case_name', key: 'case' },
    {
      title: '結果',
      dataIndex: 'result',
      key: 'result',
      width: 90,
      render: (v: string) => <Tag color={RESULT_COLOR[v] ?? 'default'}>{v}</Tag>,
    },
    { title: '測試者', dataIndex: 'tester', key: 'tester', render: (v: string) => v ?? '-' },
    { title: '備註', dataIndex: 'notes', key: 'notes', ellipsis: true, render: (v: string) => v ?? '-' },
    {
      title: '時間',
      dataIndex: 'executed_at',
      key: 'at',
      render: (v: string) => (v ? new Date(v).toLocaleString() : '-'),
    },
  ];

  let formArea;
  if (planId == null) {
    formArea = <Alert type="info" showIcon message="請先選擇專案與測試計畫" />;
  } else if ((tree?.functions.length ?? 0) === 0) {
    formArea = (
      <Alert
        type="warning"
        showIcon
        message="此計畫尚無 Function / Case"
        description="請先於「測試計畫」頁建立三層結構，再錄入自測。"
      />
    );
  } else {
    formArea = (
      <Form form={form} layout="vertical" initialValues={{ result: 'pass' }}>
        <Form.Item
          name="test_function_id"
          label="Test Function（必填）"
          rules={[{ required: true, message: '請選擇' }]}
        >
          <Select
            placeholder="選擇 Function"
            options={functionOptions}
            onChange={() => form.setFieldValue('test_case_id', undefined)}
          />
        </Form.Item>
        <Form.Item
          name="test_case_id"
          label="Test Case（必填）"
          rules={[{ required: true, message: '請選擇' }]}
        >
          <Select
            placeholder={selectedFunctionId ? '選擇 Case' : '先選 Function'}
            options={caseOptions}
            disabled={!selectedFunctionId}
          />
        </Form.Item>
        <Form.Item name="result" label="結果（必填）" rules={[{ required: true }]}>
          <Radio.Group
            options={[
              { value: 'pass', label: 'Pass' },
              { value: 'fail', label: 'Fail' },
            ]}
          />
        </Form.Item>
        <Form.Item name="tester" label="測試者">
          <Input placeholder="選填" />
        </Form.Item>
        <Form.Item name="notes" label="備註">
          <Input.TextArea rows={2} placeholder="選填" />
        </Form.Item>
        <Button type="primary" onClick={submit} block>
          記錄自測
        </Button>
      </Form>
    );
  }

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Alert
        type="info"
        showIcon
        message="自測（FR-2a / M3）"
        description="每筆自測必須同時綁定一個 Test Function 與其下的 Test Case，缺任一即拒收。案例選項依所選 Function 過濾，確保對應一致。"
      />
      {err && <Alert type="error" showIcon message={err} />}

      <Card title="專案 / 計畫">
        <Space wrap>
          <Select
            style={{ minWidth: 200 }}
            placeholder="專案"
            value={projectId ?? undefined}
            onChange={(v) => setProjectId(v)}
            options={projects.map((p) => ({ value: p.id, label: p.name }))}
          />
          <Select
            style={{ minWidth: 200 }}
            placeholder="測試計畫"
            value={planId ?? undefined}
            onChange={(v) => setPlanId(v)}
            options={plans.map((p) => ({ value: p.id, label: p.name }))}
            notFoundContent="尚無計畫"
          />
        </Space>
      </Card>

      <Row gutter={16}>
        <Col xs={24} md={9}>
          <Card title="錄入自測">{formArea}</Card>
        </Col>
        <Col xs={24} md={15}>
          <Card
            title="自測紀錄"
            extra={
              <Select
                allowClear
                placeholder="篩選結果"
                value={resultFilter}
                onChange={(v) => setResultFilter(v)}
                style={{ width: 120 }}
                options={[
                  { value: 'pass', label: 'pass' },
                  { value: 'fail', label: 'fail' },
                ]}
              />
            }
          >
            <Table
              rowKey="id"
              size="small"
              dataSource={selfTests}
              columns={columns}
              pagination={{ pageSize: 8 }}
              locale={{ emptyText: '尚無自測紀錄' }}
            />
          </Card>
        </Col>
      </Row>
    </Space>
  );
}
