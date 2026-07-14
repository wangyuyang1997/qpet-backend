"""配置相关 schema"""
from pydantic import BaseModel


class ConfigDefinitionOut(BaseModel):
    key: str
    value_type: str
    default_value: str
    description: str = ""
    category: str = "general"


class AccountConfigOut(BaseModel):
    key: str
    value: str
    value_type: str
    default_value: str
    description: str = ""


class ConfigUpdateRequest(BaseModel):
    account_id: str
    key: str
    value: str
