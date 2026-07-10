// components/common/LoadingOverlay.tsx

import React from 'react';
import { Spin } from 'antd';

interface LoadingOverlayProps {
  loading: boolean;
  tip?: string;
  children: React.ReactNode;
}

export const LoadingOverlay: React.FC<LoadingOverlayProps> = ({ loading, tip = '加载中...', children }) => {
  return (
    <div className="loading-overlay-wrapper">
      {children}
      {loading && (
        <div className="loading-overlay">
          <Spin size="large" tip={tip} />
        </div>
      )}
    </div>
  );
};
