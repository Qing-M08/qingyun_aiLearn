from pydantic import BaseModel, Field


class ToolParameter(BaseModel):
    """工具参数定义"""
    type: str = "string"                    # string / integer / number / boolean / array / object
    description: str
    required: bool = True
    default: str | int | float | bool | None = None
    enum: list[str] | None = None           # 参数枚举值（可选）


class ToolSchema(BaseModel):
    """工具 Schema 定义 — 注册到 ToolRegistry 时使用"""
    name: str                               # 工具唯一标识，如 "search_knowledge"
    display_name: str = ""                  # 工具显示名称，如 "搜索知识图谱"
    description: str                        # AI 可读的功能描述
    parameters: dict[str, ToolParameter]
    category: str = "read"                  # "read" | "write" — 控制权限和限流
    module: str = ""                        # 来源服务模块名
    icon: str = "search"                    # 图标名称（对应 Ant Design icon）


class ToolResult(BaseModel):
    """工具执行结果"""
    success: bool
    data: str | None = None                 # AI 友好的文本结果
    error_message: str | None = None
    token_count: int = 0                    # 工具调用消耗的 token 数（用于预算控制）
