"""账号管理相关 schema"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class AddAccountRequest(BaseModel):
    token: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None


class AccountCredentialsRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class AccountSummary(BaseModel):
    """GET /api/accounts 每项摘要"""
    id: str
    name: str
    level: int
    class_name: str = ""
    running: bool = False
    user_id: int = 0
    has_credentials: bool = False
    is_premium: bool = False
    premium_expires_at: Optional[datetime] = None
    stats: dict = {}
    farm_stats: dict = {}
    daily_limits: dict = {}
    daily_tasks: list = []
    collection: list = []
    collection_summary: Optional[dict] = None
    marriage_info: Optional[dict] = None
    marriage_partner: Optional[str] = None
    current_exp: int = 0
    today_exp_gained: int = 0


class CharacterDetail(BaseModel):
    """GET /api/accounts/:id/character"""
    nickname: str = ""
    level: int = 0
    class_name: str = ""
    combat_power: int = 0
    pvp_stats: dict = {}
    pve_stats: dict = {}
    skills: list[dict] = []
    weapons: list[dict] = []
    equipment: list[dict] = []
    set_bonuses: list[dict] = []
    class_info: Optional[dict] = None
    equipped_title: Optional[dict] = None


class FarmDetail(BaseModel):
    """GET /api/accounts/:id/farm"""
    unlocked_slots: int = 0
    slots: list[dict] = []
    is_premium: bool = False
    vip_slot_index: int = -1
    collection: list[dict] = []
    crop_config: list[dict] = []
    daily_tasks: list[dict] = []
    today_harvest_exp: int = 0
    experience: int = 0
    level: int = 0


class SSOData(BaseModel):
    """GET /api/accounts/:id/sso-data"""
    token: str
    jwk: dict


class MarriageInfo(BaseModel):
    """POST /api/accounts/:id/refresh-marriage"""
    married: bool = False
    partner: Optional[str] = None
    partner_user_id: Optional[int] = None
    intimacy: int = 0
    today_gift_sent: int = 0
    today_boss_done: bool = False
