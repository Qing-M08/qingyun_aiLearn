// pages/review/ReviewSessionPage.tsx

import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Spin, message, Button, Card, Steps, Space, Breadcrumb } from 'antd';
import {
  HomeOutlined,
  ArrowLeftOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import { ReviewCard } from '../../components/review/ReviewCard';
import { QuizCard } from '../../components/review/QuizCard';
import { MasteryBar } from '../../components/review/MasteryBar';
import { reviewAPI } from '../../api/review';
import type {
  ReviewPlan,
  FlashcardContent,
  QuizContent,
  ExplanationContent,
  ReviewContentType,
} from '../../types/review';

export const ReviewSessionPage: React.FC = () => {
  const { id: planId } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [plan, setPlan] = useState<ReviewPlan | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isCompleted, setIsCompleted] = useState(false);

  const [flashcardContent, setFlashcardContent] = useState<FlashcardContent | null>(null);
  const [quizContent, setQuizContent] = useState<QuizContent | null>(null);
  const [explanationContent, setExplanationContent] = useState<ExplanationContent | null>(null);

  const [selfRating, setSelfRating] = useState<number | null>(null);
  const [quizAnswered, setQuizAnswered] = useState(false);

  useEffect(() => {
    if (!planId) return;
    const initSession = async () => {
      setIsLoading(true);
      try {
        const plansRes = await reviewAPI.getPlans({ page: 1, page_size: 1 });
        // 兼容三种后端响应格式：裸数组、PaginatedResponse 或 ApiResponse 包装
        const plansBody: any = plansRes.data;
        let plansItems: any[] = [];
        if (Array.isArray(plansBody)) {
          plansItems = plansBody;
        } else if (plansBody?.items) {
          plansItems = plansBody.items;
        } else if (plansBody?.data?.items) {
          plansItems = plansBody.data.items;
        }
        const items: ReviewPlan[] = plansItems;
        const planData = items.find(
          (p) => p.id === planId
        );
        if (!planData) {
          message.error('复习计划不存在');
          navigate('/review');
          return;
        }
        setPlan(planData);

        const reviewType = mapReviewType(planData.review_type);
        const contentRes = await reviewAPI.generateContent({
          node_id: planData.node_id,
          review_type: reviewType,
        });

        // 兼容两种后端响应格式
        const contentBody: any = contentRes.data;
        const content = contentBody?.data?.content ?? contentBody?.content ?? '';
        switch (reviewType) {
          case 'flashcard':
            setFlashcardContent(JSON.parse(content) as FlashcardContent);
            break;
          case 'quiz':
            setQuizContent(JSON.parse(content) as QuizContent);
            break;
          case 'explanation':
            setExplanationContent(JSON.parse(content) as ExplanationContent);
            break;
        }
      } catch {
        message.error('加载复习内容失败');
      } finally {
        setIsLoading(false);
      }
    };
    initSession();
  }, [planId, navigate]);

  function mapReviewType(type: string): ReviewContentType {
    switch (type) {
      case 'spaced':
        return 'flashcard';
      case 'exam':
        return 'quiz';
      case 'custom':
        return 'explanation';
      default:
        return 'flashcard';
    }
  }

  const handleFlashcardRate = useCallback(
    async (rating: number) => {
      if (!planId) return;
      setSelfRating(rating);
      setIsSubmitting(true);
      try {
        await reviewAPI.completePlan(planId, { performance: rating });
        setIsCompleted(true);
        message.success('复习完成！');
      } catch {
        message.error('提交复习结果失败');
      } finally {
        setIsSubmitting(false);
      }
    },
    [planId]
  );

  const handleQuizAnswer = useCallback(
    async (_selectedIndex: number, isCorrect: boolean) => {
      setQuizAnswered(true);
      const rating = isCorrect ? 5 : 2;
      setSelfRating(rating);
    },
    []
  );

  const handleSubmitQuiz = useCallback(async () => {
    if (!planId || selfRating === null) return;
    setIsSubmitting(true);
    try {
      await reviewAPI.completePlan(planId, { performance: selfRating });
      setIsCompleted(true);
      message.success('复习完成！');
    } catch {
      message.error('提交复习结果失败');
    } finally {
      setIsSubmitting(false);
    }
  }, [planId, selfRating]);

  if (isLoading) {
    return (
      <div className="review-session-page__loading">
        <Spin size="large" tip="加载复习内容..." />
      </div>
    );
  }

  if (!plan) {
    return (
      <div className="review-session-page__empty">
        <p>复习计划不存在</p>
        <Button onClick={() => navigate('/review')}>返回复习列表</Button>
      </div>
    );
  }

  return (
    <div className="review-session-page">
      <Breadcrumb className="review-session-page__breadcrumb">
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
            onClick={() => navigate('/review')}
          >
            复习管理
          </span>
        </Breadcrumb.Item>
        <Breadcrumb.Item>复习中</Breadcrumb.Item>
      </Breadcrumb>

      <div className="review-session-page__header">
        <Button
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate('/review')}
          type="text"
        />
        <h2>
          复习：{plan.node?.name || plan.node_id}
        </h2>
      </div>

      <div className="review-session-page__content">
        {flashcardContent && (
          <ReviewCard
            content={flashcardContent}
            onRate={handleFlashcardRate}
            isCompleted={isCompleted}
          />
        )}

        {quizContent && (
          <div>
            <QuizCard
              content={quizContent}
              onAnswer={handleQuizAnswer}
              isCompleted={isCompleted}
            />
            {quizAnswered && !isCompleted && (
              <Button
                type="primary"
                onClick={handleSubmitQuiz}
                block
                className="review-session-btn"
                loading={isSubmitting}
              >
                提交复习结果
              </Button>
            )}
          </div>
        )}

        {explanationContent && (
          <Card className="review-session-page__explanation">
            <h3>{explanationContent.title}</h3>
            <div className="review-session-page__explanation-content">
              <ReactMarkdown>{explanationContent.content}</ReactMarkdown>
            </div>
            {explanationContent.keyPoints.length > 0 && (
              <div className="review-session-page__key-points">
                <h4>要点回顾</h4>
                <Steps
                  direction="vertical"
                  size="small"
                  items={explanationContent.keyPoints.map((point) => ({
                    title: point,
                    status: 'finish' as const,
                  }))}
                />
              </div>
            )}
            {!isCompleted && (
              <Button
                type="primary"
                icon={<CheckCircleOutlined />}
                onClick={async () => {
                  setIsSubmitting(true);
                  try {
                    await reviewAPI.completePlan(planId!, { performance: 4 });
                    setIsCompleted(true);
                    message.success('复习完成！');
                  } catch {
                    message.error('提交复习结果失败');
                  } finally {
                    setIsSubmitting(false);
                  }
                }}
                block
                loading={isSubmitting}
              >
                我已掌握，完成复习
              </Button>
            )}
          </Card>
        )}
      </div>

      {isCompleted && (
        <div className="review-session-page__complete">
          <Card>
            <div className="review-session-page__complete-content">
              <CheckCircleOutlined className="review-complete-icon" />
              <h3>复习完成！</h3>
              {plan.node && (
                <MasteryBar
                  score={selfRating != null ? selfRating / 5 : 0}
                  nodeName={plan.node.name}
                  reviewCount={plan.node.review_count}
                />
              )}
              <Space className="review-complete-actions">
                <Button onClick={() => navigate('/review')}>
                  返回复习列表
                </Button>
                <Button type="primary" onClick={() => navigate('/')}>
                  返回首页
                </Button>
              </Space>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
};
