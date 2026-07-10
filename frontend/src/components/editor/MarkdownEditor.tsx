// components/editor/MarkdownEditor.tsx

import React, { useEffect, useCallback, useRef } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Highlight from '@tiptap/extension-highlight';
import CodeBlockLowlight from '@tiptap/extension-code-block-lowlight';
import { Markdown } from '@tiptap/markdown';
import { Button, Space, Tooltip } from 'antd';
import {
  BoldOutlined,
  ItalicOutlined,
  OrderedListOutlined,
  UnorderedListOutlined,
  CodeOutlined,
  LinkOutlined,
} from '@ant-design/icons';
import { debounce } from 'lodash';
// lowlight 语言包 - TD-1-007: 后续需按需加载更多语言
import { createLowlight, common } from 'lowlight';
import type { Tag } from '../../types/note';
import { TagToolbar } from './TagToolbar';

interface MarkdownEditorProps {
  content: string;
  contentJson?: object;
  onChange: (content: string, json: object) => void;
  onSave: () => void;
  editable?: boolean;
  tags?: Tag[];
  onTagAdd?: (tagId: string, contentText: string, startOffset?: number, endOffset?: number) => void;
  onTagRemove?: (tagId: string) => void;
}

export const MarkdownEditor: React.FC<MarkdownEditorProps> = ({
  content,
  contentJson,
  onChange,
  onSave,
  editable = true,
  tags = [],
  onTagAdd,
  onTagRemove,
}) => {
  const debouncedOnChange = useCallback(
    debounce((markdown: string, json: object) => {
      onChange(markdown, json);
    }, 2000),
    [onChange]
  );

  // 标记内容变更是否来自编辑器内部，防止 useEffect 反馈循环
  const isInternalChange = useRef(false);

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        codeBlock: false,
      }),
      Highlight,
      CodeBlockLowlight.configure({
        lowlight: createLowlight(common),
      }),
      Markdown,
    ],
    content: contentJson || content,
    // 当 content 是 markdown 字符串时，指定 contentType 让其被正确解析
    contentType: contentJson ? undefined : (content ? 'markdown' : undefined),
    editable,
    editorProps: {
      handlePaste: (_view, event) => {
        const text = event.clipboardData?.getData('text/plain');
        if (!text) return false;

        // 检测是否包含 Markdown 语法特征
        const hasMarkdown = /(^#{1,6}\s|^\s*[-*+]\s|^\s*\d+\.\s|```|`[^`]+`|\[.+\]\(.+\)|[*_~]{1,2}|^>\s)/m.test(text);
        if (!hasMarkdown) return false;

        try {
          const markdownManager = editor?.storage?.markdown?.manager;
          if (!markdownManager) return false;

          const parsed = markdownManager.parse(text);
          if (parsed?.content?.length) {
            editor.commands.insertContent(parsed);
            return true;
          }
        } catch {
          return false;
        }
        return false;
      },
    },
    onUpdate: ({ editor }) => {
      const json = editor.getJSON();
      const markdownText = (editor as any).getMarkdown?.() || '';
      // 标记为内部变更，阻止接下来的 useEffect 重复设置内容
      isInternalChange.current = true;
      debouncedOnChange(markdownText, json);
    },
  });

  // 同步外部 content prop 变更到编辑器（如从 API 加载笔记、AI 生成内容）
  useEffect(() => {
    if (!editor) return;
    // 跳过由编辑器自身 onUpdate 触发的 prop 变更
    if (isInternalChange.current) {
      isInternalChange.current = false;
      return;
    }
    const currentMd = (editor as any).getMarkdown?.() || '';
    // 仅当外部内容与编辑器当前内容不同时才更新
    if (content && content !== currentMd) {
      editor.commands.setContent(content, { contentType: 'markdown' });
    }
  }, [content, editor]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey) {
        if (e.key === 's') {
          e.preventDefault();
          onSave();
        }
        if (e.key === 'b' && editor) {
          e.preventDefault();
          editor.chain().focus().toggleBold().run();
        }
        if (e.key === 'i' && editor) {
          e.preventDefault();
          editor.chain().focus().toggleItalic().run();
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [editor, onSave]);

  if (!editor) return null;

  return (
    <div className="markdown-editor">
      <div className="editor-toolbar">
        <Space>
          <Tooltip title="加粗 (Ctrl+B)">
            <Button
              icon={<BoldOutlined />}
              onClick={() => editor.chain().focus().toggleBold().run()}
              type={editor.isActive('bold') ? 'primary' : 'default'}
              size="small"
            />
          </Tooltip>
          <Tooltip title="斜体 (Ctrl+I)">
            <Button
              icon={<ItalicOutlined />}
              onClick={() => editor.chain().focus().toggleItalic().run()}
              type={editor.isActive('italic') ? 'primary' : 'default'}
              size="small"
            />
          </Tooltip>
          <Tooltip title="标题">
            <Button
              onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
              type={editor.isActive('heading', { level: 2 }) ? 'primary' : 'default'}
              size="small"
            >
              H2
            </Button>
          </Tooltip>
          <Tooltip title="无序列表">
            <Button
              icon={<UnorderedListOutlined />}
              onClick={() => editor.chain().focus().toggleBulletList().run()}
              type={editor.isActive('bulletList') ? 'primary' : 'default'}
              size="small"
            />
          </Tooltip>
          <Tooltip title="有序列表">
            <Button
              icon={<OrderedListOutlined />}
              onClick={() => editor.chain().focus().toggleOrderedList().run()}
              type={editor.isActive('orderedList') ? 'primary' : 'default'}
              size="small"
            />
          </Tooltip>
          <Tooltip title="代码块">
            <Button
              icon={<CodeOutlined />}
              onClick={() => editor.chain().focus().toggleCodeBlock().run()}
              type={editor.isActive('codeBlock') ? 'primary' : 'default'}
              size="small"
            />
          </Tooltip>
          <Tooltip title="链接">
            <Button
              icon={<LinkOutlined />}
              onClick={() => {
                const url = window.prompt('输入链接地址：');
                if (url) {
                  editor.chain().focus().setLink({ href: url }).run();
                }
              }}
              size="small"
            />
          </Tooltip>
        </Space>
      </div>
      <EditorContent editor={editor} className="editor-content" />
      {tags.length > 0 && onTagAdd && (
        <TagToolbar editor={editor} tags={tags} onTagAdd={onTagAdd} />
      )}
    </div>
  );
};
