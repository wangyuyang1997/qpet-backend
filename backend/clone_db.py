"""Clone production qpet → qpet_v5_dev"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

PG = "postgresql+asyncpg://postgres:qpet123@8.137.186.154:5432"


async def main():
    src = create_async_engine(f"{PG}/qpet")
    dst = create_async_engine(f"{PG}/qpet_v5_dev")

    async with src.connect() as sc:
        r = await sc.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
        ))
        tables = [row[0] for row in r.fetchall()]
        print(f"{len(tables)} tables to clone: {tables}")

        for tbl in tables:
            # Get column info
            r2 = await sc.execute(text("""
                SELECT column_name, data_type, character_maximum_length, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = :t
                ORDER BY ordinal_position
            """), {"t": tbl})
            cols = [(row[0], row[1], row[2]) for row in r2.fetchall()]
            col_names = [c[0] for c in cols]

            # Build CREATE TABLE
            defs = []
            for name, dtype, maxlen in cols:
                if dtype == "character varying":
                    dt = f"varchar({maxlen})" if maxlen else "varchar"
                elif dtype == "timestamp with time zone":
                    dt = "timestamptz"
                elif dtype == "double precision":
                    dt = "float8"
                else:
                    dt = dtype
                defs.append(f'"{name}" {dt}')
            create_sql = f'CREATE TABLE "{tbl}" ({", ".join(defs)})'

            async with dst.connect() as dc:
                await dc.execute(text(f'DROP TABLE IF EXISTS "{tbl}" CASCADE'))
                await dc.execute(text("commit"))
                await dc.execute(text(create_sql))
                await dc.execute(text("commit"))

            # Copy rows
            r3 = await sc.execute(text(f'SELECT * FROM "{tbl}"'))
            rows = r3.fetchall()
            if rows:
                async with dst.connect() as dc:
                    for row in rows:
                        vals = {}
                        for i, cn in enumerate(col_names):
                            v = getattr(row, cn, None) if hasattr(row, cn) else row[i]
                            vals[cn] = v
                        placeholders = ", ".join(f":{cn}" for cn in col_names)
                        cn_list = ", ".join(f'"{cn}"' for cn in col_names)
                        await dc.execute(
                            text(f"INSERT INTO \"{tbl}\" ({cn_list}) VALUES ({placeholders})"),
                            vals,
                        )
                    await dc.execute(text("commit"))

            # Verify
            async with dst.connect() as dc:
                r4 = await dc.execute(text(f'SELECT COUNT(*) FROM "{tbl}"'))
                cnt = r4.fetchone()[0]
                print(f"  {tbl}: {cnt} rows")

    await src.dispose()
    await dst.dispose()
    print("\nClone complete!")


if __name__ == "__main__":
    asyncio.run(main())
