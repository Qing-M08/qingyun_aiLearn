// components/review/MasteryBar.tsx

import React from 'react';
import { Progress, Tooltip } from 'antd';

interface MasteryBarProps {
  score: number;
  nodeName: string;
  reviewCount?: number;
  showLabel?: boolean;
}

function getMasteryClass(score: number): string {
  if (score >= 0.8) return 'mastery-mastered';
  if (score >= 0.3) return 'mastery-familiar';
  if (score > 0) return 'mastery-learning';
  return 'mastery-not-started';
}

function getMasteryLabel(score: number): string {
  if (score >= 0.8) return '已掌握';
  if (score >= 0.3) return '熟悉';
  if (score > 0) return '学习中';
  return '未开始';
}

export const MasteryBar: React.FC<MasteryBarProps> = ({
  score,
  nodeName,
  reviewCount,
  showLabel = true,
}) => {
  const percent = Math.round(score * 100);
  const masteryClass = getMasteryClass(score);
  const label = getMasteryLabel(score);

  return (
    <Tooltip
      title={
        reviewCount !== undefined
          ? `${nodeName} — 已复习 ${reviewCount} 次`
          : nodeName
      }
    >
      <div className="mastery-bar">
        {showLabel && (
          <div className="mastery-bar__header">
            <span className="mastery-bar__name">{nodeName}</span>
            <span className={`mastery-bar__label ${masteryClass}`}>
              {label} ({percent}%)
            </span>
          </div>
        )}
        <Progress
          percent={percent}
          showInfo={false}
          size="small"
        />
      </div>
    </Tooltip>
  );
};
