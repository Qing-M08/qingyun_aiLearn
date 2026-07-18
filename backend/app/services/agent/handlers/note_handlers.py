import uuid

from app.database import async_session_factory
from app.services.agent.tool_schemas import ToolResult
from app.services.note_service import NoteService

import structlog

logger = structlog.get_logger()


async def _tool_search_notes(user_id: str, query: str, tag: str | None = None, limit: int = 5) -> str:
    """搜索笔记工具 handler — 优先 Meilisearch 索引，回退 PostgreSQL"""
    results = []

    # 1. 优先使用 Meilisearch 索引搜索
    try:
        from app.services.search_service import get_meilisearch_client
        client = get_meilisearch_client()
        ms_result = client.index("notes").search(query, {
            "filter": [f"user_id = {user_id}"],
            "limit": limit,
        })
        for hit in ms_result.get("hits", []):
            results.append({
                "title": hit.get("title", ""),
                "content": (hit.get("content", "") or "")[:150].replace("\n", " "),
            })
    except Exception:
        pass

    # 2. Meilisearch 无结果则回退 PostgreSQL
    if not results:
        async with async_session_factory() as db:
            service = NoteService()
            notes, _ = await service.search_notes(
                db, user_id=uuid.UUID(user_id), query=query, page=1, page_size=limit
            )
            for n in notes:
                tags_list = [t.name for t in n.tags] if hasattr(n, "tags") and n.tags else []
                tags_str = ", ".join(tags_list) if tags_list else "无标签"
                preview = (n.content or "")[:150].replace("\n", " ")
                results.append({
                    "title": n.title,
                    "content": preview,
                    "tags_str": tags_str,
                })

    if not results:
        return "未找到相关笔记。"

    lines = []
    for r in results:
        tags_str = r.get("tags_str", "无标签")
        lines.append(f"📝 {r['title']}\n  标签: {tags_str}\n  摘要: {r['content']}...")
    return "\n\n".join(lines)


async def _tool_get_note_content(user_id: str, note_id: str) -> str:
    """获取笔记内容工具 handler"""
    async with async_session_factory() as db:
        service = NoteService()
        try:
            note = await service.get_note(db, uuid.UUID(note_id), uuid.UUID(user_id))
            total_lines = len((note.content or "").split("\n"))
            tags_list = [t.tag.name for t in note.tags if t.tag] if hasattr(note, "tags") and note.tags else []
            return (
                f"标题：{note.title}\n"
                f"学科：{note.subject or '未分类'}\n"
                f"标签：{', '.join(tags_list) if tags_list else '无'}\n"
                f"字数：{note.word_count}\n"
                f"总行数：{total_lines}\n"
                f"---\n{note.content}"
            )
        except Exception:
            return "笔记不存在或无权访问。"


async def _tool_edit_note(
    user_id: str,
    note_id: str,
    operation: str,
    start_line: int,
    end_line: int | None = None,
    start_column: int | None = None,
    end_column: int | None = None,
    content: str = "",
) -> ToolResult:
    """编辑笔记 — 支持行级和列级精度的局部编辑（Sprint 10 增强）

    操作类型:
    - insert: 在 start_line 行之前插入 content（行级），或在 start_line 行的 start_column 位置前插入（列级）
    - replace: 替换 start_line 到 end_line（含）的内容为 content（行级），或替换指定列范围（列级）
    - delete: 删除 start_line 到 end_line（含）的内容（行级），或删除指定列范围（列级）

    行号规则:
    - 1-based（第一行 = 1）
    - insert 时 end_line 忽略
    - start_line 超出范围时: insert 追加到末尾，replace/delete 返回错误

    列号规则（start_column / end_column 为可选参数，不传时行为与行级编辑完全一致）:
    - 0-based（第一个字符 = 0）
    - insert: 在 start_column 位置前插入，超出行长度则追加到行尾
    - replace/delete: 替换/删除从 start_column 到 end_column（含）的文本
    """
    if operation not in ("insert", "replace", "delete"):
        return ToolResult(success=False, error_message=f"无效操作: {operation}，可选: insert, replace, delete")

    if operation in ("replace", "delete") and end_line is None and end_column is None:
        return ToolResult(success=False, error_message=f"操作 {operation} 需要提供 end_line 或 end_column 参数")

    if start_line < 1:
        return ToolResult(success=False, error_message=f"start_line 必须 >= 1，当前值: {start_line}")

    try:
        note_uuid = uuid.UUID(note_id)
    except ValueError:
        return ToolResult(success=False, error_message=f"无效的笔记 ID: {note_id}")

    from app.core.utils import calculate_word_count

    async with async_session_factory() as db:
        service = NoteService()
        try:
            note = await service.get_note(db, note_uuid, uuid.UUID(user_id))
        except Exception:
            return ToolResult(success=False, error_message=f"笔记不存在或无权访问: {note_id}")

        original_content = note.content or ""
        lines = original_content.split("\n") if original_content else [""]
        total_lines = len(lines)

        # 判断是列级模式还是行级模式
        is_column_mode = start_column is not None

        if is_column_mode:
            # ===== 列级模式（Sprint 10 新增） =====
            # 边界处理
            col_start = max(0, start_column)
            col_end = end_column

            if operation == "insert":
                # 定位到 start_line 行
                if start_line > total_lines:
                    # 超出范围，追加到最后一行行尾
                    line_idx = total_lines - 1
                else:
                    line_idx = start_line - 1

                line = lines[line_idx]
                # 如果 col_start 超出行长度，追加到行尾
                insert_pos = min(col_start, len(line))
                lines[line_idx] = line[:insert_pos] + content + line[insert_pos:]

            elif operation == "replace":
                if start_line > total_lines:
                    return ToolResult(success=False, error_message=f"start_line ({start_line}) 超出范围（共 {total_lines} 行）")

                if start_line == end_line or end_line is None:
                    # 同一行内替换
                    line_idx = start_line - 1
                    line = lines[line_idx]
                    c_start = min(col_start, len(line))
                    c_end = min(col_end + 1, len(line)) if col_end is not None else len(line)
                    lines[line_idx] = line[:c_start] + content + line[c_end:]
                else:
                    # 跨多行替换
                    if end_line > total_lines:
                        return ToolResult(success=False, error_message=f"end_line ({end_line}) 超出范围（共 {total_lines} 行）")
                    start_line_text = lines[start_line - 1]
                    end_line_text = lines[end_line - 1]
                    prefix = start_line_text[:col_start]
                    suffix = end_line_text[col_end + 1:] if col_end is not None else ""
                    new_text = prefix + content + suffix
                    lines = lines[:start_line - 1] + [new_text] + lines[end_line:]

            elif operation == "delete":
                if start_line > total_lines:
                    return ToolResult(success=False, error_message=f"start_line ({start_line}) 超出范围（共 {total_lines} 行）")

                if start_line == end_line or end_line is None:
                    # 同一行内删除
                    line_idx = start_line - 1
                    line = lines[line_idx]
                    c_start = min(col_start, len(line))
                    c_end = min(col_end + 1, len(line)) if col_end is not None else len(line)
                    lines[line_idx] = line[:c_start] + line[c_end:]
                else:
                    # 跨多行删除
                    if end_line > total_lines:
                        return ToolResult(success=False, error_message=f"end_line ({end_line}) 超出范围（共 {total_lines} 行）")
                    start_line_text = lines[start_line - 1]
                    end_line_text = lines[end_line - 1]
                    prefix = start_line_text[:col_start]
                    suffix = end_line_text[col_end + 1:] if col_end is not None else ""
                    lines = lines[:start_line - 1] + [prefix + suffix] + lines[end_line:]

        else:
            # ===== 行级模式（向后兼容现有行为） =====
            if operation == "insert":
                insert_idx = min(start_line - 1, total_lines)
                new_lines = content.split("\n") if content else []
                lines = lines[:insert_idx] + new_lines + lines[insert_idx:]

            elif operation == "replace":
                if end_line is None or end_line < start_line:
                    return ToolResult(success=False, error_message=f"end_line 必须 >= start_line，当前: start={start_line}, end={end_line}")
                if start_line > total_lines:
                    return ToolResult(success=False, error_message=f"start_line ({start_line}) 超出范围（共 {total_lines} 行）")
                start_idx = start_line - 1
                end_idx = min(end_line, total_lines)
                new_lines = content.split("\n") if content else []
                lines = lines[:start_idx] + new_lines + lines[end_idx:]

            elif operation == "delete":
                if end_line is None or end_line < start_line:
                    return ToolResult(success=False, error_message=f"end_line 必须 >= start_line，当前: start={start_line}, end={end_line}")
                if start_line > total_lines:
                    return ToolResult(success=False, error_message=f"start_line ({start_line}) 超出范围（共 {total_lines} 行）")
                start_idx = start_line - 1
                end_idx = min(end_line, total_lines)
                lines = lines[:start_idx] + lines[end_idx:]

        new_content = "\n".join(lines)
        note.content = new_content
        note.word_count = calculate_word_count(new_content)
        await db.commit()
        await db.refresh(note)

        # 同步到 Meilisearch
        try:
            from app.services.note_service import _sync_note_to_meilisearch
            await _sync_note_to_meilisearch(note)
        except Exception as e:
            logger.warning("edit_note_meilisearch_sync_failed", note_id=str(note.id), error=str(e))

        # WebSocket 推送编辑通知
        try:
            from app.api.v1.websocket import manager
            client_id = f"user_{user_id}"
            await manager.send_json(client_id, {
                "type": "note_edit",
                "data": {
                    "note_id": str(note.id),
                    "operation": operation,
                    "start_line": start_line,
                    "end_line": end_line,
                    "start_column": start_column,
                    "end_column": end_column,
                    "content": content,
                    "new_content": new_content,
                    "title": note.title,
                    "word_count": note.word_count,
                },
            })
        except Exception as e:
            logger.warning("edit_note_ws_push_failed", error=str(e))

        mode_desc = "列级" if is_column_mode else "行级"
        if is_column_mode:
            operation_desc = {
                "insert": f"在第 {start_line} 行第 {start_column} 列前插入了内容",
                "replace": f"替换了第 {start_line} 行第 {start_column} 列到第 {end_line} 行第 {end_column} 列的内容",
                "delete": f"删除了第 {start_line} 行第 {start_column} 列到第 {end_line} 行第 {end_column} 列的内容",
            }
        else:
            operation_desc = {
                "insert": f"在第 {start_line} 行前插入了 {len(content.split(chr(10)))} 行",
                "replace": f"替换了第 {start_line}-{end_line} 行为 {len(content.split(chr(10)))} 行新内容",
                "delete": f"删除了第 {start_line}-{end_line} 行",
            }

        logger.info(
            "note_edited_by_agent",
            note_id=str(note.id),
            user_id=user_id,
            operation=operation,
            mode=mode_desc,
            start_line=start_line,
            end_line=end_line,
            start_column=start_column,
            end_column=end_column,
        )

        return ToolResult(
            success=True,
            data=f"笔记「{note.title}」修改成功（{mode_desc}）: {operation_desc[operation]}\n新总行数: {len(lines)}，新字数: {note.word_count}",
        )
