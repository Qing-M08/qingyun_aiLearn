// components/chat/StreamingText.tsx

import React, { useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import katex from 'katex';
import 'katex/dist/katex.min.css';
import { sanitizeMarkdown } from '../../utils/markdown';

interface StreamingTextProps {
  content: string;
  isStreaming: boolean;
}

// KaTeX行内公式渲染
const LatexRenderer = ({ children }: { children: string }) => {
  const html = katex.renderToString(children, {
    throwOnError: false,
    displayMode: false,
  });
  return <span dangerouslySetInnerHTML={{ __html: html }} />;
};

// KaTeX块级公式渲染
const BlockLatexRenderer = ({ children }: { children: string }) => {
  const html = katex.renderToString(children, {
    throwOnError: false,
    displayMode: true,
  });
  return <div className="block-latex" dangerouslySetInnerHTML={{ __html: html }} />;
};

export const StreamingText: React.FC<StreamingTextProps> = ({ content, isStreaming }) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isStreaming && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [content, isStreaming]);

  const displayContent = isStreaming ? sanitizeMarkdown(content) : content;

  return (
    <div ref={containerRef} className="streaming-text">
      <ReactMarkdown
        components={{
          p: ({ children }) => {
            const text = String(children);
            const blockParts = text.split(/\$\$(.*?)\$\$/g);
            if (blockParts.length > 1) {
              return (
                <p>
                  {blockParts.map((part, i) =>
                    i % 2 === 1 ? <BlockLatexRenderer key={i}>{part}</BlockLatexRenderer> : part
                  )}
                </p>
              );
            }
            const inlineParts = text.split(/\$([^$]+)\$/g);
            if (inlineParts.length > 1) {
              return (
                <p>
                  {inlineParts.map((part, i) =>
                    i % 2 === 1 ? <LatexRenderer key={i}>{part}</LatexRenderer> : part
                  )}
                </p>
              );
            }
            return <p>{children}</p>;
          },
          code: ({ className, children, ...props }) => {
            const match = /language-(\w+)/.exec(className || '');
            const isInline = !match;
            if (isInline) {
              return (
                <code className={className} {...props}>
                  {children}
                </code>
              );
            }
            return (
              <pre className={className}>
                <code {...props}>{children}</code>
              </pre>
            );
          },
        }}
      >
        {displayContent}
      </ReactMarkdown>
      {isStreaming && <span className="streaming-cursor">|</span>}
    </div>
  );
};
