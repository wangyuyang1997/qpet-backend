"""museum_catalog 和 collection_catalog 静态数据初始化"""
import logging
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.models import MuseumCatalog, CollectionCatalog, CropCache

logger = logging.getLogger(__name__)

# 藏品品质 → 碎片需求
QUALITY_FRAGMENTS = {"普通": 8, "良品": 18, "稀有": 40, "传说": 100}

# 10个博物馆分类
MUSEUM_CATEGORIES = [
    "农耕旧物", "古币陶瓷", "远古化石", "自然珍藏", "民俗记忆",
    "星陨奇物", "文房遗珍", "海贸遗珍", "祥瑞异录", "机巧秘藏",
]


async def init_collection_catalog(db_session_factory) -> int:
    """从 crop_cache 表同步 72 条作物到 collection_catalog"""
    async with db_session_factory() as db:
        crops = await db.execute(select(CropCache))
        crops = crops.scalars().all()

    count = 0
    async with db_session_factory() as db:
        for i, c in enumerate(crops):
            cat = _map_crop_category(c.category)
            rarity = _map_crop_rarity(c.rarity)
            stmt = pg_insert(CollectionCatalog).values(
                crop_id=c.id,
                crop_name=c.name,
                category=cat,
                crop_rarity=rarity,
                sort_order=i,
            ).on_conflict_do_update(
                constraint="collection_catalog_pkey",
                set_=dict(crop_name=c.name, category=cat, crop_rarity=rarity),
            )
            await db.execute(stmt)
            count += 1
        await db.commit()

    logger.info(f"collection_catalog 初始化完成: {count} 条")
    return count


async def seed_museum_catalog(db_session_factory, items: list[dict]) -> int:
    """写入博物馆藏品目录。items: [{item_id, name, category, rarity}]
    仅在表为空时写入（避免覆盖已有数据）。
    """
    async with db_session_factory() as db:
        existing = await db.execute(select(MuseumCatalog).limit(1))
        if existing.scalar_one_or_none():
            logger.info("museum_catalog 已有数据，跳过初始化")
            return 0

        count = 0
        for i, item in enumerate(items):
            rarity = item.get("rarity", "普通")
            stmt = pg_insert(MuseumCatalog).values(
                item_id=item["item_id"],
                name=item["name"],
                category=item.get("category", ""),
                rarity=rarity,
                fragments_needed=QUALITY_FRAGMENTS.get(rarity, 8),
                description=item.get("description", ""),
                sort_order=i,
            ).on_conflict_do_nothing()
            await db.execute(stmt)
            count += 1
        await db.commit()

    logger.info(f"museum_catalog 初始化完成: {count} 条")
    return count


def _map_crop_category(cat: str) -> str:
    mapping = {
        "grain": "粮食", "vegetable": "蔬菜", "fruit": "水果",
        "flower": "花卉", "special": "特产",
    }
    return mapping.get(cat, cat)


def _map_crop_rarity(r: str) -> str:
    mapping = {
        "normal": "普通", "fine": "良品", "rare": "稀有", "legend": "传说",
    }
    return mapping.get(r, r)
