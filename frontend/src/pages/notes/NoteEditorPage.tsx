// pages/notes/NoteEditorPage.tsx

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { message, Alert } from 'antd';
import { SaveOutlined, ArrowLeftOutlined, CloudOutlined, CloudSyncOutlined, WifiOutlined } from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { notesAPI, tagsAPI } from '../../api/notes';
import { learningAPI } from '../../api/learning';
import { MarkdownEditor } from '../../components/editor/MarkdownEditor';
import { MarkdownPreview } from '../../components/editor/MarkdownPreview';
import { ChatPanel } from '../../components/chat/ChatPanel';
import type { Note } from '../../types/note';

const LS_KEY_PREFIX = 'qingyun_note_';

/* ===== localStorage 离线持久化 ===== */
function loadFromLocal(noteId: string): { title: string; content: string } | null {
  try {
    const raw = localStorage.getItem(LS_KEY_PREFIX + noteId);
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

function saveToLocal(noteId: string, title: string, content: string) {
  try {
    localStorage.setItem(LS_KEY_PREFIX + noteId, JSON.stringify({ title, content, updatedAt: Date.now() }));
  } catch { /* 存储满时静默失败 */ }
}

function removeFromLocal(noteId: string) {
  localStorage.removeItem(LS_KEY_PREFIX + noteId);
}

/* ===== 组件 ===== */
export const NoteEditorPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [mode, setMode] = useState<'edit' | 'preview' | 'wysiwyg'>('wysiwyg');
  const [syncStatus, setSyncStatus] = useState<'saved' | 'local' | 'unsaved'>('saved');
  const [isOnline, setIsOnline] = useState(true);
  const autoSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ---------- API：加载笔记 ----------
  const { data: note, isLoading, isError } = useQuery({
    queryKey: ['note', id],
    queryFn: () => notesAPI.get(id!).then((res) => {
      // 兼容两种后端响应格式：裸Note 或 ApiResponse<Note> 包装
      const body: any = res.data;
      return body?.data?.id ? body.data : body;
    }),
    enabled: !!id && id !== 'new',
    retry: 1,
    staleTime: 30000,
  });

  const { data: tags = [] } = useQuery({
    queryKey: ['tags'],
    queryFn: () => tagsAPI.list().then((res) => {
      // 兼容两种后端响应格式：ApiResponse<Tag[]> 包装 或 直接数组
      const body: any = res.data;
      if (Array.isArray(body)) return body;
      return body?.data ?? [];
    }),
    retry: 1,
    staleTime: 60000,
  });

  // ---------- API：保存/更新 ----------
  const createMutation = useMutation({
    mutationFn: (data: Partial<Note>) => notesAPI.create(data),
    onSuccess: (res) => {
      navigate(`/notes/${res.data.id}`, { replace: true });
      removeFromLocal('new');
      setSyncStatus('saved');
      message.success('笔记已创建并同步到服务器');
    },
    onError: () => {
      saveToLocal('new', title, content);
      setSyncStatus('local');
      message.info('离线模式：笔记已保存到本地');
    },
  });

  const updateMutation = useMutation({
    mutationFn: (data: Partial<Note>) => notesAPI.update(id!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['note', id] });
      queryClient.invalidateQueries({ queryKey: ['notes'] });
      if (id && id !== 'new') removeFromLocal(id);
      setSyncStatus('saved');
    },
    onError: () => {
      if (id && id !== 'new') saveToLocal(id, title, content);
      setSyncStatus('local');
    },
  });

  // ---------- 初始化内容 ----------
  useEffect(() => {
    if (id === 'new') {
      const local = loadFromLocal('new');
      if (local) {
        setTitle(local.title);
        setContent(local.content);
        setSyncStatus('local');
      } else {
        setTitle('无标题笔记');
        setContent('');
      }
      return;
    }

    if (note) {
      setTitle(note.title);
      setContent(note.content);
      setSyncStatus('saved');
    } else if (isError && id) {
      // API 失败，尝试从 localStorage 恢复
      const local = loadFromLocal(id);
      if (local) {
        setTitle(local.title);
        setContent(local.content);
        setSyncStatus('local');
      } else {
        // 没有本地缓存，用默认内容
        setTitle('无标题笔记');
        setContent('');
        setSyncStatus('unsaved');
      }
    }
  }, [note, isError, id]);

  // ---------- 自动保存到 localStorage ----------
  const autoSaveToLocal = useCallback(() => {
    if (syncStatus === 'saved') return; // 已同步到服务器，跳过
    const noteId = (id && id !== 'new') ? id : 'new';
    if (title || content) {
      saveToLocal(noteId, title, content);
      if (syncStatus === 'unsaved') setSyncStatus('local');
    }
  }, [id, title, content, syncStatus]);

  // 内容变化时触发延时自动保存
  const handleTitleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setTitle(e.target.value);
    if (syncStatus === 'saved') setSyncStatus('unsaved');
  };

  const handleContentChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setContent(e.target.value);
    if (syncStatus === 'saved') setSyncStatus('unsaved');
  };

  const handleMarkdownChange = useCallback((markdown: string, _json: object) => {
    setContent(markdown);
    if (syncStatus === 'saved') setSyncStatus('unsaved');
  }, [syncStatus]);

  // 延时本地保存（2秒防抖）
  useEffect(() => {
    if (syncStatus === 'saved') return;
    if (autoSaveTimer.current) clearTimeout(autoSaveTimer.current);
    autoSaveTimer.current = setTimeout(autoSaveToLocal, 2000);
    return () => {
      if (autoSaveTimer.current) clearTimeout(autoSaveTimer.current);
    };
  }, [autoSaveToLocal, syncStatus]);

  // ---------- 手动保存 ----------
  const handleSave = useCallback(() => {
    if (id === 'new') {
      createMutation.mutate({ title, content });
    } else if (id) {
      updateMutation.mutate({ title, content });
    }
    // 同时保存到本地
    const noteId = (id && id !== 'new') ? id : 'new';
    saveToLocal(noteId, title, content);
  }, [id, title, content, createMutation, updateMutation]);

  // Ctrl+S
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        handleSave();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleSave]);

  // ---------- 网络状态监听 ----------
  useEffect(() => {
    const goOnline = () => setIsOnline(true);
    const goOffline = () => { setIsOnline(false); setSyncStatus('local'); };
    window.addEventListener('online', goOnline);
    window.addEventListener('offline', goOffline);
    return () => {
      window.removeEventListener('online', goOnline);
      window.removeEventListener('offline', goOffline);
    };
  }, []);

  // ---------- 同步状态图标 ----------
  const SyncIcon = () => {
    if (!isOnline) return <WifiOutlined style={{ color: '#EF4444' }} />;
    switch (syncStatus) {
      case 'saved': return <CloudOutlined style={{ color: '#10B981' }} />;
      case 'local': return <CloudSyncOutlined style={{ color: '#F59E0B' }} />;
      case 'unsaved': return <span style={{ color: '#9CA3AF', fontSize: 11 }}>未保存</span>;
    }
  };

  // ======================== AI 问答会话 ========================
  const [qaSessionId, setQaSessionId] = useState<string | null>(null);
  const [qaSessionError, setQaSessionError] = useState(false);

  // 为当前笔记创建 QA 会话（用于 AI 问答面板）
  const createQASession = useCallback(async () => {
    if (!id || id === 'new' || !note) return;
    setQaSessionId(null);
    setQaSessionError(false);
    try {
      const res = await learningAPI.createQASession({ topic: note.title || '笔记问答' });
      const body: any = res.data;
      const session = body?.data?.id ? body.data : body;
      if (session?.id) {
        setQaSessionId(session.id);
        setQaSessionError(false);
      } else {
        console.error('[AI问答] 创建会话失败：响应中缺少 id', res.data);
        setQaSessionError(true);
      }
    } catch (err: any) {
      console.error('[AI问答] 创建会话失败：', err?.message || err);
      setQaSessionError(true);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, note?.id]);

  // note 加载完成后自动创建 QA 会话（仅当未初始化且无错误时）
  const sessionInitialized = useRef(false);
  useEffect(() => {
    if (!id || id === 'new' || !note) return;
    if (sessionInitialized.current && qaSessionId) return;
    sessionInitialized.current = true;
    createQASession();
  }, [id, note?.id, createQASession, qaSessionId]);

  // ======================== 渲染 ========================
  if (isLoading) {
    return <div className="page-loading" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 400 }}>
      <span style={{ color: 'var(--color-text-secondary)' }}>加载中...</span>
    </div>;
  }

  return (
    <div className="editor-full">
      {/* Menubar */}
      <div className="editor-menubar">
        <button className="editor-back-btn" onClick={() => navigate('/notes')}>
          <ArrowLeftOutlined />
        </button>
        <input
          className="editor-title-input"
          value={title}
          onChange={handleTitleChange}
          placeholder="笔记标题"
        />
        <SyncIcon />
        <div className="editor-mode-switch">
          <button className={`editor-mode-btn${mode === 'wysiwyg' ? ' active' : ''}`} onClick={() => setMode('wysiwyg')}>所见即所得</button>
          <button className={`editor-mode-btn${mode === 'edit' ? ' active' : ''}`} onClick={() => setMode('edit')}>源码</button>
          <button className={`editor-mode-btn${mode === 'preview' ? ' active' : ''}`} onClick={() => setMode('preview')}>预览</button>
        </div>
        <button
          className="btn btn-primary"
          style={{ fontSize: 12, height: 28, padding: '0 14px' }}
          onClick={handleSave}
          disabled={createMutation.isPending || updateMutation.isPending}
        >
          <SaveOutlined /> {createMutation.isPending || updateMutation.isPending ? '保存中...' : '保存'}
        </button>
      </div>

      {/* 离线提示 */}
      {syncStatus === 'local' && (
        <Alert
          message="本地存储"
          description="内容已保存到本地浏览器。连接网络后点击「保存」按钮即可同步到服务器。"
          type="warning"
          showIcon
          style={{ borderRadius: 0, borderLeft: 'none', borderRight: 'none' }}
        />
      )}

      {/* Split Pane */}
      <div className="editor-split-pane">
        {/* Left: AI Q&A Panel */}
        <div className="editor-ai-panel">
          <div className="editor-context-bar">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>
            <span>AI 问答</span>
          </div>
          {qaSessionId ? (
            <ChatPanel
              sessionId={qaSessionId}
              contextInfo={{ lectureTitle: title }}
            />
          ) : qaSessionError ? (
            <div className="editor-chat-messages" style={{ justifyContent: 'center', alignItems: 'center', gap: 12 }}>
              <span style={{ color: 'var(--color-text-secondary)', fontSize: 13 }}>
                AI 助手初始化失败，请检查网络或后端服务
              </span>
              <button
                className="btn btn-primary"
                style={{ fontSize: 12, height: 28, padding: '0 14px' }}
                onClick={createQASession}
              >
                重试
              </button>
            </div>
          ) : (
            <div className="editor-chat-messages" style={{ justifyContent: 'center', alignItems: 'center' }}>
              <span style={{ color: 'var(--color-text-secondary)', fontSize: 13 }}>
                {id === 'new' ? '保存笔记后即可使用 AI 问答' : '正在初始化 AI 助手...'}
              </span>
            </div>
          )}
        </div>

        {/* Divider */}
        <div className="editor-divider" />

        {/* Right: Editor */}
        <div className="editor-main">
          <div className="editor-tag-bar">
            <button className="editor-tag-add">+ 标签</button>
          </div>
          <div className="editor-writing-area">
            {mode === 'wysiwyg' && (
              <MarkdownEditor
                content={content}
                onChange={handleMarkdownChange}
                onSave={handleSave}
                editable={true}
              />
            )}
            {mode === 'edit' && (
              <textarea
                className="editor-content-area"
                value={content}
                onChange={handleContentChange}
                placeholder="开始写作..."
                style={{ width: '100%', border: 'none', resize: 'none', background: 'transparent' }}
              />
            )}
            {mode === 'preview' && (
              <MarkdownPreview content={content} />
            )}
          </div>

          {/* Status Bar */}
          <div className="editor-statusbar">
            <span>字数：{(content ?? '').length}</span>
            <span className="editor-statusbar-dot" />
            <span>
              {syncStatus === 'saved' ? '✅ 已同步' : syncStatus === 'local' ? '💾 本地存储' : '○ 未保存'}
              {' · '}{new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
            </span>
            <span className="editor-statusbar-dot" />
          </div>
        </div>
      </div>
    </div>
  );
};
