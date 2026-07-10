// pages/learning/LearningRoutePage.tsx

import React, { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Spin, message, Button, Breadcrumb, Tag } from 'antd';
import {
  ArrowLeftOutlined,
  HomeOutlined,
  LoadingOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  PlayCircleOutlined,
  PauseCircleOutlined,
} from '@ant-design/icons';
import { RouteTimeline } from '../../components/learning/RouteTimeline';
import { learningAPI } from '../../api/learning';
import { useWebSocket } from '../../hooks/useWebSocket';
import { useLearningStore } from '../../stores/learningStore';
import type {
  LearningRoute,
  RouteProgress,
  StepFilterStatus,
  Lecture,
} from '../../types/learning';

export const LearningRoutePage: React.FC = () => {
  const { id: routeId } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [currentRoute, setCurrentRoute] = useState<LearningRoute | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState<StepFilterStatus>('all');
  const [lectureProgress, setLectureProgress] = useState<{
    lectureId: string;
    stage: string;
    percent: number;
  } | null>(null);
  const [descExpanded, setDescExpanded] = useState(false);
  const descRef = useRef<HTMLParagraphElement>(null);
  const [descOverflow, setDescOverflow] = useState(false);

  // Sprint 8: 步骤→讲义笔记映射
  const [stepLectureNoteMap, setStepLectureNoteMap] = useState<Map<string, string>>(new Map());

  // Sprint 8: 从 store 监听讲义完成跳转和失败状态
  const lectureCompleteNoteId = useLearningStore(s => s.lectureCompleteNoteId);
  const lectureNoteFailed = useLearningStore(s => s.lectureNoteFailed);

  // 轮询定时器引用
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 清理轮询定时器
  const clearPollTimer = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  // 组件卸载时清理
  useEffect(() => {
    return () => clearPollTimer();
  }, [clearPollTimer]);

  // Sprint 8: 监听讲义完成 → 自动跳转笔记编辑页
  useEffect(() => {
    if (lectureCompleteNoteId) {
      navigate(`/notes/${lectureCompleteNoteId}`);
      useLearningStore.getState().set({ lectureCompleteNoteId: null });
    }
  }, [lectureCompleteNoteId, navigate]);

  // Sprint 8: 监听笔记创建失败
  useEffect(() => {
    if (lectureNoteFailed) {
      message.warning('讲义生成成功，但笔记创建失败，请稍后重试');
      useLearningStore.getState().set({ lectureNoteFailed: false });
    }
  }, [lectureNoteFailed]);

  // 加载路线详情（含生成中轮询）
  useEffect(() => {
    if (!routeId) return;

    let cancelled = false;

    const fetchRoute = async () => {
      if (cancelled) return;
      try {
        const response = await learningAPI.getRoute(routeId);
        // 兼容两种后端响应格式：裸LearningRoute 或 ApiResponse<LearningRoute> 包装
        const body: any = response.data;
        const route =
          body?.data && typeof body.data === 'object' && 'id' in body.data
            ? body.data
            : body;
        // 确保 steps 始终为数组
        if (route && !Array.isArray(route.steps)) route.steps = [];

        if (cancelled) return;
        setCurrentRoute(route);

        // 判断是否需要轮询：状态为 generating 且没有步骤
        const needsPolling =
          route?.status === 'generating' &&
          (!route.steps || route.steps.length === 0);

        if (needsPolling) {
          setIsGenerating(true);
          setIsLoading(false);

          // 每 3 秒轮询一次，直到步骤生成完毕
          pollTimerRef.current = setInterval(async () => {
            if (cancelled) {
              clearPollTimer();
              return;
            }
            try {
              const pollResp = await learningAPI.getRoute(routeId);
              const pollBody: any = pollResp.data;
              const polledRoute =
                pollBody?.data && typeof pollBody.data === 'object' && 'id' in pollBody.data
                  ? pollBody.data
                  : pollBody;
              if (polledRoute && !Array.isArray(polledRoute.steps)) polledRoute.steps = [];

              if (cancelled) return;

              // 如果状态不再是 generating 或已有步骤，停止轮询
              if (
                polledRoute?.status !== 'generating' ||
                (polledRoute?.steps && polledRoute.steps.length > 0)
              ) {
                clearPollTimer();
                setIsGenerating(false);
                setCurrentRoute(polledRoute);
              }
            } catch (pollErr) {
              console.warn('[LearningRoutePage] 轮询路线失败:', pollErr);
              // 轮询失败不中断，继续重试
            }
          }, 3000);
        } else {
          setIsGenerating(false);
          setIsLoading(false);
        }
      } catch (err) {
        if (!cancelled) {
          console.error('[LearningRoutePage] 加载学习路线失败:', err);
          message.error('加载学习路线失败');
          setIsLoading(false);
        }
      }
    };

    setIsLoading(true);
    setIsGenerating(false);
    clearPollTimer();
    fetchRoute();

    return () => {
      cancelled = true;
      clearPollTimer();
    };
  }, [routeId, clearPollTimer]);

  // 检测描述文本是否溢出
  useEffect(() => {
    if (descRef.current) {
      setDescOverflow(descRef.current.scrollHeight > descRef.current.clientHeight);
    }
  }, [currentRoute?.description]);

  // 路线状态标签
  const statusConfig: Record<string, { color: string; icon: React.ReactNode; label: string }> = {
    active: { color: 'processing', icon: <PlayCircleOutlined />, label: '进行中' },
    completed: { color: 'success', icon: <CheckCircleOutlined />, label: '已完成' },
    paused: { color: 'warning', icon: <PauseCircleOutlined />, label: '已暂停' },
    generating: { color: 'default', icon: <LoadingOutlined />, label: '生成中' },
  };

  // 计算路线进度
  const progress: RouteProgress = useMemo(() => {
    if (!currentRoute) {
      return {
        totalSteps: 0,
        completedSteps: 0,
        inProgressSteps: 0,
        pendingSteps: 0,
        percentComplete: 0,
        estimatedMinutesRemaining: 0,
      };
    }
    const steps = currentRoute.steps ?? [];
    const totalSteps = steps.length;
    const completedSteps = steps.filter((s) => s.status === 'completed').length;
    const inProgressSteps = steps.filter((s) => s.status === 'in_progress').length;
    const pendingSteps = steps.filter((s) => s.status === 'pending').length;
    const percentComplete = totalSteps > 0 ? (completedSteps / totalSteps) * 100 : 0;
    const estimatedMinutesRemaining = steps
      .filter((s) => s.status !== 'completed')
      .reduce((sum, s) => sum + (s.estimated_minutes || 30), 0);

    return {
      totalSteps,
      completedSteps,
      inProgressSteps,
      pendingSteps,
      percentComplete,
      estimatedMinutesRemaining,
    };
  }, [currentRoute]);

  // 当前进行中的步骤
  const currentStepId = useMemo(() => {
    if (!currentRoute?.steps) return null;
    const inProgress = currentRoute.steps.find((s) => s.status === 'in_progress');
    return inProgress?.id || null;
  }, [currentRoute]);

  // WebSocket监听讲义生成进度
  const handleLectureProgress = useCallback(
    (wsMsg: { type: string; data: unknown }) => {
      console.log('[LearningRoutePage] WebSocket message:', wsMsg.type, wsMsg.data);
      if (wsMsg.type === 'progress') {
        const data = wsMsg.data as { stage: string; percent: number };
        setLectureProgress((prev) => ({
          lectureId: prev?.lectureId || '',
          stage: data.stage,
          percent: data.percent,
        }));
      } else if (wsMsg.type === 'complete') {
        const data = wsMsg.data as { lecture: Lecture; note_id: string | null };
        setLectureProgress(null);

        if (data.note_id) {
          // Sprint 8: 有 note_id → 跳转到笔记编辑页
          console.log('[LearningRoutePage] 讲义完成，note_id:', data.note_id);
          message.success('讲义生成完成！正在跳转到笔记...');
          setStepLectureNoteMap(prev => {
            const next = new Map(prev);
            if (data.lecture.step_id) {
              next.set(data.lecture.step_id, data.note_id!);
            }
            return next;
          });
          useLearningStore.getState().set({ lectureCompleteNoteId: data.note_id });
        } else {
          // 回退：后端未推送 note_id，导航到讲义页面
          console.log('[LearningRoutePage] 讲义完成，无 note_id，回退到讲义页');
          message.success('讲义生成完成！');
          navigate(`/learning/lecture/${data.lecture.id}`);
        }
      } else if (wsMsg.type === 'error') {
        const data = wsMsg.data as { message: string };
        setLectureProgress(null);
        message.error(`讲义生成失败：${data.message}`);
      }
    },
    [navigate]
  );

  // 讲义进度WebSocket
  useWebSocket({
    url: lectureProgress
      ? `/api/v1/ws/lecture-progress/${lectureProgress.lectureId}`
      : null,
    onMessage: handleLectureProgress,
    reconnect: false,
  });

  // 生成讲义
  const handleGenerateLecture = useCallback(
    async (stepId: string) => {
      if (!currentRoute?.steps) return;
      const step = currentRoute.steps.find((s) => s.id === stepId);
      if (!step) return;

      try {
        const response = await learningAPI.generateLecture({
          route_id: currentRoute.id,
          step_id: stepId,
          node_id: step.node_id || undefined,
        });
        // 兼容两种后端响应格式
        const body: any = response.data;
        const lectureId =
          body?.data && typeof body.data === 'object' && 'lecture_id' in body.data
            ? body.data.lecture_id
            : body.lecture_id;
        setLectureProgress({
          lectureId,
          stage: '开始生成...',
          percent: 0,
        });
        message.info('正在生成讲义...');
      } catch (err) {
        console.error('[LearningRoutePage] 生成讲义请求失败:', err);
        message.error('生成讲义请求失败');
      }
    },
    [currentRoute]
  );

  // 查看讲义笔记
  const handleViewNote = useCallback(
    (noteId: string) => {
      navigate(`/notes/${noteId}`);
    },
    [navigate]
  );
  const handleStartQA = useCallback(
    async (stepId: string) => {
      if (!currentRoute?.steps) return;
      const step = currentRoute.steps.find((s) => s.id === stepId);
      try {
        const response = await learningAPI.createQASession({
          node_id: step?.node_id || undefined,
          topic: step?.title,
        });
        // 兼容两种后端响应格式
        const body: any = response.data;
        const qaId =
          body?.data && typeof body.data === 'object' && 'id' in body.data
            ? body.data.id
            : body.id;
        navigate(`/learning/qa/${qaId}`);
      } catch (err) {
        console.error('[LearningRoutePage] 创建答疑会话失败:', err);
        message.error('创建答疑会话失败');
      }
    },
    [currentRoute, navigate]
  );

  if (isLoading) {
    return (
      <div className="learning-route-page__loading">
        <Spin size="large" tip="加载学习路线..." />
      </div>
    );
  }

  if (isGenerating) {
    return (
      <div className="learning-route-page__loading">
        <Spin
          size="large"
          indicator={<LoadingOutlined spin />}
          tip={
            <div style={{ marginTop: 16 }}>
              <p style={{ fontSize: 16, fontWeight: 500, marginBottom: 8 }}>
                正在生成学习路线：{currentRoute?.topic}
              </p>
              <p style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>
                AI 正在为您规划学习步骤，请稍候...
              </p>
            </div>
          }
        >
          {/* Spin 的 tip 需要 children 才能正确渲染 */}
          <div style={{ minHeight: 200 }} />
        </Spin>
      </div>
    );
  }

  if (!currentRoute) {
    return (
      <div className="learning-route-page__empty">
        <p>学习路线不存在或已被删除</p>
        <Button onClick={() => navigate('/')}>返回首页</Button>
      </div>
    );
  }

  return (
    <div className="learning-route-page">
      <Breadcrumb className="learning-route-page__breadcrumb">
        <Breadcrumb.Item>
          <span
            style={{ cursor: 'pointer', color: 'var(--color-text-secondary)' }}
            onClick={() => navigate('/')}
          >
            <HomeOutlined /> 首页
          </span>
        </Breadcrumb.Item>
        <Breadcrumb.Item>
          <span
            style={{ cursor: 'pointer', color: 'var(--color-text-secondary)' }}
            onClick={() => navigate('/learning')}
          >
            学习路线
          </span>
        </Breadcrumb.Item>
        <Breadcrumb.Item>{currentRoute.topic}</Breadcrumb.Item>
      </Breadcrumb>

      <div className="learning-route-page__header">
        <Button
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate(-1)}
          type="text"
        />
        <div className="learning-route-page__title-area">
          <div className="learning-route-page__title-row">
            <h2>{currentRoute.topic}</h2>
            {currentRoute.status && statusConfig[currentRoute.status] && (
              <Tag
                color={statusConfig[currentRoute.status].color}
                icon={statusConfig[currentRoute.status].icon}
                className="route-detail__status-tag"
              >
                {statusConfig[currentRoute.status].label}
              </Tag>
            )}
          </div>
          <div className="learning-route-page__meta-row">
            <span><ClockCircleOutlined /> {currentRoute.estimated_hours ?? '?'} 小时</span>
            <span>共 {currentRoute.total_steps || (currentRoute.steps?.length ?? 0)} 步骤</span>
          </div>
          {currentRoute.description && (
            <div className="learning-route-page__desc-wrapper">
              <p
                ref={descRef}
                className={`learning-route-page__desc ${descExpanded ? 'expanded' : 'collapsed'}`}
              >
                {currentRoute.description}
              </p>
              {descOverflow && (
                <Button
                  type="link"
                  size="small"
                  className="learning-route-page__desc-toggle"
                  onClick={() => setDescExpanded(!descExpanded)}
                >
                  {descExpanded ? '收起' : '展开全文'}
                </Button>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="learning-route-page__progress-section">
        <div className="route-detail__progress-bar">
          <div
            className="route-detail__progress-fill"
            style={{
              width: `${progress.percentComplete}%`,
              background:
                progress.percentComplete === 100
                  ? 'var(--color-success)'
                  : 'linear-gradient(90deg, var(--color-primary), #FBBF24)',
            }}
          />
        </div>
        <div className="route-detail__progress-stats">
          <span className="route-detail__progress-pct">
            {Math.round(progress.percentComplete)}%
          </span>
          <span className="route-detail__progress-text">
            {progress.completedSteps}/{progress.totalSteps} 已完成
            {progress.estimatedMinutesRemaining > 0 && (
              <> · 预计剩余 {progress.estimatedMinutesRemaining} 分钟</>
            )}
          </span>
        </div>
      </div>

      {lectureProgress && (
        <div className="learning-route-page__progress-banner">
          <span>正在生成讲义：{lectureProgress.stage}</span>
          <span>{lectureProgress.percent}%</span>
        </div>
      )}

      <RouteTimeline
        steps={currentRoute.steps ?? []}
        progress={progress}
        currentStepId={currentStepId}
        selectedStepId={selectedStepId}
        filterStatus={filterStatus}
        stepLectureNoteMap={stepLectureNoteMap}
        onStepSelect={setSelectedStepId}
        onStepGenerateLecture={handleGenerateLecture}
        onStepStartQA={handleStartQA}
        onStepViewNote={handleViewNote}
        onFilterChange={setFilterStatus}
      />
    </div>
  );
};
