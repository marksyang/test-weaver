import { Alert, Card, Tag, Typography } from 'antd';
import { ToolOutlined } from '@ant-design/icons';

interface Props {
  title: string;
  desc: string;
}

/** 尚未建置模組的佔位頁。 */
export default function PlaceholderPage({ title, desc }: Props) {
  return (
    <Card>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          {title}
        </Typography.Title>
        <Tag icon={<ToolOutlined />} color="orange">
          待開發
        </Tag>
      </div>
      <Typography.Paragraph type="secondary" style={{ marginBottom: 16 }}>
        {desc}
      </Typography.Paragraph>
      <Alert
        type="info"
        showIcon
        message="此模組規劃中"
        description="已列入 程式計劃書 Roadmap，尚未建置。目前可先用「RAG 檢索」。"
      />
    </Card>
  );
}
