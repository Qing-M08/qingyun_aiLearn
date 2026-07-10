// utils/markdown.ts

/**
 * 清除Markdown中不完整的语法标记（流式输出时使用）
 */
export const sanitizeMarkdown = (text: string): string => {
  let sanitized = text.replace(/\$([^$]*)$/, '$1');
  sanitized = sanitized.replace(/[*_]([^*_]*)$/, '$1');
  sanitized = sanitized.replace(/#+\s*$/, '');
  return sanitized;
};

/**
 * 从Markdown内容中提取标题
 */
export const extractHeadings = (content: string): Array<{ id: string; title: string; level: number }> => {
  return content
    .split('\n')
    .filter((line) => /^#{1,3}\s/.test(line))
    .map((line, index) => ({
      id: `heading-${index}`,
      title: line.replace(/^#+\s/, ''),
      level: line.match(/^#+/)?.[0].length || 1,
    }));
};
