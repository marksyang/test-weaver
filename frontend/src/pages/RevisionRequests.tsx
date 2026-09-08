import { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Input,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  message,
} from 'antd';
import { m5Api } from '../api/m5';
import type { RevisionRequest } from '../types/m5';

const errMsg = (e: unknown) => (e instanceof Error ? e.message : String(e));
const REVISION_COLOR: Record<string, string> = {
  open: 'orange',
  accepted: 'processing',
  rejected: 'red',
  done: 'green',
};

export default function RevisionRequests() {
  const [revisions, setRevisions] = useState<RevisionRequest[]>([]);
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);
  const [err, setErr] = useState<string | null>(null);
  const [rejecting, setRejecting] = useState<RevisionRequest | null>(null);
  const [rejectReason, setRejectReason] = useState('');

  const load = useCallback(() => {
    m5Api
      .listRevisions(statusFilter ? { status: statusFilter } : {})
      .then(setRevisions)
      .catch((e) => setErr(errMsg(e)));
  }, [statusFilter]);
  useEffect(() => {
    load();
  }, [load]);

  const accept = async (id: number) => {
    try {
      await m5Api.accept(id);
      message.success(`已接受修改要求 #${id}：補建案例 + 計畫版本 +1`);
      load();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const complete = async (id: number) => {
    try {
      await m5Api.complete(id);
      message.success(`已標記完成 #${id}`);
      load();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const doReject = async () => {
    if (!rejectReason.trim()) {
      message.warning('請輸入拒絕理由');
      return;
    }
    try {
      await m5Api.reject(rejecting!.id, rejectReason.trim());
      message.success(`已拒絕 #${rejecting!.id}`);
      setRejecting(null);
      setRejectReason('');
      load();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    {
      title: '缺陷',
      dataIndex: 'defect_id',
      key: 'defect',
      width: 80,
      render: (v: number | null) => (v ? `#${v}` : '-'),
    },
    {
      title: '計畫',
      dataIndex: 'test_plan_id',
      key: 'plan',
      width: 80,
      render: (v: number) => `#${v}`,
    },
    { title: '原因', dataIndex: 'reason', key: 'reason', ellipsis: true },
    {
      title: '狀態',
      dataIndex: 'status',
      key: 'status',
      width: 110,
      render: (v: string) => <Tag color={REVISION_COLOR[v] ?? 'default'}>{v}</Tag>,
    },
    {
      title: '操作',
      key: 'op',
      width: 170,
      render: (_: unknown, r: RevisionRequest) => (
        <Space size={4}>
          {r.status === 'open' && (
            <Button size="small" type="primary" onClick={() => accept(r.id)}>
              接受
            </Button>
          )}
          {r.status === 'open' && (
            <Button size="small" danger onClick={() => setRejecting(r)}>
              拒絕
            </Button>
          )}
          {r.status === 'accepted' && (
            <Button size="small" onClick={() => complete(r.id)}>
              完成
            </Button>
          )}
        </Space>
      ),
    },
  ];

  return (
    <Card
      title="修改要求（Test Plan Revision Request）"
      extra={
        <Select
          allowClear
          placeholder="狀態"
          value={statusFilter}
          onChange={(v) => setStatusFilter(v)}
          style={{ width: 130 }}
          options={[
            { value: 'open', label: 'open' },
            { value: 'accepted', label: 'accepted' },
            { value: 'rejected', label: 'rejected' },
            { value: 'done', label: 'done' },
          ]}
        />
      }
    >
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 12 }}
        message="Defect 無對應案例時自動建立"
        description="接受 → 補建案例並使計畫版本 +1（接 M2）；狀態機 open → accepted → done 或 open → rejected。"
      />
      {err && <Alert type="error" showIcon message={err} style={{ marginBottom: 12 }} />}
      <Table
        rowKey="id"
        size="small"
        dataSource={revisions}
        columns={columns}
        pagination={{ pageSize: 8 }}
        locale={{ emptyText: '尚無修改要求（於「缺陷」頁手動建立無案例的 Defect 即會自動產生）' }}
        expandable={{
          expandedRowRender: (r) => (
            <Space direction="vertical" style={{ width: '100%' }}>
              <div>
                <b>原因：</b>
                {r.reason ?? '-'}
              </div>
              {r.proposed_change && (
                <div>
                  <b>建議變更：</b>
                  {r.proposed_change}
                </div>
              )}
              {r.requested_by && (
                <div>
                  <b>要求者：</b>
                  {r.requested_by}
                </div>
              )}
            </Space>
          ),
        }}
      />

      <Modal
        title={`拒絕修改要求 #${rejecting?.id ?? ''}`}
        open={rejecting != null}
        onOk={doReject}
        onCancel={() => {
          setRejecting(null);
          setRejectReason('');
        }}
        okText="拒絕"
        cancelText="取消"
      >
        <Input.TextArea
          rows={3}
          placeholder="請輸入拒絕理由（必填）"
          value={rejectReason}
          onChange={(e) => setRejectReason(e.target.value)}
        />
      </Modal>
    </Card>
  );
}
