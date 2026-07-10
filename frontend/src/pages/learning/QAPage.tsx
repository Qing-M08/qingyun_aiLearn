// pages/learning/QAPage.tsx

import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Spin, message, Button, Tag, Alert, Breadcrumb } from 'antd';
import { ArrowLeftOutlined, HomeOutlined, WarningOutlined } from '@ant-design/icons';
import { ChatPanel } from '../../components/chat/ChatPanel';
import { learningAPI } from '../../api/learning';
import type { QASession, DiagnosisResult, QAContextInfo } from '../../types/learning';

export const QAPage: React.FC = () => {
  const { id: sessionId } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [session, setSession] = useState<QASession | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [contextInfo] = useState<QAContextInfo>({});
  const [diagnoses, setDiagnoses] = useState<DiagnosisResult[]>([]);

  useEffect(() => {
    if (!sessionId) return;
    const fetchSession = async () => {
      setIsLoading(true);
      try {
        await learningAPI.getQAMessages(sessionId, { limit: 1 });
        setSession({
          id: sessionId,
          user_id: '',
          lecture_id: null,
          node_id: null,
          topic: null,
          status: 'active',
          created_at: '',
          updated_at: '',
        });
      } catch {
        message.error('加载答疑会话失败');
        navigate('/');
      } finally {
        setIsLoading(false);
      }
    };
    fetchSession();
  }, [sessionId, navigate]);

  const handleDiagnosis = useCallback((diagnosis: DiagnosisResult) => {
    setDiagnoses((prev) => [...prev, diagnosis]);
    if (diagnosis.mastery_update < 0) {
      message.warning(
        `AI检测到你在知识点 ${diagnosis.node_id} 上可能存在薄弱环节，建议加强复习。`,
        8
      );
    }
  }, []);

  if (isLoading) {
    return (
      <div className="qa-page__loading">
        <Spin size="large" tip="加载答疑会话..." />
      </div>
    );
  }

  return (
    <div className="qa-page">
      <Breadcrumb className="qa-page__breadcrumb">
        <Breadcrumb.Item>
          <span
            style={{ cursor: 'pointer', color: 'var(--color-text-secondary)' }}
            onClick={() => navigate('/')}
          >
            <HomeOutlined /> 首页
          </span>
        </Breadcrumb.Item>
        <Breadcrumb.Item>智能答疑</Breadcrumb.Item>
        {session?.topic && <Breadcrumb.Item>{session.topic}</Breadcrumb.Item>}
      </Breadcrumb>

      <div className="qa-page__header">
        <Button
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate(-1)}
          type="text"
        />
        <h2>{session?.topic || '智能答疑'}</h2>
        {session?.status === 'active' && (
          <Tag color="green">进行中</Tag>
        )}
      </div>

      {diagnoses.length > 0 && (
        <div className="qa-page__diagnoses">
          <Alert
            type="info"
            showIcon
            icon={<WarningOutlined />}
            message={`已检测到 ${diagnoses.length} 个知识薄弱点`}
            description={
              <ul>
                {diagnoses.map((d, i) => (
                  <li key={i}>
                    知识点 {d.node_id}：掌握度变化 {d.mastery_update > 0 ? '+' : ''}
                    {d.mastery_update.toFixed(2)}
                  </li>
                ))}
              </ul>
            }
          />
        </div>
      )}

      <ChatPanel
        sessionId={sessionId!}
        contextInfo={contextInfo}
        onDiagnosis={handleDiagnosis}
      />
    </div>
  );
};
