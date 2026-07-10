// pages/learning/PersonalizedDocPage.tsx

import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, Button, Space, Tag, Spin, message } from 'antd';
import { ArrowLeftOutlined, DownloadOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import katex from 'katex';
import 'katex/dist/katex.min.css';
import { useQuery } from '@tanstack/react-query';
import { learningAPI } from '../../api/learning';

export const PersonalizedDocPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const { data: lecture, isLoading } = useQuery({
    queryKey: ['lecture', id, 'personalized'],
    queryFn: () => learningAPI.getLecture(id!).then((res) => {
      // 兼容两种后端响应格式：裸Lecture 或 ApiResponse<Lecture> 包装
      const body: any = res.data;
      return body?.data?.id ? body.data : body;
    }),
    enabled: !!id,
  });

  const handleExport = () => {
    if (!lecture) return;
    const blob = new Blob([lecture.content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${lecture.title}-个性化梳理.md`;
    a.click();
    URL.revokeObjectURL(url);
    message.success('导出成功');
  };

  if (isLoading) {
    return (
      <div className="page-loading">
        <Spin size="large" />
      </div>
    );
  }

  if (!lecture) {
    return <div>文档不存在</div>;
  }

  return (
    <div className="personalized-doc-page">
      <div className="page-header">
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>
            返回
          </Button>
          <h2>{lecture.title}</h2>
          <Tag color="purple">个性化梳理</Tag>
        </Space>
        <Button icon={<DownloadOutlined />} onClick={handleExport}>
          导出为Markdown
        </Button>
      </div>

      <Card>
        <ReactMarkdown
          components={{
            p: ({ children }) => {
              const text = String(children);
              const blockParts = text.split(/\$\$(.*?)\$\$/g);
              if (blockParts.length > 1) {
                return (
                  <p>
                    {blockParts.map((part, i) =>
                      i % 2 === 1 ? (
                        <div
                          key={i}
                          dangerouslySetInnerHTML={{
                            __html: katex.renderToString(part, {
                              throwOnError: false,
                              displayMode: true,
                            }),
                          }}
                          className="block-latex"
                        />
                      ) : (
                        part
                      )
                    )}
                  </p>
                );
              }
              const inlineParts = text.split(/\$([^$]+)\$/g);
              if (inlineParts.length > 1) {
                return (
                  <p>
                    {inlineParts.map((part, i) =>
                      i % 2 === 1 ? (
                        <span
                          key={i}
                          dangerouslySetInnerHTML={{
                            __html: katex.renderToString(part, { throwOnError: false }),
                          }}
                        />
                      ) : (
                        part
                      )
                    )}
                  </p>
                );
              }
              return <p>{children}</p>;
            },
          }}
        >
          {lecture.content}
        </ReactMarkdown>
      </Card>
    </div>
  );
};
