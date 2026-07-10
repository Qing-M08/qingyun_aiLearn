// pages/notes/NotesListPage.tsx

import React, { useState } from 'react';
import { Input, Select, message, Modal, Checkbox, Button, Popconfirm } from 'antd';
import {
  SearchOutlined,
  PlusOutlined,
  DeleteOutlined,
  SettingOutlined,
  CloseOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { notesAPI } from '../../api/notes';
import type { NoteListParams } from '../../api/notes';

export const NotesListPage: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchText, setSearchText] = useState('');
  const [subjectFilter, setSubjectFilter] = useState<string | undefined>();

  // 管理模式
  const [selectMode, setSelectMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [deleting, setDeleting] = useState(false);

  // API 查询 — 失败时静默回退到 mock
  const { data: apiData, isError } = useQuery({
    queryKey: ['notes', { search: searchText, subject: subjectFilter }],
    queryFn: () => notesAPI.list({
      page: 1,
      page_size: 50,
      search: searchText || undefined,
      subject: subjectFilter,
      sort_by: 'updated_at',
      sort_order: 'desc',
    }).then((res) => {
      // 兼容三种后端响应格式：裸数组、PaginatedResponse 或 ApiResponse 包装
      const body: any = res.data;
      if (Array.isArray(body)) return { items: body, total: body.length, page: 1, page_size: body.length };
      if (body?.items) return body;
      if (body?.data?.items) return body.data;
      return { items: [], total: 0, page: 1, page_size: 50 };
    }),
    retry: 1,        // 只重试1次，不阻塞UI
    staleTime: 10000,
  });

  const deleteMutation = useMutation({
    mutationFn: (noteId: string) => notesAPI.delete(noteId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notes'] });
      message.success('删除成功');
    },
    onError: () => message.info('离线模式：删除仅本地生效'),
  });

  // ========== 选择逻辑 ==========
  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === displayNotes.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(displayNotes.map((n: any) => n.id)));
    }
  };

  const exitSelectMode = () => {
    setSelectMode(false);
    setSelectedIds(new Set());
  };

  const enterSelectMode = () => {
    setSelectMode(true);
    setSelectedIds(new Set());
  };

  // ========== 删除逻辑 ==========
  const handleSingleDelete = (noteId: string) => {
    deleteMutation.mutate(noteId);
  };

  const handleBatchDelete = () => {
    if (selectedIds.size === 0 || deleting) return;

    const ids = Array.from(selectedIds);
    Modal.confirm({
      title: '确认删除',
      content: `确认删除 ${ids.length} 条笔记？删除后无法恢复。`,
      okText: '确认删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        setDeleting(true);
        try {
          const res = await notesAPI.batchDelete({ ids });
          const body: any = res.data;
          const result =
            body?.data && typeof body.data === 'object' && 'deleted_count' in body.data
              ? body.data
              : body;
          const deletedCount: number = result.deleted_count ?? 0;
          const failedIds: string[] = result.failed_ids ?? [];

          if (failedIds.length > 0 && deletedCount > 0) {
            message.warning(`${deletedCount} 条删除成功，${failedIds.length} 条无权限`);
          } else if (failedIds.length > 0) {
            message.error('删除失败，所选笔记均无权限或不存在');
          } else {
            message.success(`成功删除 ${deletedCount} 条笔记`);
          }

          queryClient.invalidateQueries({ queryKey: ['notes'] });
          exitSelectMode();
        } catch (err) {
          console.error('[NotesListPage] 批量删除失败:', err);
          message.error('批量删除失败，请重试');
        } finally {
          setDeleting(false);
        }
      },
    });
  };

  // 新建笔记 — 优先API，失败则进入离线编辑器
  const handleCreateNote = async () => {
    try {
      const res = await notesAPI.create({ title: '无标题笔记', content: '' });
      navigate(`/notes/${res.data.id}`);
    } catch {
      // 离线模式：直接进入编辑器
      navigate('/notes/new');
    }
  };

  const displayNotes = apiData?.items ?? [];

  const formatTime = (dateStr: string) => {
    const diff = Date.now() - new Date(dateStr).getTime();
    const hours = Math.floor(diff / 3600000);
    if (hours < 1) return '刚刚';
    if (hours < 24) return `${hours}小时前`;
    return `${Math.floor(hours / 24)}天前`;
  };

  return (
    <div style={{ maxWidth: 960, margin: '0 auto' }}>
      <div className="page-header">
        <div className="page-title">笔记</div>
        <div style={{ display: 'flex', gap: 8 }}>
          {!selectMode ? (
            <>
              <button
                className="btn btn-default"
                onClick={enterSelectMode}
                disabled={displayNotes.length === 0}
              >
                <SettingOutlined /> 管理模式
              </button>
              <button className="btn btn-primary" onClick={handleCreateNote}>
                <PlusOutlined /> 新建笔记
              </button>
            </>
          ) : (
            <button
              className="btn btn-default"
              onClick={exitSelectMode}
              disabled={deleting}
            >
              <CloseOutlined /> 取消
            </button>
          )}
        </div>
      </div>

      {/* ========== 管理模式工具栏 ========== */}
      {selectMode && (
        <div className="route-manage-bar">
          <Checkbox
            checked={selectedIds.size === displayNotes.length && displayNotes.length > 0}
            indeterminate={selectedIds.size > 0 && selectedIds.size < displayNotes.length}
            onChange={toggleSelectAll}
            disabled={deleting}
          >
            <span className="select-all-label">
              全选 ({selectedIds.size}/{displayNotes.length})
            </span>
          </Checkbox>
          <Button
            danger
            type="primary"
            icon={<DeleteOutlined />}
            onClick={handleBatchDelete}
            disabled={selectedIds.size === 0 || deleting}
            loading={deleting}
          >
            批量删除{selectedIds.size > 0 ? ` (${selectedIds.size})` : ''}
          </Button>
        </div>
      )}

      {isError && (
        <div style={{ marginBottom: 16, textAlign: 'center', color: 'var(--color-text-tertiary)', fontSize: 13 }}>
          加载笔记失败，请检查网络连接后刷新重试
        </div>
      )}

      <div className="toolbar">
        <Input
          placeholder="搜索笔记..."
          prefix={<SearchOutlined />}
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          onPressEnter={() => queryClient.invalidateQueries({ queryKey: ['notes'] })}
          style={{ width: 240, height: 32 }}
        />
        <Select
          placeholder="全部学科"
          allowClear
          style={{ width: 120 }}
          value={subjectFilter}
          onChange={(v) => setSubjectFilter(v)}
          options={[
            { label: '物理', value: '物理' },
            { label: '数学', value: '数学' },
            { label: '化学', value: '化学' },
          ]}
        />
      </div>

      {displayNotes.map((note: any) => {
        const isSelected = selectedIds.has(note.id);
        return (
          <div
            className={`note-card${isSelected ? ' selected' : ''}`}
            key={note.id}
            onClick={() => {
              if (selectMode) {
                toggleSelect(note.id);
              } else {
                navigate(`/notes/${note.id}`);
              }
            }}
          >
            {/* 管理模式复选框 */}
            {selectMode && (
              <div className="note-card-checkbox" onClick={(e) => e.stopPropagation()}>
                <Checkbox
                  checked={isSelected}
                  onChange={() => toggleSelect(note.id)}
                />
              </div>
            )}

            {/* 单条删除按钮（非管理模式悬浮显示） */}
            {!selectMode && (
              <div className="note-card-delete" onClick={(e) => e.stopPropagation()}>
                <Popconfirm
                  title="确认删除"
                  description="删除后无法恢复。"
                  onConfirm={() => handleSingleDelete(note.id)}
                  okText="确认删除"
                  cancelText="取消"
                  okType="danger"
                >
                  <Button
                    size="small"
                    danger
                    icon={<DeleteOutlined />}
                    type="text"
                  />
                </Popconfirm>
              </div>
            )}

            <div className="note-card-title">{note.title}</div>
            <div className="note-card-summary">
              {(note.content || '').replace(/[#*`]/g, '').substring(0, 120) || '暂无内容'}
            </div>
            <div className="note-card-footer">
              <div className="note-card-tags">
                {Array.isArray(note.tags) && note.tags.slice(0, 3).map((nt: any) => (
                  <span key={nt.tag_id} className={`tag ${nt.tag?.color === '#3B82F6' ? 'tag-blue' : nt.tag?.color === '#10B981' ? 'tag-success' : 'tag-primary'}`}>
                    {nt.tag?.name}
                  </span>
                ))}
              </div>
              <div className="note-card-time">{formatTime(note.updated_at)}</div>
            </div>
          </div>
        );
      })}

      <div className="pagination">
        <button className="page-btn active">1</button>
      </div>
    </div>
  );
};
