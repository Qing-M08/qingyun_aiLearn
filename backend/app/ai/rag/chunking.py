from dataclasses import dataclass


@dataclass
class Chunk:
    text: str
    metadata: dict | None = None


class SmartChunker:

    @staticmethod
    def chunk_by_paragraphs(
        text: str,
        target_size: int = 400,
        overlap: int = 50,
    ) -> list[Chunk]:
        """按段落边界分块，合并过短段落，拆分过长段落"""
        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # 粗略估算：中文1字≈1token，英文4字符≈1token
            char_limit = target_size * 3

            if len(current_chunk) + len(para) > char_limit:
                if current_chunk:
                    chunks.append(Chunk(text=current_chunk.strip()))
                # 保留overlap
                if overlap > 0 and current_chunk:
                    overlap_text = current_chunk[-(overlap * 3):]
                    current_chunk = overlap_text + "\n\n" + para
                else:
                    current_chunk = para
            else:
                current_chunk += "\n\n" + para if current_chunk else para

        if current_chunk.strip():
            chunks.append(Chunk(text=current_chunk.strip()))

        return chunks
