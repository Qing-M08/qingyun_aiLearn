// types/note.ts

export interface Note {
  id: string;
  user_id: string;
  title: string;
  content: string;
  content_json: object | null;
  subject: string | null;
  route_id: string | null;
  node_id: string | null;
  parent_id: string | null;
  is_template: boolean;
  word_count: number;
  tags: NoteTag[];
  created_at: string;
  updated_at: string;
}

export interface NoteTag {
  id: string;
  note_id: string;
  tag_id: string;
  content_text: string | null;
  start_offset: number | null;
  end_offset: number | null;
  context: string | null;
  tag: Tag;
  created_at: string;
}

export interface Tag {
  id: string;
  user_id: string | null;
  name: string;
  color: string | null;
  is_system: boolean;
  description: string | null;
  created_at: string;
}

export interface TagSelection {
  tag_id: string;
  content_text: string;
  start_offset?: number;
  end_offset?: number;
  context?: string;
}

export interface BatchDeleteNotesRequest {
  ids: string[];
}

export interface BatchDeleteNotesResponse {
  deleted_count: number;
  failed_ids: string[];
}
