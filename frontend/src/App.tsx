import { Layout, Menu, Spin, Typography, Button, type MenuProps } from 'antd';
import {
  AppstoreOutlined,
  BarChartOutlined,
  BugOutlined,
  CheckSquareOutlined,
  LogoutOutlined,
  ProfileOutlined,
  SearchOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from './auth/AuthContext';
import { allowedPathsForRole } from './auth/roles';
import RagPage from './pages/RagPage';
import PlanPage from './pages/PlanPage';
import SelfTestPage from './pages/SelfTestPage';
import DefectPage from './pages/DefectPage';
import PlatformPage from './pages/PlatformPage';
import ReportPage from './pages/ReportPage';
import LoginPage from './pages/LoginPage';
import SettingsPage from './pages/SettingsPage';

const { Sider, Header, Content } = Layout;

interface MenuItem {
  key: string;
  icon: React.ReactNode;
  label: string;
}

// 全量選單（key 即 path）＋ 依角色顯示
const ALL_ITEMS: NonNullable<MenuProps['items']> = [
  { key: '/rag', icon: <SearchOutlined />, label: 'RAG 檢索' },
  { key: '/plan', icon: <ProfileOutlined />, label: '測試計畫' },
  { key: '/self-test', icon: <CheckSquareOutlined />, label: '自測' },
  { key: '/defect', icon: <BugOutlined />, label: '缺陷追蹤' },
  { key: '/report', icon: <BarChartOutlined />, label: '報表 / AI' },
  { key: '/platform', icon: <AppstoreOutlined />, label: '共通類別平台' },
  { key: '/settings', icon: <SettingOutlined />, label: '設定' },
];

const TITLES: Record<string, string> = {
  '/rag': 'RAG 智能檢索',
  '/plan': '測試計畫',
  '/self-test': '自測',
  '/defect': '缺陷追蹤',
  '/report': '報表 / AI',
  '/platform': '共通類別平台',
  '/settings': '設定',
};

function menuForRole(role: string): NonNullable<MenuProps['items']> {
  const allowed = allowedPathsForRole(role);
  return ALL_ITEMS.filter((i) => !!i && 'key' in i && allowed.includes(i.key as string));
}

function Shell({ role }: { role: string }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider theme="light" width={220} breakpoint="lg" collapsedWidth={0}>
        <div style={{ padding: '16px 20px' }}>
          <Typography.Title level={4} style={{ margin: 0 }}>TestWeaver</Typography.Title>
          <Typography.Text type="secondary">測試管理平台</Typography.Text>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuForRole(role)}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header style={{ background: '#fff', padding: '0 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Typography.Title level={5} style={{ margin: '16px 0' }}>
            {TITLES[location.pathname] ?? 'TestWeaver'}
          </Typography.Title>
          <Space2>
            <Typography.Text type="secondary">
              {user?.username} · {role}
            </Typography.Text>
            <Button size="small" icon={<LogoutOutlined />} onClick={logout}>
              登出
            </Button>
          </Space2>
        </Header>
        <Content style={{ margin: 24 }}>
          <Routes>
            <Route path="/rag" element={<RagPage />} />
            <Route path="/plan" element={<PlanPage />} />
            <Route path="/self-test" element={<SelfTestPage />} />
            <Route path="/defect" element={<DefectPage />} />
            <Route path="/report" element={<ReportPage />} />
            <Route path="/platform" element={<PlatformPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/" element={<Navigate to="/rag" replace />} />
            <Route path="*" element={<Navigate to="/rag" replace />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  );
}

// 簡易 header 右側空間（避免再引一個 Space）
function Space2({ children }: { children: React.ReactNode }) {
  return <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>{children}</div>;
}

export default function App() {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (location.pathname === '/login') return <LoginPage />;
  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }}>
        <Spin size="large" />
      </div>
    );
  }
  // 啟用認證且未登入 → 導回登入（免登入模式 user 恆為匿名 admin，不會到此）
  if (!user) return <Navigate to="/login" replace />;

  return <Shell role={user.role} />;
}
