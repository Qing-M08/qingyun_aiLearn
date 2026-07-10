import re


def estimate_tokens(text: str) -> int:
    """粗略估算token数（中文约1.5字/token，英文约4字符/token）"""
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    other_chars = len(text) - chinese_chars
    return int(chinese_chars / 1.5 + other_chars / 4)


def truncate_text(text: str, max_length: int = 200) -> str:
    """截断文本到指定长度"""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def calculate_word_count(text: str) -> int:
    """计算文本字数（中文按字计，英文按词计）"""
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    english_words = len(re.findall(r"[a-zA-Z]+", text))
    return chinese_chars + english_words
