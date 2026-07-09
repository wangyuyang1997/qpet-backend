"""副本系统 schema (v4.4)"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class DungeonConfig(BaseModel):
    dungeon_type: str  # bronze/silver/gold/platinum/diamond/master/legend/abyss
    difficulty: str = "normal"  # normal/adventure/hero/king/abyss
    enabled: bool = True


class DungeonStrategy(BaseModel):
    id: Optional[int] = None
    name: str = Field(..., min_length=1, max_length=64)
    dungeon_type: str
    difficulty: str = "normal"
    use_revive: bool = False
    target_floor: int = 0  # 0=全部
    auto_repeat: bool = False


class DungeonTemplate(BaseModel):
    id: Optional[int] = None
    name: str = Field(..., min_length=1, max_length=64)
    strategies: list[DungeonStrategy] = []


class DungeonHistory(BaseModel):
    id: int
    account_id: str
    dungeon_type: str
    difficulty: str
    floors_cleared: int = 0
    exp_gained: int = 0
    items_dropped: list[dict] = []
    created_at: datetime


class DungeonStatus(BaseModel):
    dungeons: list[dict] = []
    daily_entries_used: dict = {}   # {dungeon_type: count}
    daily_entries_max: dict = {}    # {dungeon_type: max}
