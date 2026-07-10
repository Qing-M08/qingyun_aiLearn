// components/chat/MessageBubble.tsx

import React from 'react';
import ReactMarkdown from 'react-markdown';
import type { DisplayMessage } from '../../types/learning';
import { StreamingText } from './StreamingText';
import { Avatar } from 'antd';
import { UserOutlined, RobotOutlined } from '@ant-design/icons';

interface MessageBubbleProps {
  message: DisplayMessage;
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';

  if (isSystem) {
    return (
      <div className="message-bubble message-bubble--system">
        <div className="message-bubble__system-text">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div
      className={`message-bubble ${isUser ? 'message-bubble--user' : 'message-bubble--assistant'}`}
    >
      <Avatar
        className="message-bubble__avatar"
        icon={isUser ? <UserOutlined /> : <RobotOutlined />}
        size={36}
      />

      <div className="message-bubble__body">
        <div className="message-bubble__bubble">
          {isUser ? (
            <div className="message-bubble__text">{message.content}</div>
          ) : message.isStreaming ? (
            <StreamingText
              content={message.content}
              isStreaming={true}
            />
          ) : (
            <div className="message-bubble__markdown">
              <ReactMarkdown>{message.content}</ReactMarkdown>
            </div>
          )}
        </div>
        <div className="message-bubble__time">
          {new Date(message.created_at).toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </div>
      </div>
    </div>
  );
};
