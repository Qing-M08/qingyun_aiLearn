// components/chat/ChatPanel.tsx

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Input, Button, Spin, message } from 'antd';
import { SendOutlined, StopOutlined } from '@ant-design/icons';
import { MessageBubble } from './MessageBubble';
import type { DisplayMessage, QAContextInfo, DiagnosisResult } from '../../types/learning';
import { useWebSocket } from '../../hooks/useWebSocket';
import { learningAPI } from '../../api/learning';

const { TextArea } = Input;

interface ChatPanelProps {
  sessionId: string;
  contextInfo?: QAContextInfo;
  onDiagnosis?: (diagnosis: DiagnosisResult) => void;
}

export const ChatPanel: React.FC<ChatPanelProps> = ({
  sessionId,
  contextInfo,
  onDiagnosis,
}) => {
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 加载历史消息
  useEffect(() => {
    const loadHistory = async () => {
      setIsLoadingHistory(true);
      try {
        const response = await learningAPI.getQAMessages(sessionId, { limit: 50 });
        // 兼容两种后端响应格式：裸数组 或 ApiResponse<T[]> 包装
        const body: any = response.data;
        const rawMessages = Array.isArray(body) ? body : (body?.data ?? []);
        const historyMessages: DisplayMessage[] = rawMessages.map((msg: any) => ({
          ...msg,
          isStreaming: false,
        }));
        setMessages(historyMessages);
      } catch {
        message.error('加载消息历史失败');
      } finally {
        setIsLoadingHistory(false);
      }
    };
    loadHistory();
  }, [sessionId]);

  // WebSocket流式接收
  const handleWSMessage = useCallback(
    (wsMsg: { type: string; data: unknown }) => {
      switch (wsMsg.type) {
        case 'token': {
          const tokenData = wsMsg.data as { content: string };
          setStreamingContent((prev) => prev + tokenData.content);
          setIsStreaming(true);
          break;
        }
        case 'done': {
          const doneData = wsMsg.data as { message: DisplayMessage };
          setMessages((prev) => [
            ...prev,
            { ...doneData.message, isStreaming: false },
          ]);
          setStreamingContent('');
          setIsStreaming(false);
          setIsSending(false);
          break;
        }
        case 'diagnosis': {
          const diagnosisData = wsMsg.data as DiagnosisResult;
          onDiagnosis?.(diagnosisData);
          break;
        }
        case 'error': {
          const errorData = wsMsg.data as { message: string };
          message.error(errorData.message);
          setIsStreaming(false);
          setIsSending(false);
          setStreamingContent('');
          break;
        }
      }
    },
    [onDiagnosis]
  );

  // WebSocket连接（QA流式通道）
  const { isConnected, reconnectCount } = useWebSocket({
    url: `/api/v1/ws/qa-stream/${sessionId}`,
    onMessage: handleWSMessage,
    reconnect: true,
    heartbeatInterval: 30000,
  });

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingContent]);

  // 发送消息
  const handleSend = useCallback(async () => {
    const content = inputValue.trim();
    if (!content || isSending) return;

    setInputValue('');
    setIsSending(true);
    setStreamingContent('');

    const userMessage: DisplayMessage = {
      id: `temp-${Date.now()}`,
      session_id: sessionId,
      role: 'user',
      content,
      metadata: {},
      created_at: new Date().toISOString(),
      isStreaming: false,
    };
    setMessages((prev) => [...prev, userMessage]);

    try {
      const res = await learningAPI.sendQAMessage(sessionId, content);
      // HTTP 响应中包含 assistant_message，直接展示（WebSocket 不可用时的 fallback）
      const body: any = res.data;
      const assistantMsg = body?.data?.assistant_message || body?.assistant_message;
      if (assistantMsg?.content) {
        setMessages((prev) => [
          ...prev,
          { ...assistantMsg, isStreaming: false } as DisplayMessage,
        ]);
      }
      setIsSending(false);
    } catch {
      message.error('发送消息失败，请重试');
      setIsSending(false);
    }
  }, [inputValue, isSending, sessionId]);

  // Enter发送，Shift+Enter换行
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  return (
    <div className="chat-panel">
      {contextInfo && (
        <div className="chat-panel__context">
          {contextInfo.lectureTitle && (
            <span>基于讲义：{contextInfo.lectureTitle}</span>
          )}
          {contextInfo.nodeName && (
            <span>知识点：{contextInfo.nodeName}</span>
          )}
        </div>
      )}

      <div className="chat-panel__messages">
        {isLoadingHistory ? (
          <div className="chat-panel__loading">
            <Spin tip="加载消息中..." />
          </div>
        ) : (
          <>
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            {isStreaming && streamingContent && (
              <MessageBubble
                message={{
                  id: 'streaming',
                  session_id: sessionId,
                  role: 'assistant',
                  content: streamingContent,
                  metadata: {},
                  created_at: new Date().toISOString(),
                  isStreaming: true,
                }}
              />
            )}
            {isSending && !isStreaming && (
              <div className="chat-panel__thinking">
                <Spin size="small" />
                <span>AI思考中...</span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      <div className="chat-panel__input">
        <TextArea
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入你的问题...（Enter发送，Shift+Enter换行）"
          autoSize={{ minRows: 1, maxRows: 4 }}
          disabled={isSending}
          className="chat-panel__textarea"
        />
        <Button
          type="primary"
          icon={isSending ? <StopOutlined /> : <SendOutlined />}
          onClick={handleSend}
          disabled={!inputValue.trim() || isSending}
          loading={isSending && !isStreaming}
          className="chat-panel__send-btn"
        >
          {isSending ? '生成中' : '发送'}
        </Button>
      </div>

      {!isConnected && reconnectCount >= 3 && (
        <div className="chat-panel__status">
          <span className="chat-panel__status-dot chat-panel__status-dot--disconnected" />
          流式连接不可用（仍可发送消息）
        </div>
      )}
    </div>
  );
};
