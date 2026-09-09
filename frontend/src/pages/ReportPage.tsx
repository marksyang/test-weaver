import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  App,
  Button,
  Card,
  Col,
  Input,
  List,
  Modal,
  Row,
  Select,
  Space,
  Spin,
  Statistic,
  Tag,
  Typography,
} from 'antd';
import * as echarts from 'echarts';
import EChart from '../components/EChart';
import { m1Api } from '../api/m1';
import { m2Api } from '../api/m2';
import { m5Api } from '../api/m5';
import { m6Api } from '../api/m6';
import type { Project } from '../types/m1';
import type { TestPlan } from '../types/m2';
import type { Recommendation, Report } from '../types/m6';

const { Text } = Typography;
const errMsg = (e: unknown) => (e instanceof Error ? e.message : String(e));

// FR-4 / M6：測試完成 → 報表（ECharts）+ AI 分析建議 → 一鍵轉 Revision Request
export default function ReportPage() {
  const { message } = App.useApp();
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<number | undefined>(undefined);
  const [plans, setPlans] = useState<TestPlan[]>([]);
  const [planId, setPlanId] = useState<number | undefined>(undefined);
  const [report, setReport] = useState<Report | null>(null);
  const [completing, setCompleting] = useState(false);
  const [convertingId, setConvertingId] = useState<string | null>(null);
  const [loadingReport, setLoadingReport] = useState(false);
  const [emailOpen, setEmailOpen] = useState(false);
  const [emailTo, setEmailTo] = useState('');
  const [sending, setSending] = useState(false);

  useEffect(() => {
    m1Api.listProjects().then(setProjects).catch(() => setProjects([]));
  }, []);
  useEffect(() => {
    if (projects.length) setProjectId((prev) => prev ?? projects[0].id);
  }, [projects]);

  useEffect(() => {
    if (projectId == null) return;
    m2Api.listPlans(projectId).then(setPlans).catch(() => setPlans([]));
  }, [projectId]);

  const loadReport = useCallback(async (pid: number) => {
    setLoadingReport(true);
    try {
      setReport(await m6Api.getReport(pid));
    } catch {
      setReport(null); // 404：尚未生成
    } finally {
      setLoadingReport(false);
    }
  }, []);

  useEffect(() => {
    if (planId != null) loadReport(planId);
    else setReport(null);
  }, [planId, loadReport]);

  const m = report?.metrics ?? null;

  const statusOption: echarts.EChartsOption = useMemo(
    () => ({
      title: { text: '案例結果分佈', left: 'center' },
      tooltip: { trigger: 'item' },
      legend: { bottom: 0 },
      series: [
        {
          type: 'pie',
          radius: ['40%', '65%'],
          center: ['50%', '52%'],
          data: [
            { name: '通過', value: m?.passed ?? 0, itemStyle: { color: '#52c41a' } },
            { name: '失敗', value: m?.failed ?? 0, itemStyle: { color: '#ff4d4f' } },
            { name: '阻塞', value: m?.blocked ?? 0, itemStyle: { color: '#faad14' } },
            { name: '未執行', value: m?.pending ?? 0, itemStyle: { color: '#d9d9d9' } },
          ],
        },
      ],
    }),
    [m],
  );

  const sevOption: echarts.EChartsOption = useMemo(() => {
    const sev = m?.defects.by_severity ?? {};
    return {
      title: { text: '缺陷嚴重度分佈', left: 'center' },
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: ['critical', 'high', 'medium', 'low'] },
      yAxis: { type: 'value', minInterval: 1 },
      series: [
        {
          type: 'bar',
          barWidth: '45%',
          data: [sev.critical ?? 0, sev.high ?? 0, sev.medium ?? 0, sev.low ?? 0],
          itemStyle: { color: '#ff7a45' },
        },
      ],
    };
  }, [m]);

  const handleComplete = async () => {
    if (planId == null) return;
    setCompleting(true);
    try {
      await m6Api.completePlan(planId);
      message.success('計畫已標記完成，報表與 AI 分析已生成');
      await loadReport(planId);
    } catch (e) {
      message.error(errMsg(e));
    } finally {
      setCompleting(false);
    }
  };

  const handleConvert = async (rec: Recommendation) => {
    if (planId == null) return;
    setConvertingId(rec.title);
    try {
      const rr = await m5Api.createRevision({
        test_plan_id: planId,
        reason: rec.title,
        proposed_change: rec.detail,
      });
      message.success(`已建立修改要求 #${rr.id}，可至「缺陷追蹤」檢視`);
    } catch (e) {
      message.error(errMsg(e));
    } finally {
      setConvertingId(null);
    }
  };

  const handleSendEmail = async () => {
    if (planId == null) return;
    const to = emailTo.trim();
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(to)) {
      message.error('請輸入有效 email');
      return;
    }
    setSending(true);
    try {
      await m6Api.sendReport(planId, to);
      message.success(`報表已寄給 ${to}`);
      setEmailOpen(false);
      setEmailTo('');
    } catch (e) {
      message.error(errMsg(e));
    } finally {
      setSending(false);
    }
  };

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Row gutter={16} align="middle">
        <Col>
          <Space>
            <Text>專案</Text>
            <Select
              style={{ width: 260 }}
              allowClear
              placeholder="選專案"
              value={projectId}
              onChange={(v) => {
                setProjectId(v);
                setPlanId(undefined);
              }}
              options={projects.map((p) => ({ label: p.name, value: p.id }))}
            />
          </Space>
        </Col>
        <Col>
          <Space>
            <Text>測試計畫</Text>
            <Select
              style={{ width: 300 }}
              allowClear
              placeholder="選測試計畫"
              value={planId}
              onChange={(v) => setPlanId(v)}
              options={plans.map((p) => ({
                label: `#${p.id} ${p.name} v${p.version} · ${p.status}`,
                value: p.id,
              }))}
            />
          </Space>
        </Col>
        <Col>
          {planId != null && !report && (
            <Button type="primary" loading={completing} onClick={handleComplete}>
              完成計畫並生成報表
            </Button>
          )}
          {planId != null && report && (
            <Space>
              <Button href={m6Api.exportUrl(planId, 'csv')} target="_blank">
                匯出 CSV
              </Button>
              <Button href={m6Api.exportUrl(planId, 'pdf')} target="_blank">
                下載 PDF
              </Button>
              <Button onClick={() => setEmailOpen(true)}>Email 報表</Button>
            </Space>
          )}
        </Col>
      </Row>

      {planId != null && !report && (
        <Card>
          <Alert
            type="info"
            showIcon
            message="尚無報表"
            description="此計畫尚未生成報表。請將其標記為「完成」以自動生成指標與 AI 分析建議（通過率、缺陷分佈、覆蓋缺口等）。"
          />
        </Card>
      )}

      {loadingReport && <Spin />}

      {report && m && (
        <>
          <Row gutter={16}>
            <Col span={6}>
              <Card>
                <Statistic title="通過率" value={(m.pass_rate * 100).toFixed(1)} suffix="%" valueStyle={{ color: '#52c41a' }} />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic title="案例數" value={m.total_cases} suffix={`（通過 ${m.passed}）`} />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="缺陷數"
                  value={m.defects.total}
                  suffix={`（未結 ${m.defects.open_or_in_progress}）`}
                  valueStyle={m.defects.open_or_in_progress > 0 ? { color: '#ff4d4f' } : undefined}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic title="覆蓋率" value={(m.coverage * 100).toFixed(1)} suffix="%" />
              </Card>
            </Col>
          </Row>

          <Alert
            type="info"
            showIcon
            message={report.summary ?? '（無摘要）'}
            description={
              <span>
                模型：{report.model_name ?? '-'}；覆蓋缺口：
                {m.coverage_gaps.length ? m.coverage_gaps.join('、') : '無'}；失敗案例：
                {m.failed_cases.length ? m.failed_cases.join('、') : '無'}
              </span>
            }
          />

          <Row gutter={16}>
            <Col span={12}>
              <Card>
                <EChart option={statusOption} />
              </Card>
            </Col>
            <Col span={12}>
              <Card>
                <EChart option={sevOption} />
              </Card>
            </Col>
          </Row>

          <Card title="AI 分析建議（可一鍵轉 Revision Request）">
            {report.recommendations.length === 0 ? (
              <Text type="secondary">無建議</Text>
            ) : (
              <List
                dataSource={report.recommendations}
                renderItem={(rec) => (
                  <List.Item
                    actions={[
                      <Button
                        key="conv"
                        size="small"
                        loading={convertingId === rec.title}
                        onClick={() => handleConvert(rec)}
                      >
                        轉 Revision Request
                      </Button>,
                    ]}
                  >
                    <List.Item.Meta
                      title={<Tag color="geekblue">{rec.title}</Tag>}
                      description={rec.detail}
                    />
                  </List.Item>
                )}
              />
            )}
          </Card>
        </>
      )}

      <Modal
        title="Email 報表"
        open={emailOpen}
        onOk={handleSendEmail}
        okText="發送"
        cancelText="取消"
        confirmLoading={sending}
      >
        <Text>將報表（含 PDF 附件）寄給：</Text>
        <Input
          value={emailTo}
          onChange={(e) => setEmailTo(e.target.value)}
          placeholder="收件人 email"
          style={{ marginTop: 8 }}
        />
      </Modal>
    </Space>
  );
}
