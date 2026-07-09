"""Dashboard: 日志/统计/配置/SSE/状态"""
from pydantic import BaseModel, Field, field_validator


class LogEntry(BaseModel):
    id: int
    timestamp: str  # "MM-DD HH:MM"
    level: str = "info"
    category: str = ""  # 农场 | 乐斗 | 系统
    module: str = ""
    message: str = ""
    account: str = ""


class LogsResponse(BaseModel):
    logs: list[LogEntry]
    total: int


class LogStatsResponse(BaseModel):
    today: dict = {}
    history: dict = {}


class ConfigUpdateRequest(BaseModel):
    account_id: str = Field(..., min_length=1)
    key: str = Field(..., min_length=1)
    value: bool | str

    @field_validator("value")
    @classmethod
    def check_value_type(cls, v):
        if not isinstance(v, (bool, str)):
            raise ValueError("value must be bool or str")
        return v


class AutomationConfig(BaseModel):
    """22 个功能开关 + 4 个数值参数"""
    friends: bool = True
    npc_fight: bool = True
    tower: bool = True
    gang_boss: bool = True
    class_upgrade: bool = True
    upgrade: bool = True
    chest: bool = True
    checkin: bool = True
    friend_sync: bool = True
    farm: bool = True
    auto_steal: bool = True
    auto_help_friends: bool = True
    marriage_boss: bool = True
    marriage_gift: bool = True
    use_flowers: bool = True
    ad_stamina: bool = True
    farm_ad: bool = True
    community_ad: bool = True
    auto_shop: bool = False
    marriage_partner: str = ""
    fight_interval_ms: int = 3000
    farm_interval_ms: int = 30000
    max_steal_per_cycle: int = 2
    max_help_per_cycle: int = 3


class StatusResponse(BaseModel):
    uptime: str = ""
    memory_mb: float = 0.0
    accounts_total: int = 0
    accounts_running: int = 0
    version: str = ""


class VersionResponse(BaseModel):
    version: str  # v5.0-YYYYMMDDHHmm
