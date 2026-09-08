import { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  Form,
  Input,
  Modal,
  Radio,
  Row,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
  message,
} from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { m1Api } from '../api/m1';
import { m2Api } from '../api/m2';
import { m4Api } from '../api/m4';
import type { Project } from '../types/m1';
import type { PlanTree, TestPlan } from '../types/m2';
import type { Defect, DefectStatus } from '../types/m4';
import RevisionRequests from './RevisionRequests';

const errMsg = (e: unknown) => (e instanceof Error ? e.message : String(e));
const SEVERITY_COLOR: Record<string, string> = {
  low: 'default',
  medium: 'blue',
  high: 'orange',
  critical: 'red',
};
const STATUS_COLOR: Record<string, string> = {
  open: 'default',
  in_progress: 'processing',
  resolved: 'success',
  closed: 'blue',
};
// §6.2：open → in_progress → resolved → closed（可 reopened 回 in_progress）
const NEXT: Record<DefectStatus, DefectStatus[]> = {
  open: ['in_progress'],
  in_progress: ['resolved', 'open'],
  resolved: ['closed', 'in_progress'],
  closed: ['in_progress'],
};

export default function DefectPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<number | null>(null);
  const [plans, setPlans] = useState<TestPlan[]>([]);
  const [planId, setPlanId] = useState<number | null>(null);
  const [tree, setTree] = useState<PlanTree | null>(null);
  const [defects, setDefects] = useState<Defect[]>([]);
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);
  const [severityFilter, setSeverityFilter] = useState<string | undefined>(undefined);
  const [err, setErr] = useState<string | null>(null);
  const [form] = Form.useForm();

  const [manualModal, setManualModal] = useState(false);
  const [manualForm] = Form.useForm();

  useEffect(() => {
    m1Api
      .listProjects()
      .then((ps) => {
        setProjects(ps);
        setProjectId((cur) => cur ?? (ps[0]?.id ?? null));
      })
      .catch((e) => setErr(errMsg(e)));
  }, []);

  useEffect(() => {
    if (projectId == null) return;
    setPlanId(null);
    setTree(null);
    m2Api.listPlans(projectId).then(setPlans).catch((e) => setErr(errMsg(e)));
  }, [projectId]);

  useEffect(() => {
    if (planId == null) {
      setTree(null);
      return;
    }
    m2Api.tree(planId).then(setTree).catch((e) => setErr(errMsg(e)));
  }, [planId]);

  const loadDefects = useCallback(() => {
    m4Api
      .listDefects({ status: statusFilter, severity: severityFilter })
      .then(setDefects)
      .catch((e) => setErr(errMsg(e)));
  }, [statusFilter, severityFilter]);
  useEffect(() => {
    loadDefects();
  }, [loadDefects]);

  const caseOptions = (tree?.functions ?? []).flatMap((f) =>
    f.cases.map((c) => ({ value: c.id, label: `${f.name} / ${c.name}` })),
  );

  const runExecution = async () => {
    let values;
    try {
      values = await form.validateFields();
    } catch {
      return;
    }
    try {
      const out = await m4Api.executeCase({
        test_case_id: values.test_case_id,
        result: values.result,
        executed_by: values.executed_by?.trim() || undefined,
        actual_result: values.actual_result?.trim() || undefined,
      });
      if (out.defect) {
        message.warning(`執行失敗 → 已自動開立 Defect #${out.defect.id}`);
      } else {
        message.success(`執行完成（${out.execution.result}，無 Defect）`);
      }
      form.resetFields();
      loadDefects();
    } catch (e) {
      setErr(errMsg(e));
    }
  };

  const transition = async (id: number, status: string) => {
    try {
      await m4Api.patchDefect(id, { status });
      message.success(`Defect #${id} → ${status}`);
      loadDefects();
    } catch (e) {
      message.error(`狀態無法變更：${errMsg(e)}`);
    }
  };

  const createManual = async () => {
    let values;
    try {
      values = await manualForm.validateFields();
    } catch {
      return;
    }
    try {
      await m4Api.createDefect({ title: values.title, severity: values.severity });
      message.success('已手動建立 Defect');
      setManualModal(false);
      manualForm.resetFields();
      loadDefects();
    } catch (e) {
      setErr(errMsg(e));
    }
  };

  const columns = [
    { title: '標題', dataIndex: 'title', key: 'title', render: (v: string) => <b>{v}</b> },
    { title: '案例', dataIndex: 'case_name', key: 'case', render: (v: string) => v ?? '-' },
    {
      title: '嚴重度',
      dataIndex: 'severity',
      key: 'severity',
      width: 90,
      render: (v: string) => <Tag color={SEVERITY_COLOR[v] ?? 'default'}>{v}</Tag>,
    },
    {
      title: '狀態 / 流轉',
      dataIndex: 'status',
      key: 'status',
      width: 190,
      render: (v: DefectStatus, d: Defect) => (
        <Space direction="vertical" size={2}>
          <Tag color={STATUS_COLOR[v] ?? 'default'}>{v}</Tag>
          {NEXT[v]?.length ? (
            <Select
              size="small"
              placeholder="轉到…"
              style={{ width: 140 }}
              options={NEXT[v].map((s) => ({ value: s, label: s }))}
              onChange={(nv) => transition(d.id, nv)}
            />
          ) : (
            <span style={{ color: '#bbb' }}>-</span>
          )}
        </Space>
      ),
    },
    { title: '指派', dataIndex: 'assigned_to', key: 'assign', render: (v: string) => v ?? '-' },
    {
      title: '建立時間',
      dataIndex: 'created_at',
      key: 'at',
      render: (v: string) => (v ? new Date(v).toLocaleString() : '-'),
    },
  ];

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Alert
        type="info"
        showIcon
        message="缺陷追蹤 / 修改要求（FR-3 / FR-3a）"
        description="執行 Case 判 Fail → 自動開 Defect；Defect 無對應案例 → 自動建 Revision Request（接受 → 補建案例 + 計畫版本 +1）。"
      />

      <Tabs
        items={[
          {
            key: 'defects',
            label: '缺陷追蹤',
            children: (
              <Space direction="vertical" size={16} style={{ width: '100%' }}>
                {err && <Alert type="error" showIcon message={err} />}

                <Row gutter={16}>
        <Col xs={24} md={9}>
          <Card title="執行測試案例">
            <Form form={form} layout="vertical" initialValues={{ result: 'pass' }}>
              <Form.Item label="專案">
                <Select
                  placeholder="專案"
                  value={projectId ?? undefined}
                  onChange={(v) => setProjectId(v)}
                  options={projects.map((p) => ({ value: p.id, label: p.name }))}
                />
              </Form.Item>
              <Form.Item label="測試計畫">
                <Select
                  placeholder="計畫"
                  value={planId ?? undefined}
                  onChange={(v) => setPlanId(v)}
                  options={plans.map((p) => ({ value: p.id, label: p.name }))}
                  notFoundContent="尚無計畫"
                />
              </Form.Item>
              <Form.Item
                name="test_case_id"
                label="Test Case（必填）"
                rules={[{ required: true, message: '請選擇' }]}
              >
                <Select
                  placeholder={planId ? '選擇案例' : '先選計畫'}
                  options={caseOptions}
                  disabled={!planId || caseOptions.length === 0}
                />
              </Form.Item>
              <Form.Item name="result" label="結果（必填）" rules={[{ required: true }]}>
                <Radio.Group
                  options={[
                    { value: 'pass', label: 'Pass' },
                    { value: 'fail', label: 'Fail' },
                    { value: 'blocked', label: 'Blocked' },
                  ]}
                />
              </Form.Item>
              <Form.Item name="executed_by" label="執行者">
                <Input placeholder="選填" />
              </Form.Item>
              <Form.Item name="actual_result" label="實際結果">
                <Input.TextArea rows={2} placeholder="選填" />
              </Form.Item>
              <Button type="primary" onClick={runExecution} block>
                執行
              </Button>
            </Form>
          </Card>
        </Col>

        <Col xs={24} md={15}>
          <Card
            title="缺陷列表"
            extra={
              <Space>
                <Select
                  allowClear
                  placeholder="狀態"
                  value={statusFilter}
                  onChange={(v) => setStatusFilter(v)}
                  style={{ width: 130 }}
                  options={[
                    { value: 'open', label: 'open' },
                    { value: 'in_progress', label: 'in_progress' },
                    { value: 'resolved', label: 'resolved' },
                    { value: 'closed', label: 'closed' },
                  ]}
                />
                <Select
                  allowClear
                  placeholder="嚴重度"
                  value={severityFilter}
                  onChange={(v) => setSeverityFilter(v)}
                  style={{ width: 130 }}
                  options={[
                    { value: 'low', label: 'low' },
                    { value: 'medium', label: 'medium' },
                    { value: 'high', label: 'high' },
                    { value: 'critical', label: 'critical' },
                  ]}
                />
                <Button icon={<PlusOutlined />} onClick={() => setManualModal(true)}>
                  手動建立
                </Button>
              </Space>
            }
          >
            <Table
              rowKey="id"
              size="small"
              dataSource={defects}
              columns={columns}
              pagination={{ pageSize: 8 }}
              locale={{ emptyText: '尚無缺陷（執行 Fail 或手動建立）' }}
            />
          </Card>
        </Col>
                </Row>
              </Space>
            ),
          },
          {
            key: 'revisions',
            label: '修改要求（Revision Request）',
            children: <RevisionRequests />,
          },
        ]}
      />

      <Modal
        title="手動建立 Defect"
        open={manualModal}
        onOk={createManual}
        onCancel={() => {
          setManualModal(false);
          manualForm.resetFields();
        }}
      >
        <Form form={manualForm} layout="vertical" initialValues={{ severity: 'medium' }}>
          <Form.Item name="title" label="標題" rules={[{ required: true, message: '請輸入' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="severity" label="嚴重度">
            <Select
              options={[
                { value: 'low', label: 'low' },
                { value: 'medium', label: 'medium' },
                { value: 'high', label: 'high' },
                { value: 'critical', label: 'critical' },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}
