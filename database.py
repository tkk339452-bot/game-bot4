import aiosqlite
import time

DB_NAME = "game.db"


async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance INTEGER DEFAULT 0,
                priority TEXT DEFAULT 'none',
                last_work INTEGER DEFAULT 0,
                last_daily INTEGER DEFAULT 0,
                last_collect INTEGER DEFAULT 0,
                last_suggest INTEGER DEFAULT 0,
                last_casino INTEGER DEFAULT 0,
                last_duel INTEGER DEFAULT 0,
                total_earned INTEGER DEFAULT 0,
                invited_by INTEGER DEFAULT 0,
                ref_count INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                item_name TEXT,
                quantity INTEGER DEFAULT 1,
                UNIQUE(user_id, item_name)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                text TEXT,
                status TEXT DEFAULT 'pending',
                created_at INTEGER DEFAULT (strftime('%s','now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS personal_deposits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                user_id INTEGER,
                amount INTEGER DEFAULT 0,
                UNIQUE(chat_id, user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS player_banks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER UNIQUE,
                owner_name TEXT,
                bank_name TEXT,
                balance INTEGER DEFAULT 0,
                total_income INTEGER DEFAULT 0,
                interest INTEGER DEFAULT 5,
                created_at INTEGER DEFAULT (strftime('%s','now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bank_deposits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bank_id INTEGER,
                user_id INTEGER,
                amount INTEGER DEFAULT 0,
                UNIQUE(bank_id, user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS loans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lender_id INTEGER,
                lender_name TEXT,
                borrower_id INTEGER,
                borrower_name TEXT,
                amount INTEGER,
                repay_amount INTEGER,
                status TEXT DEFAULT 'pending',
                created_at INTEGER DEFAULT (strftime('%s','now')),
                expires_at INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS lottery (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                user_id INTEGER,
                username TEXT,
                tickets INTEGER DEFAULT 1,
                UNIQUE(chat_id, user_id)
            )
        """)
        await db.commit()


# ==================== USERS ====================
async def get_user(user_id: int, username: str = None):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()
            if user is None:
                from config import START_BALANCE
                await db.execute(
                    "INSERT INTO users (user_id, username, balance) VALUES (?, ?, ?)",
                    (user_id, username or "Unknown", START_BALANCE)
                )
                await db.commit()
                async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as c2:
                    user = await c2.fetchone()
            return dict(user)


async def update_balance(user_id: int, amount: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        if amount > 0:
            await db.execute("UPDATE users SET total_earned = total_earned + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()


async def update_field(user_id: int, field: str, value):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(f"UPDATE users SET {field} = ? WHERE user_id = ?", (value, user_id))
        await db.commit()


async def set_priority(user_id: int, priority: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET priority = ? WHERE user_id = ?", (priority, user_id))
        await db.commit()


async def set_referral(user_id: int, inviter_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET invited_by = ? WHERE user_id = ?", (inviter_id, user_id))
        await db.execute("UPDATE users SET ref_count = ref_count + 1 WHERE user_id = ?", (inviter_id,))
        await db.commit()


async def get_top(limit: int = 10):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT username, balance FROM users ORDER BY balance DESC LIMIT ?", (limit,)) as cursor:
            return [dict(r) for r in await cursor.fetchall()]


# ==================== INVENTORY ====================
async def add_item(user_id: int, item_name: str, qty: int = 1):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", (user_id, item_name)) as cursor:
            row = await cursor.fetchone()
            if row:
                await db.execute("UPDATE inventory SET quantity = quantity + ? WHERE user_id = ? AND item_name = ?", (qty, user_id, item_name))
            else:
                await db.execute("INSERT INTO inventory (user_id, item_name, quantity) VALUES (?, ?, ?)", (user_id, item_name, qty))
        await db.commit()


async def remove_item(user_id: int, item_name: str, qty: int = 1):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", (user_id, item_name)) as cursor:
            row = await cursor.fetchone()
            if not row or row[0] < qty:
                return False
            if row[0] == qty:
                await db.execute("DELETE FROM inventory WHERE user_id = ? AND item_name = ?", (user_id, item_name))
            else:
                await db.execute("UPDATE inventory SET quantity = quantity - ? WHERE user_id = ? AND item_name = ?", (qty, user_id, item_name))
        await db.commit()
        return True


async def set_item_quantity(user_id: int, item_name: str, quantity: int):
    async with aiosqlite.connect(DB_NAME) as db:
        if quantity <= 0:
            await db.execute("DELETE FROM inventory WHERE user_id = ? AND item_name = ?", (user_id, item_name))
        else:
            await db.execute("UPDATE inventory SET quantity = ? WHERE user_id = ? AND item_name = ?", (quantity, user_id, item_name))
        await db.commit()


async def get_inventory(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT item_name, quantity FROM inventory WHERE user_id = ?", (user_id,)) as cursor:
            return [dict(r) for r in await cursor.fetchall()]


# ==================== FOOD EFFECTS ====================
async def set_food_effect(user_id: int, effect_type: str, value: int, uses: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM inventory WHERE user_id = ? AND item_name LIKE '__effect_%'", (user_id,))
        await db.execute(
            "INSERT INTO inventory (user_id, item_name, quantity) VALUES (?, ?, ?)",
            (user_id, f"__effect_{effect_type}__{value}_{uses}", 1)
        )
        await db.commit()


async def get_food_effect(user_id: int, effect_type: str = "luck"):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT item_name FROM inventory WHERE user_id = ? AND item_name LIKE ?",
            (user_id, f"__effect_{effect_type}%")
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            parts = row[0].replace(f"__effect_{effect_type}", "").strip("_").split("_")
            if len(parts) >= 2:
                return {"value": int(parts[0]), "uses": int(parts[1])}
            return None


async def use_food_effect(user_id: int, effect_type: str = "luck"):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT item_name FROM inventory WHERE user_id = ? AND item_name LIKE ?",
            (user_id, f"__effect_{effect_type}%")
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            parts = row[0].replace(f"__effect_{effect_type}", "").strip("_").split("_")
            value = int(parts[0])
            uses = int(parts[1]) - 1
            if uses <= 0:
                await db.execute("DELETE FROM inventory WHERE user_id = ? AND item_name = ?", (user_id, row[0]))
                await db.commit()
                return None
            new_name = f"__effect_{effect_type}__{value}_{uses}"
            await db.execute("UPDATE inventory SET item_name = ? WHERE user_id = ? AND item_name = ?", (new_name, user_id, row[0]))
            await db.commit()
            return {"value": value, "uses": uses}


# ==================== SUGGESTIONS ====================
async def add_suggestion(user_id: int, username: str, text: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO suggestions (user_id, username, text) VALUES (?, ?, ?)", (user_id, username, text))
        await db.commit()


async def get_suggestions(limit: int = 30):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM suggestions ORDER BY id DESC LIMIT ?", (limit,)) as cursor:
            return [dict(r) for r in await cursor.fetchall()]


async def get_suggestion(sug_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM suggestions WHERE id = ?", (sug_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def update_suggestion_status(sug_id: int, status: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE suggestions SET status = ? WHERE id = ?", (status, sug_id))
        await db.commit()


async def delete_suggestion(sug_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM suggestions WHERE id = ?", (sug_id,))
        await db.commit()


# ==================== PERSONAL BANKS ====================
async def create_player_bank(owner_id: int, owner_name: str, bank_name: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO player_banks (owner_id, owner_name, bank_name, interest) VALUES (?, ?, ?, 5)",
            (owner_id, owner_name, bank_name)
        )
        await db.commit()
        async with db.execute("SELECT id FROM player_banks WHERE owner_id = ?", (owner_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


async def get_player_bank(owner_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM player_banks WHERE owner_id = ?", (owner_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_bank_by_id(bank_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM player_banks WHERE id = ?", (bank_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_all_player_banks():
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM player_banks ORDER BY balance DESC LIMIT 20") as cursor:
            return [dict(r) for r in await cursor.fetchall()]


async def update_player_bank(bank_id: int, amount: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE player_banks SET balance = balance + ? WHERE id = ?", (amount, bank_id))
        await db.commit()


async def add_bank_income(bank_id: int, amount: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE player_banks SET total_income = total_income + ? WHERE id = ?", (amount, bank_id))
        await db.commit()


async def set_bank_interest(bank_id: int, interest: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE player_banks SET interest = ? WHERE id = ?", (interest, bank_id))
        await db.commit()


async def rename_bank(bank_id: int, new_name: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE player_banks SET bank_name = ? WHERE id = ?", (new_name, bank_id))
        await db.commit()


async def close_bank(bank_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM bank_deposits WHERE bank_id = ?", (bank_id,))
        await db.execute("DELETE FROM player_banks WHERE id = ?", (bank_id,))
        await db.commit()


async def get_bank_deposit(bank_id: int, user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM bank_deposits WHERE bank_id = ? AND user_id = ?", (bank_id, user_id)) as cursor:
            row = await cursor.fetchone()
            if row is None:
                await db.execute("INSERT INTO bank_deposits (bank_id, user_id, amount) VALUES (?, ?, 0)", (bank_id, user_id))
                await db.commit()
                return {"bank_id": bank_id, "user_id": user_id, "amount": 0}
            return dict(row)


async def add_bank_deposit(bank_id: int, user_id: int, amount: int):
    await get_bank_deposit(bank_id, user_id)
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE bank_deposits SET amount = amount + ? WHERE bank_id = ? AND user_id = ?", (amount, bank_id, user_id))
        await db.commit()


async def get_bank_deposits(bank_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM bank_deposits WHERE bank_id = ? AND amount > 0", (bank_id,)) as cursor:
            return [dict(r) for r in await cursor.fetchall()]


async def get_user_bank_deposits(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT bd.*, pb.bank_name, pb.id as bank_id FROM bank_deposits bd "
            "JOIN player_banks pb ON bd.bank_id = pb.id "
            "WHERE bd.user_id = ? AND bd.amount > 0",
            (user_id,)
        ) as cursor:
            return [dict(r) for r in await cursor.fetchall()]


# ==================== GROUP BANK (личные вклады) ====================
async def get_deposit(chat_id: int, user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM personal_deposits WHERE chat_id = ? AND user_id = ?", (chat_id, user_id)) as cursor:
            row = await cursor.fetchone()
            if row is None:
                await db.execute("INSERT INTO personal_deposits (chat_id, user_id, amount) VALUES (?, ?, 0)", (chat_id, user_id))
                await db.commit()
                return {"chat_id": chat_id, "user_id": user_id, "amount": 0}
            return dict(row)


async def add_deposit(chat_id: int, user_id: int, amount: int):
    await get_deposit(chat_id, user_id)
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE personal_deposits SET amount = amount + ? WHERE chat_id = ? AND user_id = ?", (amount, chat_id, user_id))
        await db.commit()


async def get_all_deposits(chat_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM personal_deposits WHERE chat_id = ? AND amount > 0", (chat_id,)) as cursor:
            return [dict(r) for r in await cursor.fetchall()]


# ==================== LOANS ====================
async def create_loan(lender_id, lender_name, borrower_id, borrower_name, amount, repay_amount, expires_at):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO loans (lender_id, lender_name, borrower_id, borrower_name, amount, repay_amount, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (lender_id, lender_name, borrower_id, borrower_name, amount, repay_amount, expires_at)
        )
        await db.commit()


async def get_loan(loan_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM loans WHERE id = ?", (loan_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def update_loan_status(loan_id: int, status: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE loans SET status = ? WHERE id = ?", (status, loan_id))
        await db.commit()


async def get_user_loans(user_id: int, role: str = "borrower", status: str = "active"):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        field = "borrower_id" if role == "borrower" else "lender_id"
        async with db.execute(f"SELECT * FROM loans WHERE {field} = ? AND status = ?", (user_id, status)) as cursor:
            return [dict(r) for r in await cursor.fetchall()]


async def get_expired_loans():
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        now = int(time.time())
        async with db.execute("SELECT * FROM loans WHERE status = 'active' AND expires_at < ?", (now,)) as cursor:
            return [dict(r) for r in await cursor.fetchall()]


# ==================== LOTTERY ====================
async def add_lottery_ticket(chat_id: int, user_id: int, username: str, tickets: int = 1):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT tickets FROM lottery WHERE chat_id = ? AND user_id = ?", (chat_id, user_id)) as cursor:
            row = await cursor.fetchone()
            if row:
                await db.execute("UPDATE lottery SET tickets = tickets + ? WHERE chat_id = ? AND user_id = ?", (tickets, chat_id, user_id))
            else:
                await db.execute("INSERT INTO lottery (chat_id, user_id, username, tickets) VALUES (?, ?, ?, ?)", (chat_id, user_id, username, tickets))
        await db.commit()


async def get_lottery(chat_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM lottery WHERE chat_id = ?", (chat_id,)) as cursor:
            return [dic