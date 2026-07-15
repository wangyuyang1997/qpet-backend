"""迁移: accounts.automation JSONB → account_configs 独立行，删除 automation 列"""
import asyncio, sys, json
sys.path.insert(0, ".")

from sqlalchemy import text
from app.core.database import AsyncSessionLocal


async def main():
    async with AsyncSessionLocal() as db:
        # 1. Get all accounts with non-empty automation
        r = await db.execute(
            text("SELECT id, automation FROM accounts WHERE automation IS NOT NULL")
        )
        rows = r.fetchall()
        total = 0

        for account_id, automation in rows:
            if not automation or not isinstance(automation, dict):
                continue
            for key, value in automation.items():
                val_str = str(value).lower() if isinstance(value, bool) else str(value)
                await db.execute(
                    text("""INSERT INTO account_configs (account_id, config_key, value)
                            VALUES (:aid, :key, :val)
                            ON CONFLICT (account_id, config_key) DO NOTHING"""),
                    {"aid": account_id, "key": key, "val": val_str},
                )
                total += 1

        await db.commit()
        print(f"Migrated {total} config entries from {len(rows)} accounts")

        # 2. Drop automation column
        await db.execute(text("ALTER TABLE accounts DROP COLUMN IF EXISTS automation"))
        await db.commit()
        print("Dropped accounts.automation column")

    print("\nMigration complete.")


if __name__ == "__main__":
    asyncio.run(main())
