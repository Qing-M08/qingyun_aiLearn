ROUTE_GENERATION_PROMPT = """你是一位学习规划专家。请根据以下信息为学生生成学习路线。

## 学生信息
- 当前水平：{current_level}
- 已掌握的知识点：{known_nodes}
- 学习目标：{goal}
- 每周可用时间：{available_hours}小时

## 学习主题
{topic}

## 可用知识点（来自知识图谱）
{available_nodes_with_prerequisites}

## 输出要求
输出JSON格式：
{{
    "title": "路线标题",
    "description": "路线描述",
    "estimated_total_hours": 数字,
    "steps": [
        {{
            "order": 1,
            "node_id": "知识点ID（如有）",
            "title": "步骤标题",
            "description": "学习内容和目标",
            "estimated_minutes": 数字,
            "prerequisite_step_orders": [前置步骤序号]
        }}
    ]
}}

## 注意事项
- 步骤数量建议5-15个
- 确保前置依赖关系正确
- 时间分配要合理
- 从学生已知的内容出发，循序渐进
"""
