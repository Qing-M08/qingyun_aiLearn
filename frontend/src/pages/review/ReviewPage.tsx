// pages/review/ReviewPage.tsx

import React from 'react';
import { Empty } from 'antd';

/* ===== ReviewPage ===== */
export const ReviewPage: React.FC = () => {
  return (
    <div style={{ maxWidth: 960, margin: '0 auto' }}>
      <div className="page-header">
        <div className="page-title">待复习</div>
      </div>
      <Empty description="暂无复习数据，后端联调后将展示真实复习计划" />
    </div>
  );
};
