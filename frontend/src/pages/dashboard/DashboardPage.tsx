// pages/dashboard/DashboardPage.tsx

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { notesAPI } from '../../api/notes';
import { reviewAPI } from '../../api/review';
import { useAuthStore } from '../../stores/authStore';
import { Modal, Input, message, Empty, Button } from 'antd';
import { learningAPI } from '../../api/learning';

/* ===== Inline SVG Icons ===== */
const LightningIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
);
const ClockIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
);
const ChartIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
);
const NoteIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
);
const PlayIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
);
const qaStyle: React.CSSProperties = { width: 20, height: 20, flexShrink: 0 };
const BookIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={qaStyle}><path d="M2 3h6a4 4 0 014 4v14a3 3 0 00-3-3H2z"/><path d="M22 3h-6a4 4 0 00-4 4v14a3 3 0 013-3h7z"/></svg>
);
const RefreshIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={qaStyle}><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/></svg>
);
const PlusIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={qaStyle}><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
);
const ChevronRightIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{width:14,height:14}}><polyline points="9 18 15 12 9 6"/></svg>
);

export const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuthStore();

  const [routeModalVisible, setRouteModalVisible] = useState(false);
  const [routeTopic, setRouteTopic] = useState('');
  const [isGeneratingRoute, setIsGeneratingRoute] = useState(false);

  const handleCreateRoute = async () => {
    if (!routeTopic.trim()) {
      message.warning('请输入学习主题');
      return;
    }
    setIsGeneratingRoute(true);
    try {
      const response = await learningAPI.generateRoute({ topic: routeTopic.trim() });
      // 兼容两种后端响应格式
      const body: any = response.data;
      const newRoute =
        body?.data && typeof body.data === 'object' && 'id' in body.data
          ? body.data
          : body;
      setRouteModalVisible(false);
      setRouteTopic('');
      message.success('学习路线创建成功！');
      navigate(`/learning/route/${newRoute.id}`);
    } catch (err) {
      console.error('[DashboardPage] 创建学习路线失败:', err);
      message.error('创建学习路线失败，请重试');
    } finally {
      setIsGeneratingRoute(false);
    }
  };

  const { data: recentNotes } = useQuery({
    queryKey: ['notes', 'recent'],
    queryFn: () => notesAPI.list({ sort_by: 'updated_at', page_size: 5 }).then((res) => {
      // 兼容三种后端响应格式：裸数组、PaginatedResponse 或 ApiResponse 包装
      const body: any = res.data;
      if (Array.isArray(body)) return { items: body, total: body.length };
      if (body?.items) return body;
      if (body?.data?.items) return body.data;
      return { items: [], total: 0 };
    }),
  });

  const { data: reviewStats } = useQuery({
    queryKey: ['review', 'stats'],
    queryFn: () => reviewAPI.getStats().then((res) => {
      // 兼容两种后端响应格式
      const body: any = res.data;
      return body?.data ?? body;
    }),
  });

  const { data: recentRoutes } = useQuery({
    queryKey: ['learning', 'routes', 'recent'],
    queryFn: () => learningAPI.listRoutes({ page_size: 5 }).then((res) => {
      const body: any = res.data;
      if (Array.isArray(body)) return { items: body, total: body.length };
      if (body?.items) return body;
      if (body?.data?.items) return body.data;
      return { items: [], total: 0 };
    }),
  });

  // 统计卡片数据
  const statCards = [
    {
      icon: <LightningIcon />,
      iconClass: '',
      value: reviewStats?.total_reviewed ?? 0,
      label: '已复习知识点',
      suffix: '个',
    },
    {
      icon: <ClockIcon />,
      iconClass: 'green',
      value: reviewStats?.total_time_minutes ? Math.round(reviewStats.total_time_minutes / 60) : 0,
      label: '学习总时长',
      suffix: '小时',
    },
    {
      icon: <ChartIcon />,
      iconClass: 'blue',
      value: reviewStats?.average_mastery ? Math.round(reviewStats.average_mastery * 100) : 0,
      label: '平均掌握度',
      suffix: '%',
    },
  ];

  // 最近路线中的活跃路线
  const activeRoutes = (recentRoutes?.items ?? []).slice(0, 3);

  const today = new Date();
  const weekdays = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六'];
  const dateStr = `${today.getFullYear()}年${today.getMonth() + 1}月${today.getDate()}日 ${weekdays[today.getDay()]}`;

  return (
    <div>
      {/* Welcome Row */}
      <div className="welcome-row">
        <div className="welcome-text">欢迎回来，<span>{user?.username || '开发者'}</span></div>
        <div className="welcome-date">{dateStr}</div>
      </div>

      {/* Stats */}
      <div className="stats-grid">
        {statCards.map((card, i) => (
          <div className="stat-card" key={i}>
            <div className={`stat-icon ${card.iconClass}`}>{card.icon}</div>
            <div>
              <div className="stat-value">
                {card.value > 0 ? card.value : '—'}
                {card.value > 0 && <span className="stat-suffix">{card.suffix}</span>}
              </div>
              <div className="stat-label">{card.label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Charts & Review */}
      <div className="dashboard-grid">
        <div className="dash-card">
          <div className="card-header"><div className="card-title">知识掌握度分布</div></div>
          <Empty description="暂无掌握度数据，完成复习后将自动统计" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        </div>

        <div className="dash-card">
          <div className="card-header">
            <div className="card-title">今日待复习</div>
            <button className="card-action" onClick={() => navigate('/review')}>查看全部 <ChevronRightIcon /></button>
          </div>
          <Empty description="暂无待复习内容" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        </div>
      </div>

      {/* Notes & Learning Route */}
      <div className="dashboard-grid">
        <div className="dash-card">
          <div className="card-header">
            <div className="card-title">最近笔记</div>
            <button className="card-action" onClick={() => navigate('/notes')}>查看全部 <ChevronRightIcon /></button>
          </div>
          {(recentNotes?.items ?? []).length > 0 ? (
            (recentNotes?.items ?? []).slice(0, 3).map((note: any) => (
              <div className="note-list-item" key={note.id} onClick={() => navigate(`/notes/${note.id}`)}>
                <div className="note-list-icon"><NoteIcon /></div>
                <div className="note-list-info">
                  <div className="note-list-title">{note.title}</div>
                  <div className="note-list-meta">{note.word_count}字</div>
                  <div className="note-list-tags">
                    {Array.isArray(note.tags) && note.tags.slice(0, 3).map((nt: any) => (
                      <span key={nt.tag_id} className="tag tag-primary">{nt.tag?.name}</span>
                    ))}
                  </div>
                </div>
              </div>
            ))
          ) : (
            <Empty description="暂无笔记，点击右上角新建" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          )}
        </div>

        <div className="dash-card">
          <div className="card-header">
            <div className="card-title">当前学习</div>
            <button className="card-action" onClick={() => navigate('/learning')}>查看全部 <ChevronRightIcon /></button>
          </div>
          {activeRoutes.length > 0 ? (
            activeRoutes.map((route: any) => {
              const completed = route.steps?.filter((s: any) => s.status === 'completed').length ?? 0;
              const total = route.total_steps || route.steps?.length || 0;
              const pct = total > 0 ? Math.round((completed / total) * 100) : 0;
              const statusLabel: Record<string, string> = { active: '进行中', generating: '生成中', paused: '已暂停', completed: '已完成' };
              return (
                <div className="route-mini-card" key={route.id} onClick={() => navigate(`/learning/route/${route.id}`)}>
                  <div className="route-mini-top">
                    <span className="route-mini-name">{route.topic}</span>
                    <span className={`route-mini-status status-${route.status}`}>{statusLabel[route.status] || route.status}</span>
                  </div>
                  <div className="route-mini-bar">
                    <div className="route-mini-fill" style={{ width: `${pct}%` }} />
                  </div>
                  <div className="route-mini-meta">{completed}/{total} 步骤</div>
                </div>
              );
            })
          ) : (
            <Empty description="暂无进行中的学习路线，创建一条开始学习吧" image={Empty.PRESENTED_IMAGE_SIMPLE}>
              <Button type="primary" icon={<PlayIcon />} onClick={() => setRouteModalVisible(true)}>
                开始学习
              </Button>
            </Empty>
          )}
        </div>
      </div>

      {/* Quick Actions */}
      <div className="dash-card" style={{marginTop:0}}>
        <div className="card-header"><div className="card-title">快速入口</div></div>
        <div className="quick-actions">
          <button className="quick-btn primary" onClick={() => navigate('/notes/new')}>
            <PlusIcon /> 新建笔记
          </button>
          <button className="quick-btn secondary" onClick={() => setRouteModalVisible(true)}>
            <BookIcon /> 创建学习路线
          </button>
          <button className="quick-btn secondary" onClick={() => navigate('/review')}>
            <RefreshIcon /> 开始复习
          </button>
        </div>
      </div>

      {/* 创建学习路线弹窗 */}
      <Modal
        title="创建学习路线"
        open={routeModalVisible}
        onCancel={() => { setRouteModalVisible(false); setRouteTopic(''); }}
        onOk={handleCreateRoute}
        confirmLoading={isGeneratingRoute}
        okText="开始生成"
        cancelText="取消"
        destroyOnClose
      >
        <div style={{ marginBottom: 8, color: 'var(--color-text-secondary)', fontSize: 13 }}>
          输入你想学习的主题，AI 将为你生成个性化的学习路线。
        </div>
        <Input
          placeholder="例如：机器学习基础、微积分入门、Python 数据分析..."
          value={routeTopic}
          onChange={(e) => setRouteTopic(e.target.value)}
          onPressEnter={handleCreateRoute}
          size="large"
          autoFocus
        />
      </Modal>
    </div>
  );
};
