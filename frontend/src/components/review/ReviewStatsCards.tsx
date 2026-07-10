// components/review/ReviewStatsCards.tsx

import React from 'react';
import type { ReviewStats } from '../../types/review';
import { Card, Col, Row, Statistic } from 'antd';
import {
  ClockCircleOutlined,
  CheckCircleOutlined,
  WarningOutlined,
} from '@ant-design/icons';

interface ReviewStatsCardsProps {
  stats: ReviewStats;
}

export const ReviewStatsCards: React.FC<ReviewStatsCardsProps> = ({ stats }) => {
  return (
    <Row gutter={16} className="review-stats-cards">
      <Col span={8}>
        <Card className="review-stats-cards__card">
          <Statistic
            title="今日待复习"
            value={stats.today_due}
            prefix={<ClockCircleOutlined />}
            suffix="项"
          />
        </Card>
      </Col>
      <Col span={8}>
        <Card className="review-stats-cards__card">
          <Statistic
            title="本周已完成"
            value={stats.this_week_completed}
            prefix={<CheckCircleOutlined />}
            suffix="项"
          />
        </Card>
      </Col>
      <Col span={8}>
        <Card className="review-stats-cards__card">
          <Statistic
            title="已逾期"
            value={stats.overdue_count}
            prefix={<WarningOutlined />}
            suffix="项"
          />
        </Card>
      </Col>
    </Row>
  );
};
