// components/learning/StepDetailPanel.tsx

import React from 'react';
import { useNavigate } from 'react-router-dom';
import type { RouteStep } from '../../types/learning';
import { Drawer, Button, Descriptions, Divider, Tag } from 'antd';
import {
  BookOutlined,
  QuestionCircleOutlined,
  ClockCircleOutlined,
  FileTextOutlined,
} from '@ant-design/icons';

interface StepDetailPanelProps {
  step: RouteStep;
  onClose: () => void;
  onGenerateLecture: () => void;
  onStartQA: () => void;
  lectureNoteId?: string | null;
}

const STATUS_LABELS: Record<string, { text: string; color: string }> = {
  pending: { text: '待学习', color: 'default' },
  in_progress: { text: '进行中', color: 'processing' },
  completed: { text: '已完成', color: 'success' },
};

export const StepDetailPanel: React.FC<StepDetailPanelProps> = ({
  step,
  onClose,
  onGenerateLecture,
  onStartQA,
  lectureNoteId,
}) => {
  const navigate = useNavigate();
  const statusInfo = STATUS_LABELS[step.status];

  return (
    <Drawer
      title={step.title}
      open={true}
      onClose={onClose}
      width={400}
      className="step-detail-panel"
    >
      <Descriptions column={1} size="small">
        <Descriptions.Item label="状态">
          <Tag color={statusInfo.color}>{statusInfo.text}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label="步骤序号">
          第 {step.step_order} 步
        </Descriptions.Item>
        {step.estimated_minutes && (
          <Descriptions.Item label="预估时间">
            <ClockCircleOutlined />
            {step.estimated_minutes} 分钟
          </Descriptions.Item>
        )}
        {step.node_id && (
          <Descriptions.Item label="关联知识点">
            {step.node_id}
          </Descriptions.Item>
        )}
      </Descriptions>

      {step.description && (
        <>
          <Divider />
          <div className="step-detail-panel__description">
            {step.description}
          </div>
        </>
      )}

      {step.prerequisites?.length > 0 && (
        <>
          <Divider />
          <div className="step-detail-panel__prereqs">
            <h4>前置步骤</h4>
            {step.prerequisites.map((preId) => (
              <Tag key={preId}>{preId}</Tag>
            ))}
          </div>
        </>
      )}

      <Divider />

      <div className="step-detail-panel__actions">
        <Button
          type="primary"
          icon={<BookOutlined />}
          block
          onClick={onGenerateLecture}
          disabled={step.status === 'completed'}
        >
          生成讲义
        </Button>
        <Button
          icon={<QuestionCircleOutlined />}
          block
          className="step-detail-btn"
          onClick={onStartQA}
        >
          开始答疑
        </Button>
        {step.status === 'completed' && lectureNoteId ? (
          <Button
            type="primary"
            icon={<FileTextOutlined />}
            block
            onClick={() => navigate(`/notes/${lectureNoteId}`)}
          >
            查看讲义笔记
          </Button>
        ) : step.status === 'completed' ? (
          <Button
            block
            className="step-detail-btn"
            disabled
          >
            已完成
          </Button>
        ) : null}
      </div>
    </Drawer>
  );
};
