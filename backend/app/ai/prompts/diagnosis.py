DIAGNOSIS_PROMPT = """你是一位评估专家。请根据以下讲义内容和学生情况，生成诊断性问题。

## 讲义内容摘要：{lecture_summary}
## 知识点：{node_name}
## 学生当前掌握度：{mastery_score}

## 要求
生成3-5个诊断性问题，用于评估学生对本知识点的理解程度。

输出JSON格式：
{{
    "questions": [
        {{
            "type": "choice|short_answer",
            "question": "问题内容",
            "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
            "correct_answer": "正确答案",
            "explanation": "解析",
            "target_concept": "考查的具体概念",
            "difficulty": 1-5
        }}
    ]
}}

## 注意
- 问题应覆盖不同认知层次（记忆、理解、应用、分析）
- 针对学生掌握度较低的概念出更多基础题
- 选择题要有干扰性强的干扰项
"""
