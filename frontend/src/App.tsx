// App.tsx

import React, { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet, useNavigate, useLocation } from 'react-router-dom';
import { ConfigProvider, message } from 'antd';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAuthStore } from './stores/authStore';
import { useUIStore } from './stores/uiStore';
import { ErrorBoundary } from './components/common/ErrorBoundary';
import { LoginPage } from './pages/auth/LoginPage';
import { RegisterPage } from './pages/auth/RegisterPage';
import { DashboardPage } from './pages/dashboard/DashboardPage';
import { NotesListPage } from './pages/notes/NotesListPage';
import { NoteEditorPage } from './pages/notes/NoteEditorPage';
import { TagIndexPage } from './pages/notes/TagIndexPage';
import { PersonalizedDocPage } from './pages/learning/PersonalizedDocPage';
import { LearningRoutePage } from './pages/learning/LearningRoutePage';
import { ReviewListPage } from './pages/review/ReviewListPage';
import { ReviewSessionPage } from './pages/review/ReviewSessionPage';
import { QAPage } from './pages/learning/QAPage';
import { LearningRoutesPage } from './pages/learning/LearningRoutesPage';
import './App.css';

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 2, staleTime: 5 * 60 * 1000 } },
});

/* ===== Auth Guards ===== */
const ProtectedRoute: React.FC = () => {
  const { isAuthenticated } = useAuthStore();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <Outlet />;
};

const AuthRedirect: React.FC = () => {
  const { isAuthenticated } = useAuthStore();
  if (isAuthenticated) return <Navigate to="/" replace />;
  return <Outlet />;
};

/* ===== Sidebar Icons (inline SVG) ===== */
const iconStyle: React.CSSProperties = { width: 18, height: 18, flexShrink: 0 };
const HomeIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} style={iconStyle}><path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
);
const NotesIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} style={iconStyle}><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1={16} y1={13} x2={8} y2={13}/><line x1={16} y1={17} x2={8} y2={17}/></svg>
);
const LearnIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} style={iconStyle}><circle cx={12} cy={12} r={10}/><polyline points="12 6 12 12 16 14"/></svg>
);
const ReviewIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} style={iconStyle}><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/></svg>
);
const ChevronLeftIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} style={{width:16,height:16,flexShrink:0}}><polyline points="15 18 9 12 15 6"/></svg>
);
const SearchIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} style={{width:14,height:14}}><circle cx={11} cy={11} r={8}/><line x1={21} y1={21} x2={16.65} y2={16.65}/></svg>
);
const SunIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} style={{width:18,height:18}}><path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/></svg>
);
const MoonIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} style={{width:18,height:18}}><circle cx={12} cy={12} r={5}/><line x1={12} y1={1} x2={12} y2={3}/><line x1={12} y1={21} x2={12} y2={23}/><line x1={4.22} y1={4.22} x2={5.64} y2={5.64}/><line x1={18.36} y1={18.36} x2={19.78} y2={19.78}/><line x1={1} y1={12} x2={3} y2={12}/><line x1={21} y1={12} x2={23} y2={12}/><line x1={4.22} y1={19.78} x2={5.64} y2={18.36}/><line x1={18.36} y1={5.64} x2={19.78} y2={4.22}/></svg>
);

/* ===== MainLayout ===== */
const MainLayout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuthStore();
  const { sidebarCollapsed, toggleSidebar, theme, setTheme } = useUIStore();
  const [searchText, setSearchText] = useState('');

  const currentPath = '/' + location.pathname.split('/')[1];
  const isEditor = location.pathname.startsWith('/notes/') && location.pathname !== '/notes' && location.pathname !== '/notes/new';

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="app">
      {/* Sidebar */}
      <aside className={`app-sidebar${sidebarCollapsed ? ' collapsed' : ''}`}>
        <div className="sidebar-header">
          <div className="sidebar-logo">云</div>
          <span className="sidebar-title">青云智学</span>
        </div>
        <nav className="sidebar-nav">
          <div className={`nav-item${currentPath === '/' ? ' active' : ''}`} onClick={() => navigate('/')}>
            <HomeIcon /><span>首页</span>
          </div>
          <div className="nav-group-title">知识管理</div>
          <div className={`nav-item${currentPath === '/notes' ? ' active' : ''}`} onClick={() => navigate('/notes')}>
            <NotesIcon /><span>笔记</span>
          </div>
          <div className="nav-group-title">学习中心</div>
          <div className={`nav-item${currentPath === '/learning' ? ' active' : ''}`} onClick={() => navigate('/learning')}>
            <LearnIcon /><span>学习</span>
          </div>
          <div className="nav-group-title">复习</div>
          <div className={`nav-item${currentPath === '/review' ? ' active' : ''}`} onClick={() => navigate('/review')}>
            <ReviewIcon /><span>待复习</span>
          </div>
        </nav>
        <div className="sidebar-footer">
          <button className="collapse-btn" onClick={toggleSidebar}><ChevronLeftIcon /></button>
        </div>
      </aside>

      {/* Main */}
      <div className="app-main">
        {/* TopBar */}
        <header className="app-topbar">
          <div className="topbar-search">
            <span className="search-icon"><SearchIcon /></span>
            <input
              type="text"
              placeholder="搜索笔记、讲义、知识点..."
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && searchText.trim()) {
                  message.info('全局搜索功能将在后续版本实现');
                }
              }}
            />
            <span style={{position:'absolute',right:10,top:'50%',transform:'translateY(-50%)',fontSize:11,color:'var(--color-text-tertiary)',background:'var(--color-bg-page)',border:'1px solid var(--color-border)',borderRadius:4,padding:'1px 6px'}}>⌘K</span>
          </div>
          <div className="topbar-actions">
            <button className="theme-toggle" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} title="切换主题">
              {theme === 'dark' ? <MoonIcon /> : <SunIcon />}
            </button>
            <div className="user-avatar" onClick={handleLogout} title="点击退出登录">
              {user?.username?.charAt(0) || '?'}
            </div>
          </div>
        </header>

        {/* Content */}
        <div className={`app-content${isEditor ? '' : ''}`}>
          <ErrorBoundary key={location.pathname}>
            <Outlet />
          </ErrorBoundary>
        </div>
      </div>
    </div>
  );
};

/* ===== App ===== */
const App: React.FC = () => {
  const { loadFromStorage } = useAuthStore();
  const { theme } = useUIStore();

  useEffect(() => {
    loadFromStorage();
  }, [loadFromStorage]);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme === 'dark' ? 'dark' : '');
  }, [theme]);

  return (
    <QueryClientProvider client={queryClient}>
      <ConfigProvider
        theme={{
          token: {
            colorPrimary: '#F59E0B',
            borderRadius: 6,
            fontFamily: 'var(--font-family)',
          },
        }}
      >
        <BrowserRouter>
          <Routes>
            <Route element={<AuthRedirect />}>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
            </Route>
            <Route element={<ProtectedRoute />}>
              <Route element={<MainLayout />}>
                <Route path="/" element={<DashboardPage />} />
                <Route path="/notes" element={<NotesListPage />} />
                <Route path="/notes/new" element={<NoteEditorPage />} />
                <Route path="/notes/:id" element={<NoteEditorPage />} />
                <Route path="/notes/tags/:id" element={<TagIndexPage />} />
                <Route path="/learning" element={<LearningRoutesPage />} />
                <Route path="/learning/route/:id" element={<LearningRoutePage />} />
                <Route path="/learning/lecture/:id" element={<Navigate to="/" replace />} />
                <Route path="/learning/summary/:id" element={<PersonalizedDocPage />} />
                <Route path="/review" element={<ReviewListPage />} />
                <Route path="/review/:id" element={<ReviewSessionPage />} />
                <Route path="/learning/qa/:id" element={<QAPage />} />
              </Route>
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </ConfigProvider>
    </QueryClientProvider>
  );
};

export default App;
