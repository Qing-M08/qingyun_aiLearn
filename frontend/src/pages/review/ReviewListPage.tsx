// pages/review/ReviewListPage.tsx

import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Spin,
  message,
  Button,
  Table,
  Tag,
  Select,
  DatePicker,
  Space,
  Breadcrumb,
  Card,
} from 'antd';
import {
  HomeOutlined,
  PlayCircleOutlined,
  CalendarOutlined,
} from '@ant-design/icons';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts';
import { ReviewStatsCards } from '../../components/review/ReviewStatsCards';
import { reviewAPI } from '../../api/review';
import type { ReviewPlan, ReviewStats } from '../../types/review';
import type { PaginatedResponse } from '../../types/common';
import dayjs from 'dayjs';

const { RangePicker } = DatePicker;

const STATUS_CONFIG: Record<string, { color: string; label: string }> = {
  pending: { color: 'processing', label: '待复习' },
  completed: { color: 'success', label: '已完成' },
  skipped: { color: 'default', label: '已跳过' },
};

const PRIORITY_CONFIG: Record<number, { color: string; label: string }> = {
  1: { color: 'red', label: '最高' },
  2: { color: 'orange', label: '高' },
  3: { color: 'blue', label: '中' },
  4: { color: 'default', label: '低' },
  5: { color: 'default', label: '最低' },
};

const PIE_COLORS = ['#9CA3AF', '#F59E0B', '#3B82F6', '#10B981'];

export const ReviewListPage: React.FC = () => {
  const navigate = useNavigate();

  const [plans, setPlans] = useState<ReviewPlan[]>([]);
  const [stats, setStats] = useState<ReviewStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const params: Record<string, unknown> = {
        page: pagination.current,
        page_size: pagination.pageSize,
      };
      if (statusFilter !== 'all') params.status = statusFilter;
      if (dateRange) {
        params.from_date = dateRange[0].format('YYYY-MM-DD');
        params.to_date = dateRange[1].format('YYYY-MM-DD');
      }

      const [plansRes, statsRes] = await Promise.all([
        reviewAPI.getPlans(params as Record<string, string>),
        reviewAPI.getStats(),
      ]);

      // 兼容三种后端响应格式：裸数组、PaginatedResponse 或 ApiResponse 包装
      const plansBody: any = plansRes.data;
      let plansData: any;
      if (Array.isArray(plansBody)) {
        plansData = { items: plansBody, total: plansBody.length };
      } else if (plansBody?.items) {
        plansData = plansBody;
      } else {
        plansData = plansBody?.data ?? { items: [], total: 0 };
      }
      setPlans(plansData.items ?? []);
      setPagination((prev) => ({ ...prev, total: plansData.total ?? 0 }));

      const statsBody: any = statsRes.data;
      setStats(statsBody?.data ?? statsBody);
    } catch {
      message.error('加载复习数据失败');
    } finally {
      setIsLoading(false);
    }
  }, [pagination.current, pagination.pageSize, statusFilter, dateRange]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const masteryChartData = stats?.mastery_distribution
    ? [
        { name: '未开始', value: stats.mastery_distribution.not_started },
        { name: '学习中', value: stats.mastery_distribution.learning },
        { name: '熟悉', value: stats.mastery_distribution.familiar },
        { name: '已掌握', value: stats.mastery_distribution.mastered },
      ]
    : [];

  const columns = [
    {
      title: '知识点',
      dataIndex: ['node', 'name'],
      key: 'node_name',
      render: (name: string, record: ReviewPlan) => name || record.node_id,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const config = STATUS_CONFIG[status];
        return <Tag color={config?.color}>{config?.label || status}</Tag>;
      },
    },
    {
      title: '优先级',
      dataIndex: 'priority',
      key: 'priority',
      render: (priority: number) => {
        const config = PRIORITY_CONFIG[priority];
        return <Tag color={config?.color}>{config?.label || `P${priority}`}</Tag>;
      },
    },
    {
      title: '计划时间',
      dataIndex: 'scheduled_at',
      key: 'scheduled_at',
      render: (date: string) => date ? dayjs(date).format('MM-DD HH:mm') : '-',
      sorter: (a: ReviewPlan, b: ReviewPlan) =>
        dayjs(a.scheduled_at).valueOf() - dayjs(b.scheduled_at).valueOf(),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: ReviewPlan) => (
        <Button
          type="link"
          icon={<PlayCircleOutlined />}
          disabled={record.status !== 'pending'}
          onClick={() => navigate(`/review/${record.id}`)}
        >
          开始复习
        </Button>
      ),
    },
  ];

  return (
    <div className="review-list-page">
      <Breadcrumb className="review-list-page__breadcrumb">
        <Breadcrumb.Item>
          <span
            style={{ cursor: 'pointer', color: 'var(--color-text-secondary)' }}
            onClick={() => navigate('/')}
          >
            <HomeOutlined /> 首页
          </span>
        </Breadcrumb.Item>
        <Breadcrumb.Item>复习管理</Breadcrumb.Item>
      </Breadcrumb>

      <h2>复习管理</h2>

      {stats && <ReviewStatsCards stats={stats} />}

      {stats?.mastery_distribution && (
        <Card title="掌握度分布" className="review-list-page__chart-card">
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie
                data={masteryChartData}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={100}
                paddingAngle={2}
                dataKey="value"
                label={({ name, percent }) =>
                  `${name} ${(percent * 100).toFixed(0)}%`
                }
              >
                {masteryChartData.map((_entry, index) => (
                  <Cell key={index} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </Card>
      )}

      <div className="review-list-page__filters">
        <Space wrap>
          <Select
            value={statusFilter}
            onChange={setStatusFilter}
            options={[
              { label: '全部', value: 'all' },
              { label: '待复习', value: 'pending' },
              { label: '已完成', value: 'completed' },
              { label: '已跳过', value: 'skipped' },
            ]}
          />
          <RangePicker
            value={dateRange}
            onChange={(dates) =>
              setDateRange(dates as [dayjs.Dayjs, dayjs.Dayjs] | null)
            }
            prefix={<CalendarOutlined />}
          />
        </Space>
      </div>

      <Table
        columns={columns}
        dataSource={plans}
        rowKey="id"
        loading={isLoading}
        pagination={{
          current: pagination.current,
          pageSize: pagination.pageSize,
          total: pagination.total,
          onChange: (page, pageSize) =>
            setPagination((prev) => ({
              ...prev,
              current: page,
              pageSize: pageSize || 20,
            })),
          showSizeChanger: true,
          showTotal: (total) => `共 ${total} 条`,
        }}
      />
    </div>
  );
};
