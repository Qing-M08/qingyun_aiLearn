// pages/notes/TagIndexPage.tsx

import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { List, Card, Tag, Pagination, Spin, Empty } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { notesAPI } from '../../api/notes';

export const TagIndexPage: React.FC = () => {
  const { id: tagId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [page, setPage] = React.useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ['tag-index', tagId, page],
    queryFn: () => notesAPI.getTagIndex(tagId!, { page, page_size: 20 }).then((res) => {
      // 兼容三种后端响应格式：裸数组、PaginatedResponse 或 ApiResponse 包装
      const body: any = res.data;
      if (Array.isArray(body)) return { items: body, total: body.length };
      if (body?.items) return body;
      if (body?.data?.items) return body.data;
      return { items: [], total: 0 };
    }),
    enabled: !!tagId,
  });

  if (isLoading) {
    return (
      <div className="page-loading">
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div className="tag-index-page">
      <h2>标签索引</h2>
      <List
        dataSource={(data as any)?.items || []}
        renderItem={(item: any) => (
          <List.Item>
            <Card
              className="tag-index-card"
              onClick={() => navigate(`/notes/${item.note_id}`)}
            >
              <Card.Meta
                title={
                  <span>
                    {item.note_title} <Tag color={item.tag_color}>{item.tag_name}</Tag>
                  </span>
                }
                description={
                  <div>
                    <div className="tag-index-highlight">
                      <strong>标记内容：</strong>
                      <span className="tag-index-text">
                        {item.content_text}
                      </span>
                    </div>
                    {item.context && (
                      <div className="tag-index-context">
                        <strong>上下文：</strong>
                        {item.context}
                      </div>
                    )}
                  </div>
                }
              />
            </Card>
          </List.Item>
        )}
        locale={{ emptyText: <Empty description="该标签下暂无笔记" /> }}
      />
      <Pagination
        current={page}
        total={(data as any)?.total || 0}
        pageSize={20}
        onChange={setPage}
        className="tag-index-pagination"
      />
    </div>
  );
};
