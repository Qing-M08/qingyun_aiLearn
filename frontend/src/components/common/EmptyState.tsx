// components/common/EmptyState.tsx

import React from 'react';
import { Empty, Button } from 'antd';

interface EmptyStateProps {
  description?: string;
  actionText?: string;
  onAction?: () => void;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  description = '暂无数据',
  actionText,
  onAction,
}) => {
  return (
    <Empty description={description}>
      {actionText && onAction && (
        <Button type="primary" onClick={onAction}>
          {actionText}
        </Button>
      )}
    </Empty>
  );
};
