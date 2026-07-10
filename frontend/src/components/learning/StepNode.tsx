// components/learning/StepNode.tsx

import React from 'react';
import type { RouteStep } from '../../types/learning';
import { CheckCircleOutlined, ClockCircleOutlined, PlayCircleOutlined, BookOutlined, QuestionCircleOutlined, FileTextOutlined } from '@ant-design/icons';
import { Tag, Tooltip } from 'antd';

interface StepNodeProps {
  step: RouteStep;
  order: number;
  isCurrent: boolean;
  isSelected: boolean;
  hasDependency: boolean;
  prerequisiteNames: string[];
  lectureNoteId?: string | null;
  onClick: () => void;
  onGenerateLecture: () => void;
  onStartQA: () => void;
  onViewNote: () => void;
}

const STATUS_CONFIG: Record<string, { icon: React.ReactNode; label: string; dotColor: string }> = {
  pending: {
    icon: <ClockCircleOutlined />,
    label: '待学习',
    dotColor: 'var(--color-text-tertiary)',
  },
  in_progress: {
    icon: <PlayCircleOutlined />,
    label: '进行中',
    dotColor: 'var(--color-primary)',
  },
  completed: {
    icon: <CheckCircleOutlined />,
    label: '已完成',
    dotColor: 'var(--color-success)',
  },
};

export const StepNode: React.FC<StepNodeProps> = ({
  step,
  order,
  isCurrent,
  isSelected,
  hasDependency,
  prerequisiteNames,
  lectureNoteId,
  onClick,
  onGenerateLecture,
  onStartQA,
  onViewNote,
}) => {
  const config = STATUS_CONFIG[step.status];

  return (
    <div
      className={`step-node ${isCurrent ? 'step-node--current' : ''} ${isSelected ? 'step-node--selected' : ''}`}
      data-status={step.status}
      onClick={onClick}
    >
      <div className="step-node__indicator">
        <span
          className="step-node__dot"
          style={{ background: config.dotColor }}
        />
        <span className="step-node__order">{order}</span>
      </div>

      <div className="step-node__content">
        <div className="step-node__title">{step.title}</div>
        {step.description && (
          <div className="step-node__desc">{step.description}</div>
        )}
        <div className="step-node__meta">
          <Tag>{config.label}</Tag>
          {step.estimated_minutes && (
            <span className="step-node__time">
              <ClockCircleOutlined />
              {step.estimated_minutes} 分钟
            </span>
          )}
        </div>

        {hasDependency && prerequisiteNames.length > 0 && (
          <div className="step-node__prereqs">
            <span className="step-node__prereqs-label">前置：</span>
            {prerequisiteNames.map((name, i) => (
              <Tag key={i} className="step-node__prereq-tag">{name}</Tag>
            ))}
          </div>
        )}
      </div>

      <div className="step-node__actions">
        {step.status === 'completed' && lectureNoteId ? (
          <Tooltip title="查看讲义笔记">
            <FileTextOutlined
              className="step-node__action-btn"
              onClick={(e) => {
                e.stopPropagation();
                onViewNote();
              }}
            />
          </Tooltip>
        ) : (
          <Tooltip title="生成讲义">
            <BookOutlined
              className="step-node__action-btn"
              onClick={(e) => {
                e.stopPropagation();
                onGenerateLecture();
              }}
            />
          </Tooltip>
        )}
        <Tooltip title="开始答疑">
          <QuestionCircleOutlined
            className="step-node__action-btn"
            onClick={(e) => {
              e.stopPropagation();
              onStartQA();
            }}
          />
        </Tooltip>
      </div>
    </div>
  );
};
