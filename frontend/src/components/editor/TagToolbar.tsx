// components/editor/TagToolbar.tsx

import React, { useState, useEffect } from 'react';
import type { Editor } from '@tiptap/react';
import { Popover, Tag, Input, Button, List } from 'antd';
import { PlusOutlined, TagOutlined } from '@ant-design/icons';
import type { Tag as TagType } from '../../types/note';

interface TagToolbarProps {
  editor: Editor;
  tags: TagType[];
  onTagAdd: (tagId: string, contentText: string, startOffset?: number, endOffset?: number) => void;
}

export const TagToolbar: React.FC<TagToolbarProps> = ({ editor, tags, onTagAdd }) => {
  const [visible, setVisible] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [selectedText, setSelectedText] = useState('');
  const [position, setPosition] = useState({ top: 0, left: 0 });

  useEffect(() => {
    const handleSelectionUpdate = () => {
      const { from, to, empty } = editor.state.selection;
      if (!empty) {
        const text = editor.state.doc.textBetween(from, to, ' ');
        setSelectedText(text);
        const coords = editor.view.coordsAtPos(from);
        setPosition({ top: coords.top, left: coords.left });
        setVisible(true);
      } else {
        setVisible(false);
      }
    };

    editor.on('selectionUpdate', handleSelectionUpdate);
    return () => {
      editor.off('selectionUpdate', handleSelectionUpdate);
    };
  }, [editor]);

  const filteredTags = tags.filter((tag) =>
    tag.name.toLowerCase().includes(searchText.toLowerCase())
  );

  const handleTagClick = (tag: TagType) => {
    onTagAdd(tag.id, selectedText);
    setVisible(false);
    setSearchText('');
  };

  return (
    <Popover
      content={
        <div className="tag-popover-content">
          <Input
            placeholder="搜索标签..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
          />
          <List
            size="small"
            dataSource={filteredTags}
            renderItem={(tag) => (
              <List.Item
                className="tag-popover-item"
                onClick={() => handleTagClick(tag)}
              >
                <Tag color={tag.color || 'default'}>{tag.name}</Tag>
                {tag.description && (
                  <span className="tag-popover-desc">
                    {tag.description}
                  </span>
                )}
              </List.Item>
            )}
            locale={{ emptyText: '暂无标签' }}
          />
          <Button
            type="dashed"
            icon={<PlusOutlined />}
            block
            onClick={() => {
              // TD-1-002: 标签创建对话框未实现
              console.log('创建新标签:', searchText);
            }}
          >
            创建标签 &quot;{searchText}&quot;
          </Button>
        </div>
      }
      trigger="click"
      open={visible}
      onOpenChange={setVisible}
    >
      <Button
        icon={<TagOutlined />}
        size="small"
        style={{
          position: 'absolute',
          top: position.top - 40,
          left: position.left,
          zIndex: 1000,
        }}
      >
        添加标签
      </Button>
    </Popover>
  );
};
