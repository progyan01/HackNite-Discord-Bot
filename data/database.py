import aiosqlite
import sqlite3

DB_PATH = "data/database.sqlite"

async def setup():
    """Initializes the database and creates the necessary tables if they don't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 1000
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                user_id INTEGER PRIMARY KEY,
                perk_10 INTEGER DEFAULT 0,
                perk_15 INTEGER DEFAULT 0,
                perk_20 INTEGER DEFAULT 0
            )
        """)
        try:
            await db.execute("ALTER TABLE users ADD COLUMN last_daily TEXT")
        except sqlite3.OperationalError:
            pass # Column already exists
            
        try:
            await db.execute("ALTER TABLE inventory ADD COLUMN perk_10 INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
            
        try:
            await db.execute("ALTER TABLE inventory ADD COLUMN perk_15 INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
            
        try:
            await db.execute("ALTER TABLE inventory ADD COLUMN perk_20 INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
            
        try:
            await db.execute("ALTER TABLE users ADD COLUMN daily_streak INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass

        try:
            await db.execute("ALTER TABLE users ADD COLUMN loan_amount INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass

        try:
            await db.execute("ALTER TABLE users ADD COLUMN loan_due TEXT")
        except sqlite3.OperationalError:
            pass

        try:
            await db.execute("ALTER TABLE users ADD COLUMN bounty INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass

        await db.commit()

async def get_inventory(user_id: int) -> dict:
    """Gets the user's perk inventory."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT perk_10, perk_15, perk_20 FROM inventory WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"perk_10": row[0], "perk_15": row[1], "perk_20": row[2]}
            else:
                return {"perk_10": 0, "perk_15": 0, "perk_20": 0}

async def update_perk(user_id: int, perk_type: str, amount: int):
    """Updates the quantity of a specific perk. perk_type should be 'perk_10', 'perk_15', or 'perk_20'."""
    # Ensure perk_type is strictly what we expect to avoid SQL injection since we format the string
    if perk_type not in ["perk_10", "perk_15", "perk_20"]:
        return
        
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"""
            INSERT INTO inventory (user_id, {perk_type}) 
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET {perk_type} = MAX(0, {perk_type} + excluded.{perk_type})
        """, (user_id, amount))
        await db.commit()

async def get_balance(user_id: int, create_if_missing: bool = True) -> int | None:
    """Gets the balance of a specific user."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return row[0]
            else:
                if create_if_missing:
                    # If user doesn't exist, insert them with default 1000 balance
                    await update_balance(user_id, 0)
                    return 1000
                return None

async def update_balance(user_id: int, amount: int):
    """Adds the given amount to the user's balance."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Insert user with 1000 + amount if they don't exist, otherwise increase by amount
        await db.execute("""
            INSERT INTO users (user_id, balance) 
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET balance = balance + ?
        """, (user_id, 1000 + amount, amount))
        await db.commit()

async def get_last_daily(user_id: int) -> str | None:
    """Gets the ISO formatted string of the last time a user claimed daily."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT last_daily FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return row[0]
            return None

async def update_last_daily(user_id: int, date_str: str, streak: int = 0):
    """Sets the ISO formatted string of the last time a user claimed daily and updates streak."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, balance, last_daily, daily_streak) 
            VALUES (?, 1000, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET last_daily = excluded.last_daily, daily_streak = excluded.daily_streak
        """, (user_id, date_str, streak))
        await db.commit()

async def get_user_data(user_id: int) -> dict | None:
    """Gets all relevant info for a user (balance, streaks, loans, bounties)"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT balance, last_daily, daily_streak, loan_amount, loan_due, bounty FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "balance": row[0],
                    "last_daily": row[1],
                    "daily_streak": row[2] or 0,
                    "loan_amount": row[3] or 0,
                    "loan_due": row[4],
                    "bounty": row[5] or 0
                }
            return None

async def update_loan(user_id: int, amount: int, due: str | None):
    """Updates the user's loan"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, balance, loan_amount, loan_due) 
            VALUES (?, 1000, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET loan_amount = excluded.loan_amount, loan_due = excluded.loan_due
        """, (user_id, amount, due))
        await db.commit()

async def update_bounty(user_id: int, amount_change: int):
    """Updates the user's bounty by amount_change"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, balance, bounty) 
            VALUES (?, 1000, MAX(0, ?))
            ON CONFLICT(user_id) DO UPDATE SET bounty = MAX(0, bounty + ?)
        """, (user_id, amount_change, amount_change))
        await db.commit()

async def get_all_loans():
    """Gets all active loans"""
    loans = []
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, loan_amount, loan_due FROM users WHERE loan_amount > 0 AND loan_due IS NOT NULL") as cursor:
            async for row in cursor:
                loans.append({"user_id": row[0], "loan_amount": row[1], "loan_due": row[2]})
    return loans

async def get_top_users(limit: int = 10) -> list:
    """Gets the top users by balance"""
    users = []
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT ?", (limit,)) as cursor:
            async for row in cursor:
                users.append({"user_id": row[0], "balance": row[1]})
    return users
