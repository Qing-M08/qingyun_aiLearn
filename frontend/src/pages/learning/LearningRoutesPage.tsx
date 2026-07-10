// pages/learning/LearningRoutesPage.tsx

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Spin, message, Button, Modal, Input, Tag, Breadcrumb, Empty, Card, Checkbox, Popconfirm } from 'antd';
import {
  HomeOutlined,
  PlusOutlined,
  PlayCircleOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  PauseCircleOutlined,
  LoadingOutlined,
  DeleteOutlined,
  SettingOutlined,
  CloseOutlined,
} from '@ant-design/icons';
import { learningAPI } from '../../api/learning';
import type { LearningRoute } from '../../types/learning';
import dayjs from 'dayjs';

const STATUS_CONFIG: Record<string, { color: string; label: string; icon: React.ReactNode }> = {
  active: { color: 'processing', label: '进行中', icon: <PlayCircleOutlined /> },
  completed: { color: 'success', label: '已完成', icon: <CheckCircleOutlined /> },
  paused: { color: 'warning', label: '已暂停', icon: <PauseCircleOutlined /> },
  generating: { color: 'default', label: '生成中', icon: <LoadingOutlined /> },
};

export const LearningRoutesPage: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [modalVisible, setModalVisible] = useState(false);
  const [topic, setTopic] = useState('');
  const [generating, setGenerating] = useState(false);

  // 管理模式
  const [selectMode, setSelectMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [deleting, setDeleting] = useState(false);

  const { data: routesData, isLoading } = useQuery({
    queryKey: ['learning', 'routes'],
    queryFn: () =>
      learningAPI.listRoutes({ page_size: 50 }).then((res) => {
        const body: any = res.data;
        // 兼容三种后端响应格式：裸数组、PaginatedResponse 或 ApiResponse 包装
        if (Array.isArray(body)) return { items: body, total: body.length };
        if (body?.items) return body;
        if (body?.data?.items) return body.data;
        return { items: [], total: 0 };
      }),
  });

  const routes: LearningRoute[] = (routesData?.items ?? []) as LearningRoute[];

  const handleCreateRoute = async () => {
    if (!topic.trim()) {
      message.warning('请输入学习主题');
      return;
    }
    setGenerating(true);
    try {
      const response = await learningAPI.generateRoute({ topic: topic.trim() });
      // 兼容两种后端响应格式
      const body: any = response.data;
      const newRoute =
        body?.data && typeof body.data === 'object' && 'id' in body.data
          ? body.data
          : body;

      // 安全检查：确保 newRoute 有效
      if (!newRoute || typeof newRoute !== 'object' || !newRoute.id) {
        console.error('[LearningRoutesPage] 后端返回数据异常:', response.data);
        // 后端 202 可能不返回完整路线对象，刷新列表后跳转列表页
        queryClient.invalidateQueries({ queryKey: ['learning', 'routes'] });
        setModalVisible(false);
        setTopic('');
        message.success('路线已创建，AI 正在生成学习步骤...');
        // 不跳转详情页，让用户在列表中看到 "生成中" 状态
        return;
      }
      setModalVisible(false);
      setTopic('');
      queryClient.invalidateQueries({ queryKey: ['learning', 'routes'] });
      if (newRoute?.status === 'generating') {
        message.success('路线已创建，AI 正在生成学习步骤...');
      } else {
        message.success('学习路线创建成功！');
      }
      navigate(`/learning/route/${newRoute.id}`);
    } catch (err) {
      console.error('[LearningRoutesPage] 创建学习路线失败:', err);
      message.error('创建学习路线失败，请重试');
    } finally {
      setGenerating(false);
    }
  };

  // ========== 选择逻辑 ==========
  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === routes.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(routes.map((r) => r.id)));
    }
  };

  const exitSelectMode = () => {
    setSelectMode(false);
    setSelectedIds(new Set());
  };

  const enterSelectMode = () => {
    setSelectMode(true);
    setSelectedIds(new Set());
  };

  // ========== 删除逻辑 ==========
  const handleSingleDelete = async (routeId: string) => {
    try {
      await learningAPI.deleteRoute(routeId);
      message.success('删除成功');
      queryClient.invalidateQueries({ queryKey: ['learning', 'routes'] });
      // 同时刷新 Dashboard 的路线数据
      queryClient.invalidateQueries({ queryKey: ['learning', 'routes', 'recent'] });
    } catch (err) {
      console.error('[LearningRoutesPage] 删除路线失败:', err);
      message.error('删除失败，请重试');
    }
  };

  const handleBatchDelete = () => {
    if (selectedIds.size === 0 || deleting) return;

    const ids = Array.from(selectedIds);
    Modal.confirm({
      title: '确认删除',
      content: `确认删除 ${ids.length} 条学习路线？删除后无法恢复，关联的学习步骤、讲义和问答记录也将一并删除。`,
      okText: '确认删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        setDeleting(true);
        try {
          await learningAPI.batchDeleteRoutes(ids);
          message.success(`成功删除 ${ids.length} 条学习路线`);
          queryClient.invalidateQueries({ queryKey: ['learning', 'routes'] });
          queryClient.invalidateQueries({ queryKey: ['learning', 'routes', 'recent'] });
          exitSelectMode();
        } catch (err) {
          console.error('[LearningRoutesPage] 批量删除失败:', err);
          message.error('批量删除失败，请重试');
        } finally {
          setDeleting(false);
        }
      },
    });
  };

  return (
    <div className="learning-routes-page">
      <Breadcrumb style={{ marginBottom: 16 }}>
        <Breadcrumb.Item>
          <span
            style={{ cursor: 'pointer', color: 'var(--color-text-secondary)' }}
            onClick={() => navigate('/')}
          >
            <HomeOutlined /> 首页
          </span>
        </Breadcrumb.Item>
        <Breadcrumb.Item>学习路线</Breadcrumb.Item>
      </Breadcrumb>

      {/* ========== 顶部工具栏 ========== */}
      {selectMode ? (
        <div className="route-manage-bar">
          <Checkbox
            checked={selectedIds.size === routes.length && routes.length > 0}
            indeterminate={selectedIds.size > 0 && selectedIds.size < routes.length}
            onChange={toggleSelectAll}
            disabled={deleting}
          >
            <span className="select-all-label">
              全选 ({selectedIds.size}/{routes.length})
            </span>
          </Checkbox>
          <Button
            danger
            type="primary"
            icon={<DeleteOutlined />}
            onClick={handleBatchDelete}
            disabled={selectedIds.size === 0 || deleting}
            loading={deleting}
          >
            批量删除{selectedIds.size > 0 ? ` (${selectedIds.size})` : ''}
          </Button>
          <Button
            icon={<CloseOutlined />}
            onClick={exitSelectMode}
            disabled={deleting}
          >
            取消
          </Button>
        </div>
      ) : (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>学习路线</h2>
          <div style={{ display: 'flex', gap: 8 }}>
            <Button
              icon={<SettingOutlined />}
              onClick={enterSelectMode}
              disabled={routes.length === 0}
            >
              管理模式
            </Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setModalVisible(true)}
            >
              创建学习路线
            </Button>
          </div>
        </div>
      )}

      {isLoading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}>
          <Spin size="large" tip="加载学习路线..." />
        </div>
      ) : routes.length === 0 ? (
        <Card>
          <Empty description="暂无学习路线，点击上方按钮创建第一条路线">
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setModalVisible(true)}
            >
              创建学习路线
            </Button>
          </Empty>
        </Card>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 16 }}>
          {routes.map((route) => {
            const status = STATUS_CONFIG[route.status] || STATUS_CONFIG.active;
            const completedSteps = route.steps?.filter((s) => s.status === 'completed').length ?? 0;
            const totalSteps = route.total_steps || route.steps?.length || 0;
            const progress = totalSteps > 0 ? Math.round((completedSteps / totalSteps) * 100) : 0;
            const isSelected = selectedIds.has(route.id);

            return (
              <Card
                key={route.id}
                hoverable
                className={`route-card${isSelected ? ' selected' : ''}`}
                onClick={() => {
                  if (selectMode) {
                    toggleSelect(route.id);
                  } else {
                    navigate(`/learning/route/${route.id}`);
                  }
                }}
              >
                {/* 管理模式复选框 */}
                {selectMode && (
                  <div className="route-card-checkbox" onClick={(e) => e.stopPropagation()}>
                    <Checkbox
                      checked={isSelected}
                      onChange={() => toggleSelect(route.id)}
                    />
                  </div>
                )}

                {/* 单条删除按钮（非管理模式悬浮显示） */}
                {!selectMode && (
                  <div className="route-card-delete" onClick={(e) => e.stopPropagation()}>
                    <Popconfirm
                      title="确认删除"
                      description="删除后无法恢复，关联的学习步骤、讲义和问答记录也将一并删除。"
                      onConfirm={() => handleSingleDelete(route.id)}
                      okText="确认删除"
                      cancelText="取消"
                      okType="danger"
                    >
                      <Button
                        size="small"
                        danger
                        icon={<DeleteOutlined />}
                        type="text"
                      />
                    </Popconfirm>
                  </div>
                )}

                <div className="route-card__header">
                  <div className="route-card__title">
                    {route.topic}
                  </div>
                  <Tag color={status.color} className="route-card__tag">
                    {status.icon} {status.label}
                  </Tag>
                </div>

                {route.description && (
                  <div className="route-card__desc">
                    {route.description}
                  </div>
                )}

                <div className="route-card__meta">
                  <span>
                    步骤 {completedSteps}/{totalSteps}
                  </span>
                  {route.estimated_hours != null && (
                    <span>
                      <ClockCircleOutlined style={{ marginRight: 4 }} />
                      {route.estimated_hours}h
                    </span>
                  )}
                </div>

                {/* 进度条 */}
                <div className="route-card__progress">
                  <div
                    className="route-card__progress-fill"
                    style={{
                      width: `${progress}%`,
                      background: progress === 100
                        ? 'var(--color-success)'
                        : 'linear-gradient(90deg, var(--color-primary), #FBBF24)',
                    }}
                  />
                </div>

                <div className="route-card__date">
                  {dayjs(route.created_at).format('YYYY-MM-DD HH:mm')} 创建
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* 创建学习路线弹窗 */}
      <Modal
        title="创建学习路线"
        open={modalVisible}
        onCancel={() => { setModalVisible(false); setTopic(''); }}
        onOk={handleCreateRoute}
        confirmLoading={generating}
        okText="开始生成"
        cancelText="取消"
        destroyOnClose
      >
        <div style={{ marginBottom: 8, color: 'var(--color-text-secondary)', fontSize: 13 }}>
          输入你想学习的主题，AI 将为你生成个性化的学习路线。
        </div>
        <Input
          placeholder="例如：机器学习基础、微积分入门、Python 数据分析..."
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          onPressEnter={handleCreateRoute}
          size="large"
          autoFocus
        />
      </Modal>
    </div>
  );
};
