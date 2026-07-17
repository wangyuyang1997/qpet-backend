"""测试 FarmSync 写入 player_museum / player_collection / farm_land"""
import sys
sys.path.insert(0, ".")

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text
from app.config import settings
from app.services.farm.sync import FarmSync

TEST_ACCOUNT = "test_sync_001"

# Unicode escapes for Chinese status values to avoid encoding issues
JIAN  = "见"   # 见
BAN   = "半"   # 半
CHENG = "成"   # 成


@pytest.fixture
def sf():
    """每个测试独立的 session factory"""
    engine = create_async_engine(settings.database_url)
    f = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield f
    # 同步清理：用同步 engine 删测试数据
    from sqlalchemy import create_engine as sync_engine
    se = sync_engine(settings.database_url_sync)
    with se.connect() as c:
        for t in ["player_museum", "player_collection", "farm_land"]:
            c.execute(text(f"DELETE FROM {t} WHERE account_id='{TEST_ACCOUNT}'"))
        c.commit()
    se.dispose()


def farm_data_factory(land_from_slot=False, **overrides):
    """构造模拟的 GET /api/farm 返回数据。land_from_slot=True 模拟真实 API 的 slots[0].land 格式"""
    data = {
        "museum": {
            "items": [
                {"id": "rusty_sickle", "rarity": "normal", "fragmentCount": 2},
                {"id": "wooden_plow",  "rarity": "normal", "fragmentCount": 8},
                {"id": "saber_tooth",  "rarity": "rare",   "fragmentCount": 40},
                {"id": "earth_heart",  "rarity": "legend", "fragmentCount": 50},
            ],
        },
        # 真实 API 格式：flat list of {cropId, quality: "normal"/"fine"/"rare"}
        "collection": [
            {"cropId": "barley", "quality": "normal"},
            {"cropId": "carrot", "quality": "normal"},
            {"cropId": "carrot", "quality": "fine"},
            {"cropId": "corn",   "quality": "normal"},
            {"cropId": "corn",   "quality": "fine"},
            {"cropId": "corn",   "quality": "rare"},
        ],
        "slots": [],
    }

    if land_from_slot:
        # 真实 API 格式：土地数据在 slots[0].land
        data["slots"] = [{
            "slotIndex": 0,
            "land": {
                "level": 1, "name": "普通土地", "canUpgrade": False,
                "requirements": {
                    "research": {"current": 121, "required": 200, "met": False},
                    "collection": {"current": 0, "required": 4, "met": False},
                },
                "nextLevel": {
                    "level": 2, "name": "肥沃土地",
                    "researchCost": 200, "uniqueRequired": 4,
                    "growthReduction": 0.02, "harvestBonus": 0.02,
                },
            },
        }]
    else:
        # 简化格式（顶层 land）
        data["land"] = {
            "level": 1, "name": "普通土地",
            "researchPoints": 121, "canUpgrade": False,
            "next": {"level": 2, "name": "肥沃土地",
                     "rpNeeded": 200, "artifacts": 4,
                     "growthPct": -2, "harvestPct": 2},
        }

    for k, v in overrides.items():
        if isinstance(v, dict):
            data[k].update(v)
        else:
            data[k] = v
    return data


# ===================== museum =====================

@pytest.mark.asyncio
async def test_sync_museum_fragments(sf):
    sync = FarmSync(sf)
    await sync._sync_museum(TEST_ACCOUNT, farm_data_factory())

    async with sf() as s:
        rows = await s.execute(
            text("SELECT item_id, fragment_count, status, is_repaired "
                 "FROM player_museum WHERE account_id=:aid ORDER BY item_id"),
            {"aid": TEST_ACCOUNT},
        )
        rows = rows.fetchall()

    assert len(rows) == 4
    by_id = {r[0]: (r[1], r[2], r[3]) for r in rows}

    assert by_id["rusty_sickle"] == (2, JIAN, False)
    assert by_id["wooden_plow"] == (8, CHENG, True)
    assert by_id["saber_tooth"] == (40, CHENG, True)
    assert by_id["earth_heart"] == (50, BAN, False)


@pytest.mark.asyncio
async def test_sync_museum_upsert(sf):
    sync = FarmSync(sf)
    data = farm_data_factory()
    await sync._sync_museum(TEST_ACCOUNT, data)

    data["museum"]["items"][0]["fragmentCount"] = 8
    await sync._sync_museum(TEST_ACCOUNT, data)

    async with sf() as s:
        rows = await s.execute(
            text("SELECT item_id, fragment_count, status, is_repaired "
                 "FROM player_museum WHERE account_id=:aid ORDER BY item_id"),
            {"aid": TEST_ACCOUNT},
        )
        rows = rows.fetchall()

    assert len(rows) == 4
    by_id = {r[0]: (r[1], r[2], r[3]) for r in rows}
    assert by_id["rusty_sickle"] == (8, CHENG, True)


# ===================== collection =====================

@pytest.mark.asyncio
async def test_sync_collection(sf):
    sync = FarmSync(sf)
    await sync._sync_collection(TEST_ACCOUNT, farm_data_factory())

    async with sf() as s:
        rows = await s.execute(
            text("SELECT crop_id, quality, is_collected "
                 "FROM player_collection WHERE account_id=:aid ORDER BY crop_id, quality"),
            {"aid": TEST_ACCOUNT},
        )
        rows = rows.fetchall()

    collected = {(r[0], r[1], r[2]) for r in rows}
    assert len(rows) == 6

    assert ("barley", "普通", True) in collected
    assert sum(1 for r in rows if r[0] == "barley") == 1

    assert ("carrot", "普通", True) in collected
    assert ("carrot", "优", True) in collected

    assert ("corn", "普通", True) in collected
    assert ("corn", "优", True) in collected
    assert ("corn", "稀有", True) in collected


# ===================== land =====================

@pytest.mark.asyncio
async def test_sync_land_write(sf):
    sync = FarmSync(sf)
    await sync._sync_land(TEST_ACCOUNT, farm_data_factory())

    async with sf() as s:
        r = (await s.execute(
            text("SELECT land_level, land_name, research_points, next_level, "
                 "next_name, next_rp_needed, next_artifacts, "
                 "next_growth_pct, next_harvest_pct, can_upgrade "
                 "FROM farm_land WHERE account_id=:aid"),
            {"aid": TEST_ACCOUNT},
        )).fetchone()

    assert r is not None
    assert r[0] == 1
    assert r[1] == "普通土地"   # 普通土地
    assert r[2] == 121
    assert r[3] == 2
    assert r[4] == "肥沃土地"   # 肥沃土地
    assert r[5] == 200
    assert r[6] == 4
    assert r[7] == -2
    assert r[8] == 2
    assert r[9] is False


@pytest.mark.asyncio
async def test_sync_land_upsert(sf):
    sync = FarmSync(sf)
    data = farm_data_factory()
    await sync._sync_land(TEST_ACCOUNT, data)

    data["land"].update({
        "level": 2, "name": "肥沃土地",
        "researchPoints": 200, "canUpgrade": True,
        "next": {"level": 3, "name": "红土地",
                 "rpNeeded": 350, "artifacts": 10,
                 "growthPct": -4, "harvestPct": 4},
    })
    await sync._sync_land(TEST_ACCOUNT, data)

    async with sf() as s:
        r = (await s.execute(
            text("SELECT land_level, land_name, research_points, next_level, "
                 "next_name, next_rp_needed, next_artifacts, can_upgrade "
                 "FROM farm_land WHERE account_id=:aid"),
            {"aid": TEST_ACCOUNT},
        )).fetchone()

    assert r[0] == 2
    assert r[1] == "肥沃土地"   # 肥沃土地
    assert r[2] == 200
    assert r[3] == 3
    assert r[4] == "红土地"          # 红土地
    assert r[5] == 350
    assert r[6] == 10
    assert r[7] is True    # can_upgrade


@pytest.mark.asyncio
async def test_sync_land_from_slot(sf):
    """土地：从 slots[0].land 提取（真实 API 格式）"""
    sync = FarmSync(sf)
    await sync._sync_land(TEST_ACCOUNT, farm_data_factory(land_from_slot=True))

    async with sf() as s:
        r = (await s.execute(
            text("SELECT land_level, land_name, research_points, next_level, "
                 "next_name, next_rp_needed, next_artifacts, "
                 "next_growth_pct, next_harvest_pct, can_upgrade "
                 "FROM farm_land WHERE account_id=:aid"),
            {"aid": TEST_ACCOUNT},
        )).fetchone()

    assert r is not None
    assert r[0] == 1         # Lv.1
    assert r[1] == "普通土地"
    assert r[2] == 121       # research_points from requirements.research.current
    assert r[3] == 2         # next level
    assert r[4] == "肥沃土地"
    assert r[5] == 200       # nextLevel.researchCost
    assert r[6] == 4         # nextLevel.uniqueRequired
    assert r[7] == -2        # growthReduction 0.02 → -2%
    assert r[8] == 2         # harvestBonus 0.02 → +2%
    assert r[9] is False


# ===================== sync_all =====================

@pytest.mark.asyncio
async def test_sync_all(sf):
    sync = FarmSync(sf)
    result = await sync.sync_all(TEST_ACCOUNT, farm_data_factory())

    assert result["museum"] == 4
    assert result["collection"] == 6
    assert result["land"] is True

    async with sf() as s:
        m = (await s.execute(
            text("SELECT count(*) FROM player_museum WHERE account_id=:aid"),
            {"aid": TEST_ACCOUNT})).scalar()
        c = (await s.execute(
            text("SELECT count(*) FROM player_collection WHERE account_id=:aid"),
            {"aid": TEST_ACCOUNT})).scalar()
        l = (await s.execute(
            text("SELECT count(*) FROM farm_land WHERE account_id=:aid"),
            {"aid": TEST_ACCOUNT})).scalar()

    assert m == 4
    assert c == 6
    assert l == 1
