// components/editor/MarkdownPreview.tsx

import React, { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface MarkdownPreviewProps {
  content: string;
}

/** 将 $$...$$ 块公式转为预处理标记，避免被 markdown 解析器破坏 */
function preprocessLatexBlocks(text: string): { html: string }[] {
  const blocks: { html: string }[] = [];
  const parts = text.split(/(\$\$[\s\S]*?\$\$)/g);
  let result = '';

  for (const part of parts) {
    if (part.startsWith('$$') && part.endsWith('$$')) {
      const formula = part.slice(2, -2).trim();
      const idx = blocks.length;
      blocks.push({
        html: `<div class="block-latex">\\[${formula}\\]</div>`,
      });
      result += `{LATEX_BLOCK_${idx}}`;
    } else {
      result += part;
    }
  }

  return [{ html: result }, ...blocks.slice(1)];
}

export const MarkdownPreview: React.FC<MarkdownPreviewProps> = ({ content }) => {
  const { processedContent, latexBlocks } = useMemo(() => {
    const blocks = preprocessLatexBlocks(content);
    return { processedContent: blocks[0].html, latexBlocks: blocks.slice(1) };
  }, [content]);

  return (
    <div className="editor-content-area markdown-preview">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // 自定义公式块渲染
          p: ({ children, ...props }) => {
            const text = extractText(children);
            if (typeof text === 'string' && text.startsWith('{LATEX_BLOCK_')) {
              const idx = parseInt(text.replace('{LATEX_BLOCK_', '').replace('}', ''), 10);
              if (latexBlocks[idx]) {
                return <div dangerouslySetInnerHTML={{ __html: latexBlocks[idx].html }} />;
              }
            }
            return <p {...props}>{children}</p>;
          },
          // 行内公式 $...$
          code: ({ className, children, ...props }) => {
            const text = String(children);
            // 检测行内 LaTeX（以 $ 包裹在 code 中）
            if (text.startsWith('$') && text.endsWith('$')) {
              return <span className="inline-latex">{text.slice(1, -1)}</span>;
            }
            return (
              <code className={className} {...props}>
                {children}
              </code>
            );
          },
          // 粗体高亮
          strong: ({ children, node, ...props }) => {
            const text = extractText(children);
            if (typeof text === 'string' && text.includes('核心要点')) {
              return <strong className="editor-highlight" style={{ display: 'block' }} {...props}>{children}</strong>;
            }
            return <strong {...props}>{children}</strong>;
          },
          // 表格样式
          table: ({ children }) => (
            <div style={{ overflowX: 'auto', margin: '12px 0' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
                {children}
              </table>
            </div>
          ),
          th: ({ children }) => (
            <th style={{ border: '1px solid var(--color-border)', padding: '8px 12px', background: 'var(--color-bg-input)', fontWeight: 600, textAlign: 'left' }}>
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td style={{ border: '1px solid var(--color-border)', padding: '8px 12px' }}>
              {children}
            </td>
          ),
          // 引用块
          blockquote: ({ children }) => (
            <blockquote style={{ borderLeft: '3px solid var(--color-primary)', paddingLeft: 16, margin: '12px 0', color: 'var(--color-text-secondary)' }}>
              {children}
            </blockquote>
          ),
        }}
      >
        {processedContent}
      </ReactMarkdown>
    </div>
  );
};

/** 递归提取 React children 中的纯文本 */
function extractText(children: React.ReactNode): string {
  if (typeof children === 'string') return children;
  if (typeof children === 'number') return String(children);
  if (Array.isArray(children)) return children.map(extractText).join('');
  if (React.isValidElement(children) && children.props?.children) {
    return extractText(children.props.children);
  }
  return '';
}
