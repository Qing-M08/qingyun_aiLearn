// components/editor/EditorPreview.tsx

import React from 'react';
import { Radio } from 'antd';
import ReactMarkdown from 'react-markdown';
import katex from 'katex';
import 'katex/dist/katex.min.css';
import { MarkdownEditor } from './MarkdownEditor';
import type { Tag } from '../../types/note';

interface EditorPreviewProps {
  content: string;
  contentJson?: object;
  mode: 'edit' | 'preview' | 'split';
  onModeChange: (mode: 'edit' | 'preview' | 'split') => void;
  onChange?: (content: string, json: object) => void;
  onSave?: () => void;
  editable?: boolean;
  tags?: Tag[];
  onTagAdd?: (tagId: string, contentText: string, startOffset?: number, endOffset?: number) => void;
  onTagRemove?: (tagId: string) => void;
}

export const EditorPreview: React.FC<EditorPreviewProps> = ({
  content,
  contentJson,
  mode,
  onModeChange,
  onChange,
  onSave,
  editable = true,
  tags = [],
  onTagAdd,
  onTagRemove,
}) => {
  return (
    <div className="editor-preview-container">
      <div className="mode-switcher">
        <Radio.Group value={mode} onChange={(e) => onModeChange(e.target.value)}>
          <Radio.Button value="edit">编辑</Radio.Button>
          <Radio.Button value="preview">预览</Radio.Button>
          <Radio.Button value="split">分栏</Radio.Button>
        </Radio.Group>
      </div>
      <div className="editor-area">
        {(mode === 'edit' || mode === 'split') && (
          <div className="edit-pane">
            <MarkdownEditor
              content={content}
              contentJson={contentJson}
              onChange={onChange || (() => {})}
              onSave={onSave || (() => {})}
              editable={editable}
              tags={tags}
              onTagAdd={onTagAdd}
              onTagRemove={onTagRemove}
            />
          </div>
        )}
        {(mode === 'preview' || mode === 'split') && (
          <div className="preview-pane">
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
                              className="block-latex"
                              dangerouslySetInnerHTML={{
                                __html: katex.renderToString(part, { throwOnError: false, displayMode: true }),
                              }}
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
              {content}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
};
