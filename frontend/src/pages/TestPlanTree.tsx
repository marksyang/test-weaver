import { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { m2Api } from '../api/m2';
import type { CaseStatus, PlanStatus, PlanTree, TestCase } from '../types/m2';

const errMsg = (e: unknown) => (e instanceof Error ? e.message : String(e));

const PLAN_STATUSES: PlanStatus[] = ['draft', 'in_progress', 'completed', 'archived'];
const CASE_STATUSES: CaseStatus[] = ['draft', 'ready', 'passed', 'failed', 'blocked'];
const PLAN_COLOR: Record<string, string> = {
  draft: 'default',
  in_progress: 'processing',
  completed: 'success',
  archived: 'default',
};
const CASE_COLOR: Record<string, string> = {
  draft: 'default',
  ready: 'blue',
  passed: 'green',
  failed: 'red',
  blocked: 'orange',
};
const PRIORITY_COLOR: Record<string, string> = { low: 'default', medium: 'blue', high: 'orange' };

export default function TestPlanTree({ projectId }: { projectId: number }) {
  const [plans, setPlans] = useState<{ id: number; name: string }[]>([]);
  const [planId, setPlanId] = useState<number | null>(null);
  const [tree, setTree] = useState<PlanTree | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [newPlanName, setNewPlanName] = useState('');

  const [fnModal, setFnModal] = useState(false);
  const [fnName, setFnName] = useState('');
  const [caseModalFor, setCaseModalFor] = useState<number | null>(null);
  const [caseForm] = Form.useForm();

  const loadPlans = useCallback(async () => {
    try {
      const ps = await m2Api.listPlans(projectId);
      setPlans(ps);
      setPlanId((cur) => (cur && ps.some((p) => p.id === cur) ? cur : ps[0]?.id ?? null));
    } catch (e) {
      setErr(errMsg(e));
    }
  }, [projectId]);
  useEffect(() => {
    loadPlans();
  }, [loadPlans]);

  const loadTree = useCallback(async () => {
    if (planId == null) {
      setTree(null);
      return;
    }
    try {
      setTree(await m2Api.tree(planId));
    } catch (e) {
      setErr(errMsg(e));
    }
  }, [planId]);
  useEffect(() => {
    loadTree();
  }, [loadTree]);

  const refresh = () => {
    loadPlans();
    loadTree();
  };

  const createPlan = async () => {
    const name = newPlanName.trim();
    if (!name) {
      message.warning('請輸入計畫名稱');
      return;
    }
    try {
      await m2Api.createPlan(projectId, { name });
      setNewPlanName('');
      message.success('已建立計畫（v1 / draft）');
      refresh();
    } catch (e) {
      setErr(errMsg(e));
    }
  };

  const addFunction = async () => {
    const name = fnName.trim();
    if (!name) return;
    if (planId == null) return;
    try {
      await m2Api.createFunction(planId, { name });
      setFnModal(false);
      setFnName('');
      loadTree();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const addCase = async () => {
    let values;
    try {
      values = await caseForm.validateFields();
    } catch {
      return; // 表單驗證失敗
    }
    try {
      await m2Api.createCase(caseModalFor!, values);
      setCaseModalFor(null);
      caseForm.resetFields();
      loadTree();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const setPlanStatus = async (status: string) => {
    if (planId == null) return;
    try {
      await m2Api.patchPlan(planId, { status });
      message.success('計畫狀態已更新');
      refresh();
    } catch (e) {
      message.error(`狀態無法變更：${errMsg(e)}`);
    }
  };

  const bumpVersion = async () => {
    if (planId == null) return;
    try {
      await m2Api.createRevision(planId);
      message.success('已提升版本（回到 draft）');
      refresh();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const setCaseStatus = async (caseId: number, status: string) => {
    try {
      await m2Api.patchCaseStatus(caseId, status);
      loadTree();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const caseColumns = [
    { title: '案例', dataIndex: 'name', key: 'name', render: (v: string) => <b>{v}</b> },
    {
      title: '優先度',
      dataIndex: 'priority',
      key: 'priority',
      width: 90,
      render: (v: string) => <Tag color={PRIORITY_COLOR[v] ?? 'default'}>{v}</Tag>,
    },
    {
      title: '狀態',
      key: 'status',
      width: 130,
      render: (_: unknown, c: TestCase) => (
        <Select
          size="small"
          value={c.status}
          onChange={(v) => setCaseStatus(c.id, v)}
          options={CASE_STATUSES.map((s) => ({ value: s, label: s }))}
          style={{ width: 120 }}
        />
      ),
    },
    { title: '步驟', dataIndex: 'steps', key: 'steps', ellipsis: true },
  ];

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card title="測試計畫">
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="三層結構：Test Plan → Test Function → Test Case（FR-2）"
          description="計畫具版本號與狀態機（draft → in_progress → completed → archived）；「提升版本」會 +1 並回到 draft。"
        />
        {err && <Alert type="error" showIcon message={err} style={{ marginBottom: 16 }} />}
        <Space wrap>
          <Select
            style={{ minWidth: 240 }}
            placeholder="選擇計畫"
            value={planId ?? undefined}
            onChange={(v) => setPlanId(v)}
            options={plans.map((p) => ({ value: p.id, label: p.name }))}
            notFoundContent="尚無計畫"
          />
          <Input
            placeholder="新計畫名稱"
            value={newPlanName}
            onChange={(e) => setNewPlanName(e.target.value)}
            style={{ width: 200 }}
          />
          <Button type="primary" icon={<PlusOutlined />} onClick={createPlan}>
            新增計畫
          </Button>
        </Space>
      </Card>

      {planId != null && tree && (
        <Card
          title={
            <Space>
              {tree.name}
              <Tag color="geekblue">v{tree.version}</Tag>
            </Space>
          }
          extra={
            <Space>
              <Typography.Text type="secondary">狀態</Typography.Text>
              <Tag color={PLAN_COLOR[tree.status]}>{tree.status}</Tag>
              <Select
                size="small"
                value={tree.status}
                onChange={setPlanStatus}
                options={PLAN_STATUSES.map((s) => ({ value: s, label: s }))}
                style={{ width: 140 }}
              />
              <Button size="small" onClick={bumpVersion}>
                提升版本
              </Button>
            </Space>
          }
        >
          <Button
            type="dashed"
            icon={<PlusOutlined />}
            onClick={() => setFnModal(true)}
            style={{ marginBottom: 16 }}
          >
            新增 Test Function
          </Button>

          {tree.functions.length === 0 ? (
            <Typography.Text type="secondary">尚無 Test Function，請先新增。</Typography.Text>
          ) : (
            <Space direction="vertical" size={12} style={{ width: '100%' }}>
              {tree.functions.map((fn) => (
                <Card
                  key={fn.id}
                  type="inner"
                  size="small"
                  title={
                    <Space>
                      {fn.name}
                      {fn.description && (
                        <Typography.Text type="secondary">{fn.description}</Typography.Text>
                      )}
                    </Space>
                  }
                  extra={
                    <Button size="small" onClick={() => setCaseModalFor(fn.id)}>
                      新增案例
                    </Button>
                  }
                >
                  <Table
                    rowKey="id"
                    size="small"
                    dataSource={fn.cases}
                    columns={caseColumns}
                    pagination={false}
                    locale={{ emptyText: '尚無 Test Case' }}
                  />
                </Card>
              ))}
            </Space>
          )}
        </Card>
      )}

      <Modal
        title="新增 Test Function"
        open={fnModal}
        onOk={addFunction}
        onCancel={() => {
          setFnModal(false);
          setFnName('');
        }}
      >
        <Input
          placeholder="功能名稱"
          value={fnName}
          onChange={(e) => setFnName(e.target.value)}
          onPressEnter={addFunction}
        />
      </Modal>

      <Modal
        title={`新增 Test Case（功能 #${caseModalFor ?? ''}）`}
        open={caseModalFor != null}
        onOk={addCase}
        onCancel={() => {
          setCaseModalFor(null);
          caseForm.resetFields();
        }}
      >
        <Form form={caseForm} layout="vertical" initialValues={{ priority: 'medium' }}>
          <Form.Item name="name" label="案例名稱" rules={[{ required: true, message: '請輸入' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="precondition" label="前置條件">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="steps" label="步驟">
            <Input.TextArea rows={3} placeholder={"1. ...\n2. ..."} />
          </Form.Item>
          <Form.Item name="expected_result" label="預期結果">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="priority" label="優先度">
            <Select
              options={[
                { value: 'low', label: 'low' },
                { value: 'medium', label: 'medium' },
                { value: 'high', label: 'high' },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}
