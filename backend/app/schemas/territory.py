"""地盘系统 schema (v4.4)"""
from pydantic import BaseModel
from typing import Optional


class TerritoryZone(BaseModel):
    id: str
    name: str
    level_required: int = 1
    stamina_cost: int = 8
    occupier: Optional[str] = None
    occupier_level: Optional[int] = None
    slots_used: int = 0
    slots_max: int = 20
    hourly_exp: int = 0
    hourly_gang_contrib: int = 0


class TerritoryStatus(BaseModel):
    zones: list[TerritoryZone] = []
    my_zone: Optional[str] = None
    daily_attacks_used: int = 0
    daily_attacks_max: int = 10
    battle_log: list[dict] = []
