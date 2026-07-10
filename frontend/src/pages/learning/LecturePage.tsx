// @deprecated 已废弃（Sprint 8），讲义现在通过笔记编辑页 /notes/{noteId} 查看
// pages/learning/LecturePage.tsx

import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, Button, Space, Tag, Spin, Anchor, message } from 'antd';
import { ArrowLeftOutlined, MessageOutlined, FileTextOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import katex from 'katex';
import 'katex/dist/katex.min.css';
import { useQuery } from '@tanstack/react-query';
import { learningAPI } from '../../api/learning';
import { useWebSocket } from '../../hooks/useWebSocket';
import { extractHeadings } from '../../utils/markdown';

export const LecturePage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const { data: lecture, isLoading, refetch } = useQuery({
    queryKey: ['lecture', id],
    queryFn: () => learningAPI.getLecture(id!).then((res) => {
      // 兼容两种后端响应格式：裸Lecture 或 ApiResponse<Lecture> 包装
      const body: any = res.data;
      return body?.data?.id ? body.data : body;
    }),
    enabled: !!id,
  });

  useWebSocket({
    url: lecture?.status === 'generating' ? `/api/v1/ws/lecture-progress/${id}` : null,
    onMessage: (msg) => {
      if (msg.type === 'progress') {
        console.log('生成进度:', msg.data.percent);
      } else if (msg.type === 'complete') {
        message.success('讲义生成完成');
        refetch();
      } else if (msg.type === 'error') {
        message.error(`生成失败: ${msg.data.message}`);
      }
    },
  });

  if (isLoading) {
    return (
      <div className="page-loading">
        <Spin size="large" />
      </div>
    );
  }

  if (!lecture) {
    return <div>讲义不存在</div>;
  }

  const headings = extractHeadings(lecture.content ?? '');

  return (
    <div className="lecture-page">
      <div className="page-header">
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>
            返回
          </Button>
          <h2>{lecture.title}</h2>
          <Tag color={lecture.status === 'generated' ? 'green' : 'orange'}>{lecture.status}</Tag>
        </Space>
        <Space>
          <Button icon={<MessageOutlined />} onClick={() => navigate(`/learning/qa/${id}`)}>
            开始答疑
          </Button>
          <Button
            type="primary"
            icon={<FileTextOutlined />}
            onClick={async () => {
              try {
                await learningAPI.generatePersonalizedSummary({ lecture_id: id! });
                message.success('个性化梳理生成中');
              } catch {
                message.error('生成失败');
              }
            }}
          >
            生成个性化梳理
          </Button>
        </Space>
      </div>

      <div className="lecture-content">
        <div className="main-content">
          {lecture.status === 'generating' ? (
            <div className="lecture-generating">
              <Spin size="large" />
              <p>讲义生成中...</p>
            </div>
          ) : (
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
          )}
        </div>

        <div className="sidebar">
          <Card title="讲义大纲" size="small">
            <Anchor
              items={headings.map((h) => ({
                key: h.id,
                href: `#${h.id}`,
                title: h.title,
              }))}
            />
          </Card>

          {lecture.source_urls && lecture.source_urls.length > 0 && (
            <Card title="参考来源" size="small" className="sidebar-sources">
              {lecture.source_urls.map((url: string, index: number) => (
                <div key={index}>
                  <a href={url} target="_blank" rel="noopener noreferrer">
                    {url}
                  </a>
                </div>
              ))}
            </Card>
          )}
        </div>
      </div>
    </div>
  );
};
