import asyncio
import random
import time
import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

import config
from database import (
    init_db, get_user, update_balance, update_field, set_priority, set_referral,
    add_item, remove_item, set_item_quantity, get_inventory, get_top,
    set_food_effect, get_food_effect, use_food_effect,
    add_suggestion, get_suggestions, get_suggestion,
    update_suggestion_status, delete_suggestion,
    create_player_bank, get_player_bank, get_bank_by_id, get_all_player_banks,
    update_player_bank, add_bank_income, set_bank_interest, rename_bank, close_bank,
    get_bank_deposit, add_bank_deposit, get_bank_deposits, get_user_bank_deposits,
    get_deposit, add_deposit, get_all_deposits,
    create_loan, get_loan, update_loan_status, get_user_loans, get_expired_loans,
    add_lottery_ticket, get_lottery, clear_lottery
)

bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

casino_pending = {}


def is_owner(user_id: int) -> bool:
    return user_id == config.OWNER_ID


# ==================== МЕНЮ ====================
def main_menu_kb(user_id: int):
    rows = [
        [InlineKeyboardButton(text="👤 Профиль", callback_data=f"m_profile::{user_id}"),
         InlineKeyboardButton(text="💼 Работа", callback_data=f"m_work::{user_id}")],
        [InlineKeyboardButton(text="🏪 Магазин", callback_data=f"m_shop::{user_id}"),
         InlineKeyboardButton(text="🎒 Инвентарь", callback_data=f"m_inv::{user_id}")],
        [InlineKeyboardButton(text="📦 Сбор", callback_data=f"m_collect::{user_id}"),
         InlineKeyboardButton(text="🎰 Казино", callback_data=f"m_casino::{user_id}")],
        [InlineKeyboardButton(text="🏆 Топ", callback_data=f"m_top::{user_id}"),
         InlineKeyboardButton(text="💡 Идея", callback_data=f"m_suggest::{user_id}")],
    ]
    if is_owner(user_id):
        rows.append([InlineKeyboardButton(text="⭐ Приоритет", callback_data="o_setprio"),
                     InlineKeyboardButton(text="💸 Деньги", callback_data="o_give")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def main_menu_text(user):
    prio = config.PRIORITIES.get(user.get("priority", "none"), config.PRIORITIES["none"])
    return (
        f"🎮 <b>ГЛАВНОЕ МЕНЮ</b>\n\n"
        f"👤 {user['username']}\n"
        f"💰 Баланс: <b>{user['balance']} {config.CURRENCY}</b>\n"
        f"⭐ {prio['name']}"
    )


HELP_TEXT = """🎮 <b>КОМАНДЫ</b>

/profile /balance /work /daily
/shop /inv /use /sell
/collect /casino /top
/mypriority /priorities /suggest
/pay /ref /duel /loan /loans /repay
/bank — система банков
/help — эта справка
"""

OWNER_TEXT = """
👑 <b>ВЛАДЕЛЕЦ:</b>
/setpriority /takepriority
/give /suggestions
"""


@dp.message(Command("start"))
async def cmd_start(message: Message):
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            inviter_id = int(args[1].replace("ref_", ""))
            user = await get_user(message.from_user.id, message.from_user.username)
            if user.get("invited_by", 0) == 0 and inviter_id != message.from_user.id:
                await set_referral(message.from_user.id, inviter_id)
                await update_balance(message.from_user.id, config.REFERRAL_BONUS_NEW)
                await update_balance(inviter_id, config.REFERRAL_BONUS_INVITER)
                try:
                    await bot.send_message(inviter_id, f"🎉 По твоей ссылке пришёл игрок!\n+{config.REFERRAL_BONUS_INVITER} {config.CURRENCY}")
                except Exception:
                    pass
        except Exception:
            pass
    user = await get_user(message.from_user.id, message.from_user.username)
    text = main_menu_text(user) + "\n\n" + HELP_TEXT
    if is_owner(message.from_user.id):
        text += OWNER_TEXT
    await message.answer(text, reply_markup=main_menu_kb(message.from_user.id))


@dp.message(Command("help"))
async def cmd_help(message: Message):
    text = HELP_TEXT
    if is_owner(message.from_user.id):
        text += OWNER_TEXT
    await message.answer(text)


@dp.callback_query(F.data == "m_main")
async def cb_main(call: CallbackQuery):
    user = await get_user(call.from_user.id, call.from_user.username)
    await call.message.edit_text(main_menu_text(user), reply_markup=main_menu_kb(call.from_user.id))
    await call.answer()


# ==================== ПРОФИЛЬ ====================
async def profile_text(user):
    items = await get_inventory(user["user_id"])
    biz = sum(i["quantity"] for i in items if i["item_name"] in config.BUSINESSES)
    tra = sum(i["quantity"] for i in items if i["item_name"] in config.TRANSPORT)
    prio = config.PRIORITIES.get(user.get("priority", "none"), config.PRIORITIES["none"])
    return (
        f"👤 <b>ПРОФИЛЬ</b>\n\n"
        f"🆔 <code>{user['user_id']}</code>\n"
        f"📛 {user['username']}\n"
        f"💰 Баланс: <b>{user['balance']} {config.CURRENCY}</b>\n"
        f"⭐ {prio['name']}\n"
        f"💼 Бизнесов: {biz}\n"
        f"🚗 Транспорта: {tra}\n"
        f"👥 Приглашено: {user.get('ref_count', 0)}\n"
        f"📈 Всего: {user['total_earned']}"
    )


@dp.message(Command("profile"))
async def cmd_profile(message: Message):
    user = await get_user(message.from_user.id, message.from_user.username)
    await message.answer(await profile_text(user))


@dp.callback_query(F.data.startswith("m_profile::"))
async def cb_profile(call: CallbackQuery):
    owner_id = int(call.data.split("::")[1])
    if call.from_user.id != owner_id:
        await call.answer("❌ Это не твоё меню! Напиши /start", show_alert=True)
        return
    user = await get_user(call.from_user.id, call.from_user.username)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="m_main")]])
    await call.message.edit_text(await profile_text(user), reply_markup=kb)
    await call.answer()


@dp.message(Command("balance"))
async def cmd_balance(message: Message):
    user = await get_user(message.from_user.id, message.from_user.username)
    await message.answer(f"💰 Баланс: <b>{user['balance']} {config.CURRENCY}</b>")


# ==================== РАБОТА ====================
JOBS = ["программистом", "курьером", "баристой", "таксистом", "грузчиком", "дизайнером"]
VALVE_TEXTS = [
    "🎮 <b>РЕДКОЕ СОБЫТИЕ!</b>\n\n💼 Ты в <b>Valve</b>!\n👨‍💼 Гейб: «HL3 скоро™»\n\n💰 Заработал: <b>3 {c}</b>",
    "🎮 <b>РЕДКОЕ СОБЫТИЕ!</b>\n\n💼 Ты в офисе <b>Valve</b>!\n\n💰 Заработал: <b>3 {c}</b>",
    "🎮 <b>РЕДКОЕ СОБЫТИЕ!</b>\n\n💼 Работа в <b>Valve</b>!\n🎲 HL3: 3%\n\n💰 Заработал: <b>3 {c}</b>",
]
BIG_BONUS = ["🏆 <b>КРУПНАЯ ПРЕМИЯ!</b>", "🏆 <b>Тебя повысили!</b>"]
SMALL_BONUS = ["🎁 <b>Премия!</b>", "🎁 <b>Бонус!</b>"]


def roll_work():
    salary = random.randint(config.WORK_MIN, config.WORK_MAX)
    if random.random() < config.WORK_VALVE_CHANCE:
        return 3, 300, "valve", random.choice(VALVE_TEXTS).format(c=config.CURRENCY)
    if random.random() < config.WORK_BIG_BONUS_CHANCE:
        return salary, config.WORK_BIG_BONUS, "big", random.choice(BIG_BONUS)
    if random.random() < config.WORK_SMALL_BONUS_CHANCE:
        return salary, config.WORK_SMALL_BONUS, "small", random.choice(SMALL_BONUS)
    return salary, 0, "none", ""


async def do_work(user_id: int, username: str, reply_func):
    user = await get_user(user_id, username)
    now = int(time.time())
    # Проверка энергии от бургера
    energy = await get_food_effect(user_id, "energy")
    if now - user["last_work"] < config.WORK_COOLDOWN and not energy:
        await reply_func(f"⏳ Отдохни {config.WORK_COOLDOWN - (now - user['last_work'])} сек.")
        return
    if energy:
        await use_food_effect(user_id, "energy")
    salary, bonus, kind, event_text = roll_work()
    total = salary + bonus
    await update_balance(user_id, total)
    await update_field(user_id, "last_work", now)
    if kind == "valve":
        await reply_func(event_text + f"\n\n🎁 Бонус: +{bonus}\n\n💵 Итого: <b>+{total} {config.CURRENCY}</b>")
    elif kind in ("big", "small"):
        await reply_func(f"💼 Ты поработал {random.choice(JOBS)} и заработал <b>{salary} {config.CURRENCY}</b>!\n\n{event_text}\n💰 Бонус: +{bonus}\n\n💵 Итого: <b>+{total} {config.CURRENCY}</b>")
    else:
        await reply_func(f"💼 Ты поработал {random.choice(JOBS)} и заработал <b>{salary} {config.CURRENCY}</b>!")


@dp.message(Command("work"))
async def cmd_work(message: Message):
    await do_work(message.from_user.id, message.from_user.username, message.answer)


@dp.callback_query(F.data.startswith("m_work::"))
async def cb_work(call: CallbackQuery):
    owner_id = int(call.data.split("::")[1])
    if call.from_user.id != owner_id:
        await call.answer("❌ Это не твоё меню! Напиши /start", show_alert=True)
        return
    await do_work(call.from_user.id, call.from_user.username, call.message.answer)
    await call.answer()


@dp.message(Command("daily"))
async def cmd_daily(message: Message):
    user = await get_user(message.from_user.id, message.from_user.username)
    now = int(time.time())
    if now - user["last_daily"] < config.DAILY_COOLDOWN:
        wait = config.DAILY_COOLDOWN - (now - user["last_daily"])
        await message.answer(f"⏳ Бонус через {wait // 3600}ч {(wait % 3600) // 60}м")
        return
    await update_balance(message.from_user.id, config.DAILY_REWARD)
    await update_field(message.from_user.id, "last_daily", now)
    await message.answer(f"🎁 Бонус: <b>{config.DAILY_REWARD} {config.CURRENCY}</b>!")
    

# ==================== МАГАЗИН ====================
def shop_menu_kb(owner_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💼 Бизнесы", callback_data=f"sc_business::{owner_id}"),
         InlineKeyboardButton(text="🚗 Транспорт", callback_data=f"sc_transport::{owner_id}")],
        [InlineKeyboardButton(text="⚔️ Предметы", callback_data=f"sc_items::{owner_id}"),
         InlineKeyboardButton(text="🍔 Еда", callback_data=f"sc_food::{owner_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="m_main")],
    ])


def make_items_kb(items_dict, prefix, owner_id: int):
    rows = []
    for name, info in items_dict.items():
        rows.append([InlineKeyboardButton(
            text=f"{name} — {info['price']} {config.CURRENCY}",
            callback_data=f"{prefix}::{name}::{owner_id}"
        )])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"m_shop::{owner_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@dp.message(Command("shop"))
async def cmd_shop(message: Message):
    await message.answer("🏪 <b>МАГАЗИН</b>\n\nВыбери категорию:", reply_markup=shop_menu_kb(message.from_user.id))


@dp.callback_query(F.data.startswith("m_shop::"))
async def cb_shop(call: CallbackQuery):
    owner_id = int(call.data.split("::")[1])
    if call.from_user.id != owner_id:
        await call.answer("❌ Это не твоё меню! Напиши /shop", show_alert=True)
        return
    await call.message.edit_text("🏪 <b>МАГАЗИН</b>\n\nВыбери категорию:", reply_markup=shop_menu_kb(owner_id))
    await call.answer()


@dp.callback_query(F.data.startswith("sc_"))
async def cb_shop_cat(call: CallbackQuery):
    parts = call.data.split("::")
    cat = parts[0].replace("sc_", "")
    owner_id = int(parts[1])
    if call.from_user.id != owner_id:
        await call.answer("❌ Это не твоё меню! Напиши /shop", show_alert=True)
        return
    if cat == "business":
        text = "💼 <b>БИЗНЕСЫ</b>\n\n"
        for name, info in config.BUSINESSES.items():
            text += f"{name}\n💰 {info['price']} · 📈 +{info['income']}/час\n<i>{info['description']}</i>\n\n"
        await call.message.edit_text(text, reply_markup=make_items_kb(config.BUSINESSES, "buybiz", owner_id))
    elif cat == "transport":
        text = "🚗 <b>ТРАНСПОРТ</b>\n\n"
        for name, info in config.TRANSPORT.items():
            text += f"{name}\n💰 {info['price']} · 📈 +{info['income']}/час\n<i>{info['description']}</i>\n\n"
        await call.message.edit_text(text, reply_markup=make_items_kb(config.TRANSPORT, "buytra", owner_id))
    elif cat == "items":
        text = "⚔️ <b>ПРЕДМЕТЫ</b>\n\n"
        for name, info in config.ITEMS.items():
            text += f"{name} — {info['price']}\n<i>{info['description']}</i>\n\n"
        await call.message.edit_text(text, reply_markup=make_items_kb(config.ITEMS, "buyitm", owner_id))
    elif cat == "food":
        text = "🍔 <b>ЕДА</b>\n\n"
        for name, info in config.FOOD.items():
            text += f"{name} — {info['price']}\n<i>{info['description']}</i>\n\n"
        await call.message.edit_text(text, reply_markup=make_items_kb(config.FOOD, "buyfood", owner_id))
    await call.answer()


@dp.callback_query(F.data.startswith("buybiz::") | F.data.startswith("buytra::") | F.data.startswith("buyitm::") | F.data.startswith("buyfood::"))
async def cb_buy(call: CallbackQuery):
    parts = call.data.split("::")
    name = parts[1]
    owner_id = int(parts[2])
    if call.from_user.id != owner_id:
        await call.answer("❌ Не твоё меню", show_alert=True)
        return
    all_items = {}
    all_items.update(config.BUSINESSES)
    all_items.update(config.TRANSPORT)
    all_items.update(config.ITEMS)
    all_items.update(config.FOOD)
    if name not in all_items:
        await call.answer("❌ Не найдено", show_alert=True)
        return
    item = all_items[name]
    user = await get_user(call.from_user.id, call.from_user.username)
    if user["balance"] < item["price"]:
        await call.answer(f"❌ Нужно {item['price']}, у тебя {user['balance']}", show_alert=True)
        return
    await update_balance(call.from_user.id, -item["price"])
    await add_item(call.from_user.id, name)
    if name == "🍔 Бургер":
        await call.answer(f"✅ Куплено: {name}", show_alert=True)
        await call.message.answer("🍔 Мы что, идём есть бургеры? 😋")
        return
    await call.answer(f"✅ Куплено: {name}", show_alert=True)


# ==================== ИНВЕНТАРЬ ====================
def inv_menu_kb(owner_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💼 Бизнесы", callback_data=f"ic_biz::{owner_id}"),
         InlineKeyboardButton(text="🚗 Транспорт", callback_data=f"ic_tra::{owner_id}")],
        [InlineKeyboardButton(text="⚔️ Предметы", callback_data=f"ic_items::{owner_id}"),
         InlineKeyboardButton(text="🍔 Еда", callback_data=f"ic_food::{owner_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="m_main")],
    ])


async def inv_menu_text(user_id: int):
    items = await get_inventory(user_id)
    biz = sum(i["quantity"] for i in items if i["item_name"] in config.BUSINESSES)
    tra = sum(i["quantity"] for i in items if i["item_name"] in config.TRANSPORT)
    itm = sum(i["quantity"] for i in items if i["item_name"] in config.ITEMS)
    food = sum(i["quantity"] for i in items if i["item_name"] in config.FOOD)
    return (
        f"🎒 <b>ИНВЕНТАРЬ</b>\n\n"
        f"💼 Бизнесы: <b>{biz}</b>\n"
        f"🚗 Транспорт: <b>{tra}</b>\n"
        f"⚔️ Предметы: <b>{itm}</b>\n"
        f"🍔 Еда: <b>{food}</b>"
    )


@dp.message(Command("inv"))
async def cmd_inv(message: Message):
    await message.answer(await inv_menu_text(message.from_user.id), reply_markup=inv_menu_kb(message.from_user.id))


@dp.message(Command("inventory"))
async def cmd_inventory(message: Message):
    await cmd_inv(message)


@dp.callback_query(F.data.startswith("m_inv::"))
async def cb_inv(call: CallbackQuery):
    owner_id = int(call.data.split("::")[1])
    if call.from_user.id != owner_id:
        await call.answer("❌ Это не твоё меню! Напиши /inv", show_alert=True)
        return
    await call.message.edit_text(await inv_menu_text(owner_id), reply_markup=inv_menu_kb(owner_id))
    await call.answer()


@dp.callback_query(F.data.startswith("ic_"))
async def cb_inv_cat(call: CallbackQuery):
    parts = call.data.split("::")
    cat = parts[0].replace("ic_", "")
    owner_id = int(parts[1])
    if call.from_user.id != owner_id:
        await call.answer("❌ Не твоё меню", show_alert=True)
        return
    items = await get_inventory(call.from_user.id)
    back_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data=f"m_inv::{owner_id}")]])

    if cat == "biz":
        found = [i for i in items if i["item_name"] in config.BUSINESSES]
        if not found:
            await call.message.edit_text("💼 Бизнесов нет", reply_markup=back_kb)
            await call.answer()
            return
        rows = [[InlineKeyboardButton(text=f"{i['item_name']} × {i['quantity']}", callback_data=f"ibp::{i['item_name']}::{owner_id}")] for i in found]
        rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"m_inv::{owner_id}")])
        await call.message.edit_text("💼 <b>ВЫБЕРИ БИЗНЕС</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    elif cat == "tra":
        found = [i for i in items if i["item_name"] in config.TRANSPORT]
        if not found:
            await call.message.edit_text("🚗 Транспорта нет", reply_markup=back_kb)
            await call.answer()
            return
        rows = [[InlineKeyboardButton(text=f"{i['item_name']} × {i['quantity']}", callback_data=f"itp::{i['item_name']}::{owner_id}")] for i in found]
        rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"m_inv::{owner_id}")])
        await call.message.edit_text("🚗 <b>ТРАНСПОРТ</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    elif cat == "items":
        found = [i for i in items if i["item_name"] in config.ITEMS]
        if not found:
            await call.message.edit_text("⚔️ Предметов нет", reply_markup=back_kb)
            await call.answer()
            return
        rows = [[InlineKeyboardButton(text=f"{i['item_name']} × {i['quantity']}", callback_data=f"iip::{i['item_name']}::{owner_id}")] for i in found]
        rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"m_inv::{owner_id}")])
        await call.message.edit_text("⚔️ <b>ПРЕДМЕТЫ</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    elif cat == "food":
        found = [i for i in items if i["item_name"] in config.FOOD]
        if not found:
            await call.message.edit_text("🍔 Еды нет", reply_markup=back_kb)
            await call.answer()
            return
        rows = [[InlineKeyboardButton(text=f"{i['item_name']} × {i['quantity']}", callback_data=f"ifp::{i['item_name']}::{owner_id}")] for i in found]
        rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"m_inv::{owner_id}")])
        await call.message.edit_text("🍔 <b>ЕДА</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


# ---- Бизнес: улучшить/продать ----
@dp.callback_query(F.data.startswith("ibp::"))
async def cb_inv_biz_pick(call: CallbackQuery):
    parts = call.data.split("::")
    name = parts[1]
    owner_id = int(parts[2])
    if call.from_user.id != owner_id:
        await call.answer("❌ Не твоё меню", show_alert=True)
        return
    items = await get_inventory(call.from_user.id)
    item = next((i for i in items if i["item_name"] == name), None)
    if not item:
        await call.answer("❌ Не найдено", show_alert=True)
        return
    level = min(item["quantity"], config.BUSINESS_MAX_LEVEL)
    info = config.BUSINESSES[name]
    income = int(info["income"] * (1 + config.BUSINESS_UPGRADE_BONUS * (level - 1)))
    upgrade_cost = int(info["price"] * config.BUSINESS_UPGRADE_COST * level)
    text = (
        f"💼 <b>{name}</b>\n\n"
        f"📊 Уровень: <b>{level}/{config.BUSINESS_MAX_LEVEL}</b>\n"
        f"💰 Доход: <b>{income} {config.CURRENCY}/час</b>\n"
        f"💵 Улучшение: <b>{upgrade_cost} {config.CURRENCY}</b>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📈 Улучшить ({upgrade_cost})", callback_data=f"ibu::{name}::{owner_id}")],
        [InlineKeyboardButton(text="💸 Продать", callback_data=f"ibs::{name}::{owner_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"ic_biz::{owner_id}")],
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@dp.callback_query(F.data.startswith("ibu::"))
async def cb_inv_biz_up(call: CallbackQuery):
    parts = call.data.split("::")
    name = parts[1]
    owner_id = int(parts[2])
    if call.from_user.id != owner_id:
        await call.answer("❌ Не твоё меню", show_alert=True)
        return
    items = await get_inventory(call.from_user.id)
    item = next((i for i in items if i["item_name"] == name), None)
    if not item:
        await call.answer("❌ Не найдено", show_alert=True)
        return
    level = min(item["quantity"], config.BUSINESS_MAX_LEVEL)
    if level >= config.BUSINESS_MAX_LEVEL:
        await call.answer("❌ Максимум!", show_alert=True)
        return
    cost = int(config.BUSINESSES[name]["price"] * config.BUSINESS_UPGRADE_COST * level)
    user = await get_user(call.from_user.id)
    if user["balance"] < cost:
        await call.answer(f"❌ Нужно {cost}", show_alert=True)
        return
    await update_balance(call.from_user.id, -cost)
    await set_item_quantity(call.from_user.id, name, item["quantity"] + 1)
    await call.answer(f"✅ Уровень {level + 1}!", show_alert=True)
    call.data = f"ibp::{name}::{owner_id}"
    await cb_inv_biz_pick(call)


@dp.callback_query(F.data.startswith("ibs::"))
async def cb_inv_biz_sell(call: CallbackQuery):
    parts = call.data.split("::")
    name = parts[1]
    owner_id = int(parts[2])
    if call.from_user.id != owner_id:
        await call.answer("❌ Не твоё меню", show_alert=True)
        return
    items = await get_inventory(call.from_user.id)
    item = next((i for i in items if i["item_name"] == name), None)
    if not item:
        await call.answer("❌ Не найдено", show_alert=True)
        return
    level = min(item["quantity"], config.BUSINESS_MAX_LEVEL)
    price = int(config.BUSINESSES[name]["price"] * config.SELL_PERCENT / 100 * level)
    await set_item_quantity(call.from_user.id, name, item["quantity"] - 1)
    await update_balance(call.from_user.id, price)
    await call.answer(f"💸 +{price} {config.CURRENCY}!", show_alert=True)


# ---- Предмет: продать ----
@dp.callback_query(F.data.startswith("iip::"))
async def cb_inv_item_pick(call: CallbackQuery):
    parts = call.data.split("::")
    name = parts[1]
    owner_id = int(parts[2])
    if call.from_user.id != owner_id:
        await call.answer("❌ Не твоё меню", show_alert=True)
        return
    info = config.ITEMS[name]
    text = f"⚔️ <b>{name}</b>\n\n<i>{info['description']}</i>\n\n💰 Продать: {info['price'] * config.SELL_PERCENT // 100}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Продать", callback_data=f"iis::{name}::{owner_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"ic_items::{owner_id}")],
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@dp.callback_query(F.data.startswith("iis::"))
async def cb_inv_item_sell(call: CallbackQuery):
    parts = call.data.split("::")
    name = parts[1]
    owner_id = int(parts[2])
    if call.from_user.id != owner_id:
        await call.answer("❌ Не твоё меню", show_alert=True)
        return
    price = config.ITEMS[name]["price"] * config.SELL_PERCENT // 100
    ok = await remove_item(call.from_user.id, name, 1)
    if not ok:
        await call.answer("❌ Нет", show_alert=True)
        return
    await update_balance(call.from_user.id, price)
    await call.answer(f"💸 +{price}!", show_alert=True)


# ---- Еда: съесть ----
@dp.callback_query(F.data.startswith("ifp::"))
async def cb_inv_food_pick(call: CallbackQuery):
    parts = call.data.split("::")
    name = parts[1]
    owner_id = int(parts[2])
    if call.from_user.id != owner_id:
        await call.answer("❌ Не твоё меню", show_alert=True)
        return
    info = config.FOOD[name]
    text = f"🍔 <b>{name}</b>\n\n<i>{info['description']}</i>"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🍽 Съесть", callback_data=f"ife::{name}::{owner_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"ic_food::{owner_id}")],
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@dp.callback_query(F.data.startswith("ife::"))
async def cb_inv_food_eat(call: CallbackQuery):
    parts = call.data.split("::")
    name = parts[1]
    owner_id = int(parts[2])
    if call.from_user.id != owner_id:
        await call.answer("❌ Не твоё меню", show_alert=True)
        return
    ok = await remove_item(call.from_user.id, name, 1)
    if not ok:
        await call.answer("❌ Нет", show_alert=True)
        return
    if name == "🍔 Бургер":
        await call.message.answer("🍔 Мы что, идём есть бургеры? 😋")
        await call.answer()
        return
    info = config.FOOD[name]
    await set_food_effect(call.from_user.id, info["effect"], info["value"], info["uses"])
    if info["effect"] == "luck":
        await call.message.answer(f"🍽 Ты съел <b>{name}</b>!\n🍀 Удача +{info['value']}% на {info['uses']} игр")
    else:
        await call.message.answer(f"🍽 Ты съел <b>{name}</b>!")
    await call.answer()
    

# ==================== ИСПОЛЬЗОВАНИЕ / ПРОДАЖА (команды) ====================
@dp.message(Command("use"))
async def cmd_use(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: <code>/use [Название]</code>")
        return
    query = args[1].strip().lower()
    items = await get_inventory(message.from_user.id)
    matched = next((i["item_name"] for i in items if query in i["item_name"].lower()), None)
    if not matched:
        await message.answer("❌ Нет такого предмета")
        return
    if matched in config.FOOD:
        ok = await remove_item(message.from_user.id, matched, 1)
        if not ok:
            await message.answer("❌ Не найдено")
            return
        if matched == "🍔 Бургер":
            await message.answer("🍔 Мы что, идём есть бургеры? 😋")
            return
        info = config.FOOD[matched]
        await set_food_effect(message.from_user.id, info["effect"], info["value"], info["uses"])
        await message.answer(f"🍽 Ты съел <b>{matched}</b>!")
    elif matched == "💎 Алмаз":
        ok = await remove_item(message.from_user.id, matched, 1)
        if ok:
            await update_balance(message.from_user.id, 800)
            await message.answer("💎 Обменял Алмаз на <b>+800 {}</b>!".format(config.CURRENCY))
    else:
        await message.answer(f"ℹ️ <b>{matched}</b> — используй через /inv")


@dp.message(Command("sell"))
async def cmd_sell(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: <code>/sell [Название]</code>")
        return
    query = args[1].strip().lower()
    items = await get_inventory(message.from_user.id)
    matched = next((i["item_name"] for i in items if query in i["item_name"].lower()), None)
    if not matched:
        await message.answer("❌ Нет такого предмета")
        return
    if matched in config.BUSINESSES or matched in config.TRANSPORT:
        await message.answer("❌ Бизнесы и транспорт продаются через /inv")
        return
    all_items = {}
    all_items.update(config.ITEMS)
    all_items.update(config.FOOD)
    if matched not in all_items:
        await message.answer("❌ Нельзя продать")
        return
    price = all_items[matched]["price"] * config.SELL_PERCENT // 100
    await remove_item(message.from_user.id, matched, 1)
    await update_balance(message.from_user.id, price)
    await message.answer(f"💸 Продано <b>{matched}</b>\n💰 +{price} {config.CURRENCY}")


# ==================== СБОР ДОХОДА ====================
async def do_collect(user_id: int, username: str):
    user = await get_user(user_id, username)
    now = int(time.time())
    if now - user["last_collect"] < config.COLLECT_COOLDOWN:
        return None, f"⏳ Сбор через {(config.COLLECT_COOLDOWN - (now - user['last_collect'])) // 60}м"
    items = await get_inventory(user_id)
    biz = 0
    for i in items:
        if i["item_name"] in config.BUSINESSES:
            lvl = min(i["quantity"], config.BUSINESS_MAX_LEVEL)
            base_income = config.BUSINESSES[i["item_name"]]["income"]
            biz += int(base_income * (1 + config.BUSINESS_UPGRADE_BONUS * (lvl - 1)))
    tra = sum(config.TRANSPORT[i["item_name"]]["income"] * i["quantity"] for i in items if i["item_name"] in config.TRANSPORT)
    base = biz + tra
    if base == 0:
        return None, "❌ Нечего собирать!"
    prio = config.PRIORITIES.get(user.get("priority", "none"), config.PRIORITIES["none"])
    bonus = base * prio["bonus_income"] // 100
    gross = base + bonus
    tax_p = max(0, config.BASE_TAX_PERCENT - prio["tax_discount"])
    tax = gross * tax_p // 100
    net = gross - tax
    await update_balance(user_id, net)
    await update_field(user_id, "last_collect", now)
    return (
        f"📦 <b>СБОР</b>\n\n💼 Бизнесы: {biz}\n🚗 Транспорт: {tra}\nБаза: {base}\n"
        f"⭐ {prio['name']}: +{prio['bonus_income']}% → +{bonus}\n"
        f"Итого: {gross}\nНалог: −{tax}\n"
        f"✅ <b>{net} {config.CURRENCY}</b>"
    ), None


@dp.message(Command("collect"))
async def cmd_collect(message: Message):
    result, err = await do_collect(message.from_user.id, message.from_user.username)
    await message.answer(err if err else result)


@dp.callback_query(F.data.startswith("m_collect::"))
async def cb_collect(call: CallbackQuery):
    owner_id = int(call.data.split("::")[1])
    if call.from_user.id != owner_id:
        await call.answer("❌ Это не твоё меню!", show_alert=True)
        return
    result, err = await do_collect(call.from_user.id, call.from_user.username)
    if err:
        await call.answer(err, show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="m_main")]])
    await call.message.edit_text(result, reply_markup=kb)
    await call.answer()


# ==================== КАЗИНО ====================
def casino_menu_kb(owner_id: int):
    rows = []
    games = list(config.CASINO_GAMES.items())
    for i in range(0, len(games), 2):
        row = [InlineKeyboardButton(text=g["name"], callback_data=f"cg::{k}::{owner_id}") for k, g in games[i:i+2]]
        rows.append(row)
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="m_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@dp.message(Command("casino"))
async def cmd_casino(message: Message):
    await message.answer(
        f"🎰 <b>КАЗИНО</b>\n\nСтавки: {config.CASINO_MIN_BET}–{config.CASINO_MAX_BET} {config.CURRENCY}",
        reply_markup=casino_menu_kb(message.from_user.id)
    )


@dp.callback_query(F.data.startswith("m_casino::"))
async def cb_casino(call: CallbackQuery):
    owner_id = int(call.data.split("::")[1])
    if call.from_user.id != owner_id:
        await call.answer("❌ Это не твоё меню!", show_alert=True)
        return
    await call.message.edit_text(
        f"🎰 <b>КАЗИНО</b>\n\nСтавки: {config.CASINO_MIN_BET}–{config.CASINO_MAX_BET}",
        reply_markup=casino_menu_kb(owner_id)
    )
    await call.answer()


@dp.callback_query(F.data.startswith("cg::"))
async def cb_casino_pick(call: CallbackQuery):
    parts = call.data.split("::")
    key = parts[1]
    owner_id = int(parts[2])
    if call.from_user.id != owner_id:
        await call.answer("❌ Это не твоё меню!", show_alert=True)
        return
    game = config.CASINO_GAMES.get(key)
    if not game:
        await call.answer("❌ Не найдено", show_alert=True)
        return
    casino_pending[call.from_user.id] = key
    user = await get_user(call.from_user.id, call.from_user.username)
    text = (
        f"{game['name']}\n\n📈 ×{game['multiplier']}\n🎯 Шанс: {int(game['chance']*100)}%\n"
        f"💰 Баланс: <b>{user['balance']}</b>\n\n✍️ Напиши сумму ставки"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="m_main")]])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@dp.message(F.text.regexp(r"^\d+$"))
async def handle_bet(message: Message):
    if message.from_user.id not in casino_pending:
        return
    key = casino_pending.pop(message.from_user.id)
    game = config.CASINO_GAMES.get(key)
    if not game:
        return
    bet = int(message.text)
    if bet < config.CASINO_MIN_BET or bet > config.CASINO_MAX_BET:
        await message.answer(f"❌ Ставка от {config.CASINO_MIN_BET} до {config.CASINO_MAX_BET}")
        return
    user = await get_user(message.from_user.id, message.from_user.username)
    if user["balance"] < bet:
        await message.answer("❌ Недостаточно средств!")
        return
    luck = await get_food_effect(message.from_user.id, "luck")
    bonus_chance = 0
    if luck:
        bonus_chance = luck["value"] / 100
        await use_food_effect(message.from_user.id, "luck")
    if random.random() < (game["chance"] + bonus_chance):
        profit = int(bet * game["multiplier"]) - bet
        await update_balance(message.from_user.id, profit)
        luck_text = f"\n🍀 Удача помогла!" if luck else ""
        await message.answer(f"{game['name']}\n\n🎉 <b>ПОБЕДА!</b>\n💰 <b>+{profit} {config.CURRENCY}</b>{luck_text}")
    else:
        await update_balance(message.from_user.id, -bet)
        await message.answer(f"{game['name']}\n\n😢 <b>Проигрыш</b>\nПотеряно: <b>{bet} {config.CURRENCY}</b>")


# ==================== ТОП ====================
@dp.message(Command("top"))
async def cmd_top(message: Message):
    top = await get_top(10)
    medals = ["🥇", "🥈", "🥉"]
    text = "🏆 <b>ТОП</b>\n\n"
    for i, u in enumerate(top):
        prefix = medals[i] if i < 3 else f"{i+1}."
        text += f"{prefix} {u['username']} — <b>{u['balance']}</b>\n"
    await message.answer(text or "Пусто")


@dp.callback_query(F.data.startswith("m_top::"))
async def cb_top(call: CallbackQuery):
    owner_id = int(call.data.split("::")[1])
    if call.from_user.id != owner_id:
        await call.answer("❌ Это не твоё меню!", show_alert=True)
        return
    top = await get_top(10)
    medals = ["🥇", "🥈", "🥉"]
    text = "🏆 <b>ТОП</b>\n\n"
    for i, u in enumerate(top):
        prefix = medals[i] if i < 3 else f"{i+1}."
        text += f"{prefix} {u['username']} — <b>{u['balance']}</b>\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="m_main")]])
    await call.message.edit_text(text or "Пусто", reply_markup=kb)
    await call.answer()


# ==================== ПРИОРИТЕТЫ ====================
@dp.message(Command("mypriority"))
async def cmd_mypriority(message: Message):
    user = await get_user(message.from_user.id, message.from_user.username)
    prio = config.PRIORITIES.get(user.get("priority", "none"), config.PRIORITIES["none"])
    await message.answer(f"⭐ {prio['name']}\n📈 +{prio['bonus_income']}%\n💸 −{prio['tax_discount']}%")


@dp.message(Command("priorities"))
async def cmd_priorities(message: Message):
    text = "⭐ <b>ПРИОРИТЕТЫ</b>\n\n"
    for k, p in config.PRIORITIES.items():
        text += f"{p['name']}\n📈 +{p['bonus_income']}% · 💸 −{p['tax_discount']}%\n\n"
    await message.answer(text)


# ==================== ПРЕДЛОЖЕНИЯ ====================
@dp.message(Command("suggest"))
async def cmd_suggest(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("✍️ <code>/suggest Твоя идея</code>")
        return
    text = args[1].strip()[:config.SUGGEST_MAX_LENGTH]
    if len(text) < 5:
        await message.answer("❌ Коротко")
        return
    user = await get_user(message.from_user.id, message.from_user.username)
    now = int(time.time())
    if now - user["last_suggest"] < config.SUGGEST_COOLDOWN:
        await message.answer(f"⏳ Подожди {config.SUGGEST_COOLDOWN - (now - user['last_suggest'])} сек.")
        return
    await add_suggestion(message.from_user.id, message.from_user.username or "Unknown", text)
    await update_field(message.from_user.id, "last_suggest", now)
    await message.answer("✅ Отправлено!")
    if config.OWNER_ID:
        try:
            await bot.send_message(config.OWNER_ID, f"📬 <b>Идея</b>\n👤 @{message.from_user.username or message.from_user.id}\n💬 {text}")
        except Exception:
            pass


@dp.callback_query(F.data.startswith("m_suggest::"))
async def cb_suggest(call: CallbackQuery):
    owner_id = int(call.data.split("::")[1])
    if call.from_user.id != owner_id:
        await call.answer("❌ Это не твоё меню!", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="m_main")]])
    await call.message.edit_text("💡 Напиши: <code>/suggest Твоя идея</code>", reply_markup=kb)
    await call.answer()


# ==================== ПЕРЕВОД ДЕНЕГ ====================
@dp.message(Command("pay"))
async def cmd_pay(message: Message):
    args = message.text.split()
    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
        if len(args) < 2:
            await message.answer("Использование: <code>/pay [сумма]</code>")
            return
        try:
            amount = int(args[1])
        except ValueError:
            await message.answer("❌ Сумма — число")
            return
    else:
        if len(args) < 3:
            await message.answer("Использование: <code>/pay [ID] [сумма]</code>")
            return
        try:
            target_id = int(args[1])
            amount = int(args[2])
        except ValueError:
            await message.answer("❌ ID и сумма — числа")
            return
    if target_id == message.from_user.id:
        await message.answer("❌ Себе нельзя")
        return
    if amount <= 0:
        await message.answer("❌ Сумма > 0")
        return
    sender = await get_user(message.from_user.id, message.from_user.username)
    if sender["balance"] < amount:
        await message.answer(f"❌ У тебя только {sender['balance']}")
        return
    await get_user(target_id)
    await update_balance(message.from_user.id, -amount)
    await update_balance(target_id, amount)
    await message.answer(f"💸 Переведено <b>{amount} {config.CURRENCY}</b>")
    try:
        await bot.send_message(target_id, f"💸 Тебе перевели <b>{amount} {config.CURRENCY}</b>!")
    except Exception:
        pass


# ==================== РЕФЕРАЛЫ ====================
@dp.message(Command("ref"))
async def cmd_ref(message: Message):
    user = await get_user(message.from_user.id, message.from_user.username)
    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=ref_{message.from_user.id}"
    await message.answer(
        f"🎁 <b>РЕФЕРАЛЫ</b>\n\n"
        f"👥 Приглашено: <b>{user.get('ref_count', 0)}</b>\n\n"
        f"🔗 Твоя ссылка:\n<code>{link}</code>\n\n"
        f"💰 За друга: <b>+{config.REFERRAL_BONUS_INVITER} {config.CURRENCY}</b>\n"
        f"🎁 Друг получит: <b>+{config.REFERRAL_BONUS_NEW} {config.CURRENCY}</b>"
    )


# ==================== ДУЭЛИ ====================
@dp.message(Command("duel"))
async def cmd_duel(message: Message):
    if not message.reply_to_message:
        await message.answer(
            f"⚔️ <b>ДУЭЛЬ</b>\n\nОтветь (reply) на игрока:\n<code>/duel [сумма]</code>\n\n"
            f"Ставки: {config.DUEL_MIN_BET}–{config.DUEL_MAX_BET}"
        )
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ <code>/duel 500</code>")
        return
    try:
        bet = int(args[1])
    except ValueError:
        await message.answer("❌ Сумма — число")
        return
    if bet < config.DUEL_MIN_BET or bet > config.DUEL_MAX_BET:
        await message.answer(f"❌ Ставки от {config.DUEL_MIN_BET} до {config.DUEL_MAX_BET}")
        return
    opponent_id = message.reply_to_message.from_user.id
    if opponent_id == message.from_user.id:
        await message.answer("❌ С собой нельзя")
        return
    if opponent_id == bot.id:
        await message.answer("🤖 Я не дерусь!")
        return
    challenger = await get_user(message.from_user.id, message.from_user.username)
    opponent = await get_user(opponent_id)
    if challenger["balance"] < bet:
        await message.answer(f"❌ У тебя только {challenger['balance']}")
        return
    if opponent["balance"] < bet:
        await message.answer(f"❌ У противника только {opponent['balance']}")
        return
    winner = random.choice([challenger, opponent])
    loser = opponent if winner["user_id"] == challenger["user_id"] else challenger
    await update_balance(winner["user_id"], bet)
    await update_balance(loser["user_id"], -bet)
    cname = message.from_user.username or message.from_user.first_name
    oname = message.reply_to_message.from_user.username or message.reply_to_message.from_user.first_name
    await message.answer(
        f"⚔️ <b>ДУЭЛЬ!</b>\n\n🥊 {cname} vs {oname}\n💰 Ставка: {bet}\n\n"
        f"🏆 Победитель: <b>{winner['username']}</b>\n💰 +{bet} {config.CURRENCY}"
    )
    

# ==================== КРЕДИТЫ ====================
@dp.message(Command("loan"))
async def cmd_loan(message: Message):
    if not message.reply_to_message:
        await message.answer(
            f"💳 <b>КРЕДИТ</b>\n\nОтветь (reply) на игрока:\n<code>/loan [сумма]</code>\n\n"
            f"📊 Сумма: {config.LOAN_MIN}–{config.LOAN_MAX}\n"
            f"📈 Процент: {config.LOAN_INTEREST}%\n"
            f"⏰ Срок: {config.LOAN_DURATION // 3600}ч\n"
            f"⚠️ Штраф: {config.LOAN_PENALTY}%"
        )
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ <code>/loan 500</code>")
        return
    try:
        amount = int(args[1])
    except ValueError:
        await message.answer("❌ Сумма — число")
        return
    if amount < config.LOAN_MIN or amount > config.LOAN_MAX:
        await message.answer(f"❌ От {config.LOAN_MIN} до {config.LOAN_MAX}")
        return
    borrower_id = message.reply_to_message.from_user.id
    if borrower_id == message.from_user.id:
        await message.answer("❌ Себе нельзя")
        return
    if borrower_id == bot.id:
        await message.answer("🤖 Мне не надо")
        return
    lender = await get_user(message.from_user.id, message.from_user.username)
    if lender["balance"] < amount:
        await message.answer(f"❌ У тебя только {lender['balance']}")
        return
    borrower = await get_user(borrower_id)
    repay = amount + amount * config.LOAN_INTEREST // 100
    now = int(time.time())
    await create_loan(
        message.from_user.id,
        message.from_user.username or message.from_user.first_name,
        borrower_id,
        borrower["username"],
        amount, repay, now + config.LOAN_DURATION
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принять", callback_data=f"lok::{message.from_user.id}::{amount}::{repay}"),
         InlineKeyboardButton(text="❌ Отклонить", callback_data=f"lno::{message.from_user.id}")]
    ])
    try:
        await bot.send_message(
            borrower_id,
            f"💳 <b>ЗАЯВКА НА КРЕДИТ</b>\n\n"
            f"👤 От: @{message.from_user.username or message.from_user.id}\n"
            f"💰 Сумма: <b>{amount} {config.CURRENCY}</b>\n"
            f"📈 К возврату: <b>{repay}</b> (через {config.LOAN_DURATION // 3600}ч)\n\nПринять?",
            reply_markup=kb
        )
        await message.answer(f"✅ Заявка отправлена @{borrower['username']}")
    except Exception:
        await message.answer("❌ Не удалось (игрок не начал диалог с ботом)")


@dp.callback_query(F.data.startswith("lok::"))
async def cb_loan_ok(call: CallbackQuery):
    parts = call.data.split("::")
    lender_id = int(parts[1])
    amount = int(parts[2])
    repay = int(parts[3])
    borrower_id = call.from_user.id
    loans = await get_user_loans(borrower_id, "borrower", "pending")
    loan = next((l for l in loans if l["lender_id"] == lender_id and l["amount"] == amount), None)
    if not loan:
        await call.answer("❌ Не найдено", show_alert=True)
        return
    await update_balance(borrower_id, amount)
    await update_balance(lender_id, -amount)
    await update_loan_status(loan["id"], "active")
    await call.message.edit_text(
        f"✅ <b>Кредит принят!</b>\n\n💰 Получено: <b>{amount} {config.CURRENCY}</b>\n"
        f"📈 Вернуть: <b>{repay}</b>\n⏰ {config.LOAN_DURATION // 3600}ч\n\n"
        f"💡 <code>/repay {loan['id']}</code>"
    )
    await call.answer("✅ Принято!")
    try:
        await bot.send_message(lender_id, f"✅ @{call.from_user.username or borrower_id} принял кредит на {amount}")
    except Exception:
        pass


@dp.callback_query(F.data.startswith("lno::"))
async def cb_loan_no(call: CallbackQuery):
    lender_id = int(call.data.split("::")[1])
    borrower_id = call.from_user.id
    loans = await get_user_loans(borrower_id, "borrower", "pending")
    loan = next((l for l in loans if l["lender_id"] == lender_id), None)
    if loan:
        await update_loan_status(loan["id"], "rejected")
    await call.message.edit_text("❌ <b>Кредит отклонён</b>")
    await call.answer()
    try:
        await bot.send_message(lender_id, f"❌ @{call.from_user.username or borrower_id} отклонил кредит")
    except Exception:
        pass


@dp.message(Command("loans"))
async def cmd_loans(message: Message):
    args = message.text.split()
    mode = args[1].lower() if len(args) > 1 else "all"
    text = "💳 <b>МОИ КРЕДИТЫ</b>\n\n"
    has = False
    if mode in ("all", "in"):
        active = await get_user_loans(message.from_user.id, "borrower", "active")
        if active:
            has = True
            text += "📥 <b>Я должен:</b>\n"
            for l in active:
                left = max(0, (l["expires_at"] - int(time.time())) // 3600)
                text += f"#{l['id']} → @{l['lender_name']}: <b>{l['repay_amount']}</b> (⏰ {left}ч)\n"
            text += "\n💡 <code>/repay [ID]</code>\n\n"
    if mode in ("all", "out"):
        lent = await get_user_loans(message.from_user.id, "lender", "active")
        if lent:
            has = True
            text += "📤 <b>Мне должны:</b>\n"
            for l in lent:
                left = max(0, (l["expires_at"] - int(time.time())) // 3600)
                text += f"#{l['id']} ← @{l['borrower_name']}: <b>{l['repay_amount']}</b> (⏰ {left}ч)\n"
    if not has:
        text += "Активных кредитов нет."
    await message.answer(text)


@dp.message(Command("repay"))
async def cmd_repay(message: Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: <code>/repay [ID]</code>")
        return
    try:
        loan_id = int(args[1])
    except ValueError:
        await message.answer("❌ ID — число")
        return
    loan = await get_loan(loan_id)
    if not loan:
        await message.answer("❌ Не найден")
        return
    if loan["borrower_id"] != message.from_user.id:
        await message.answer("❌ Не твой")
        return
    if loan["status"] != "active":
        await message.answer(f"❌ Статус: {loan['status']}")
        return
    user = await get_user(message.from_user.id, message.from_user.username)
    if user["balance"] < loan["repay_amount"]:
        await message.answer(f"❌ Нужно {loan['repay_amount']}, у тебя {user['balance']}")
        return
    await update_balance(message.from_user.id, -loan["repay_amount"])
    await update_balance(loan["lender_id"], loan["repay_amount"])
    await update_loan_status(loan_id, "returned")
    await message.answer(f"✅ Кредит #{loan_id} возвращён!")
    try:
        await bot.send_message(loan["lender_id"], f"💰 @{message.from_user.username or message.from_user.id} вернул кредит #{loan_id}\n+{loan['repay_amount']} {config.CURRENCY}")
    except Exception:
        pass


# ==================== БАНК (общая система) ====================
@dp.message(Command("bank"))
async def cmd_bank(message: Message):
    args = message.text.split()
    if len(args) == 1 or (len(args) >= 2 and args[1].lower() == "help"):
        await message.answer(
            "🏛️ <b>СИСТЕМА БАНКОВ</b>\n\n"
            "📋 <b>Основное:</b>\n"
            "<code>/bank list</code> — все банки\n"
            "<code>/bank info [ID]</code> — инфо о банке\n"
            "<code>/bank create Название</code> — создать банк\n\n"
            "💰 <b>Вклады:</b>\n"
            "<code>/bank deposit [ID] [сумма]</code> — положить\n"
            "<code>/bank withdraw [ID] [сумма]</code> — снять свои\n"
            "<code>/bank my deposits</code> — мои вклады\n\n"
            "👑 <b>Владельцу:</b>\n"
            "<code>/bank my</code> — мой банк\n"
            "<code>/bank setinterest [ID] [%]</code> — процент (1–20)\n"
            "<code>/bank rename [ID] Название</code> — переименовать\n"
            "<code>/bank withdraw_bank [сумма]</code> — снять доход\n"
            "<code>/bank close [ID]</code> — закрыть\n\n"
            f"💡 Создание: {config.BANK_CREATE_PRICE} {config.CURRENCY}"
        )
        return

    sub = args[1].lower()

    if sub == "list":
        banks = await get_all_player_banks()
        if not banks:
            await message.answer("🏛️ Пока нет банков\n<code>/bank create Название</code>")
            return
        text = "🏛️ <b>ВСЕ БАНКИ</b>\n\n"
        for b in banks:
            text += f"#{b['id']} · <b>{b['bank_name']}</b>\n👤 {b['owner_name']} · 📈 {b['interest']}%\n💰 {b['balance']} {config.CURRENCY}\n\n"
        text += "💵 <code>/bank deposit [ID] [сумма]</code>"
        await message.answer(text)
        return

    if sub == "info" and len(args) >= 3:
        try:
            bank_id = int(args[2])
        except ValueError:
            await message.answer("❌ ID — число")
            return
        bank = await get_bank_by_id(bank_id)
        if not bank:
            await message.answer(f"❌ Банк #{bank_id} не найден")
            return
        deposits = await get_bank_deposits(bank_id)
        text = (
            f"🏛️ <b>{bank['bank_name']}</b> (#{bank['id']})\n\n"
            f"👤 {bank['owner_name']}\n📈 {bank['interest']}%\n"
            f"💰 Баланс: <b>{bank['balance']} {config.CURRENCY}</b>\n"
            f"📊 Всего дохода: {bank['total_income']}\n\n"
        )
        if deposits:
            text += "👥 <b>Вклады:</b>\n"
            for d in deposits[:10]:
                user = await get_user(d["user_id"])
                text += f"• {user['username']} — {d['amount']}\n"
        await message.answer(text)
        return

    if sub == "create":
        if len(args) < 3:
            await message.answer("Использование: <code>/bank create Название</code>")
            return
        bank_name = " ".join(args[2:])[:30]
        if len(bank_name) < 3:
            await message.answer("❌ Минимум 3 символа")
            return
        existing = await get_player_bank(message.from_user.id)
        if existing:
            await message.answer(f"❌ У тебя уже есть: <b>{existing['bank_name']}</b>")
            return
        user = await get_user(message.from_user.id, message.from_user.username)
        if user["balance"] < config.BANK_CREATE_PRICE:
            await message.answer(f"❌ Нужно {config.BANK_CREATE_PRICE}")
            return
        await update_balance(message.from_user.id, -config.BANK_CREATE_PRICE)
        bank_id = await create_player_bank(
            message.from_user.id,
            message.from_user.username or message.from_user.first_name,
            bank_name
        )
        await message.answer(
            f"🎉 <b>Банк создан!</b>\n\n#{bank_id} · <b>{bank_name}</b>\n"
            f"📈 Процент: {config.BANK_INTEREST_DEFAULT}%\n\n"
            f"💡 <code>/bank deposit {bank_id} [сумма]</code>"
        )
        return

    if sub == "deposit" and len(args) >= 4:
        try:
            bank_id = int(args[2])
            amount = int(args[3])
        except ValueError:
            await message.answer("❌ ID и сумма — числа")
            return
        bank = await get_bank_by_id(bank_id)
        if not bank:
            await message.answer(f"❌ Банк #{bank_id} не найден")
            return
        if bank["owner_id"] == message.from_user.id:
            await message.answer("❌ В свой банк нельзя")
            return
        if amount < config.MIN_BANK_DEPOSIT:
            await message.answer(f"❌ Минимум {config.MIN_BANK_DEPOSIT}")
            return
        user = await get_user(message.from_user.id, message.from_user.username)
        if user["balance"] < amount:
            await message.answer(f"❌ У тебя только {user['balance']}")
            return
        owner_cut = amount * bank["interest"] // 100
        user_kept = amount - owner_cut
        await update_balance(message.from_user.id, -amount)
        await add_bank_deposit(bank_id, message.from_user.id, user_kept)
        await update_player_bank(bank_id, owner_cut)
        await add_bank_income(bank_id, owner_cut)
        await message.answer(
            f"✅ Положил <b>{user_kept} {config.CURRENCY}</b> в #{bank_id}\n"
            f"💸 Комиссия ({bank['interest']}%): {owner_cut}"
        )
        try:
            await bot.send_message(bank["owner_id"], f"💰 Вклад в твой банк!\n+{owner_cut} {config.CURRENCY}")
        except Exception:
            pass
        return

    if sub == "withdraw" and len(args) >= 4:
        try:
            bank_id = int(args[2])
            amount = int(args[3])
        except ValueError:
            await message.answer("❌ ID и сумма — числа")
            return
        dep = await get_bank_deposit(bank_id, message.from_user.id)
        if dep["amount"] < amount:
            await message.answer(f"❌ У тебя в #{bank_id} только {dep['amount']}")
            return
        await add_bank_deposit(bank_id, message.from_user.id, -amount)
        await update_balance(message.from_user.id, amount)
        await message.answer(f"✅ Снял <b>{amount} {config.CURRENCY}</b> из #{bank_id}")
        return

    if sub == "my":
        if len(args) >= 3 and args[2].lower() == "deposits":
            deps = await get_user_bank_deposits(message.from_user.id)
            if not deps:
                await message.answer("💼 Ты не вкладывал ни в один банк")
                return
            text = "💼 <b>МОИ ВКЛАДЫ</b>\n\n"
            for d in deps:
                text += f"#{d['bank_id']} «{d['bank_name']}» — <b>{d['amount']}</b>\n"
            await message.answer(text)
            return
        bank = await get_player_bank(message.from_user.id)
        if not bank:
            await message.answer(f"❌ Нет банка\n<code>/bank create Название</code>")
            return
        deposits = await get_bank_deposits(bank["id"])
        text = (
            f"🏛️ <b>МОЙ БАНК</b>\n\n#{bank['id']} · <b>{bank['bank_name']}</b>\n"
            f"📈 {bank['interest']}%\n💰 <b>{bank['balance']} {config.CURRENCY}</b>\n"
            f"📊 Доход: {bank['total_income']}\n\n"
        )
        if deposits:
            text += "👥 <b>Вклады:</b>\n"
            for d in deposits[:10]:
                user = await get_user(d["user_id"])
                text += f"• {user['username']} — {d['amount']}\n"
        text += (
            f"\n⚙️ <code>/bank setinterest {bank['id']} 7</code>\n"
            f"<code>/bank rename {bank['id']} Имя</code>\n"
            f"<code>/bank withdraw_bank 500</code>\n"
            f"<code>/bank close {bank['id']}</code>"
        )
        await message.answer(text)
        return

    if sub == "setinterest" and len(args) >= 4:
        try:
            bank_id = int(args[2])
            interest = int(args[3])
        except ValueError:
            await message.answer("❌ ID и % — числа")
            return
        bank = await get_bank_by_id(bank_id)
        if not bank or bank["owner_id"] != message.from_user.id:
            await message.answer("❌ Не твой банк")
            return
        if interest < config.BANK_INTEREST_MIN or interest > config.BANK_INTEREST_MAX:
            await message.answer(f"❌ От {config.BANK_INTEREST_MIN} до {config.BANK_INTEREST_MAX}")
            return
        await set_bank_interest(bank_id, interest)
        await message.answer(f"✅ Процент #{bank_id} теперь <b>{interest}%</b>")
        return

    if sub == "rename" and len(args) >= 4:
        try:
            bank_id = int(args[2])
        except ValueError:
            await message.answer("❌ ID — число")
            return
        bank = await get_bank_by_id(bank_id)
        if not bank or bank["owner_id"] != message.from_user.id:
            await message.answer("❌ Не твой банк")
            return
        new_name = " ".join(args[3:])[:30]
        if len(new_name) < 3:
            await message.answer("❌ Минимум 3 символа")
            return
        await rename_bank(bank_id, new_name)
        await message.answer(f"✅ Переименован в <b>{new_name}</b>")
        return

    if sub == "withdraw_bank" and len(args) >= 3:
        bank = await get_player_bank(message.from_user.id)
        if not bank:
            await message.answer("❌ Нет банка")
            return
        try:
            amount = int(args[2])
        except ValueError:
            await message.answer("❌ Сумма — число")
            return
        if amount <= 0 or bank["balance"] < amount:
            await message.answer(f"❌ Доступно {bank['balance']}")
            return
        await update_player_bank(bank["id"], -amount)
        await update_balance(message.from_user.id, amount)
        await message.answer(f"💸 Снял <b>{amount} {config.CURRENCY}</b>")
        return

    if sub == "close" and len(args) >= 3:
        try:
            bank_id = int(args[2])
        except ValueError:
            await message.answer("❌ ID — число")
            return
        bank = await get_bank_by_id(bank_id)
        if not bank or bank["owner_id"] != message.from_user.id:
            await message.answer("❌ Не твой банк")
            return
        deposits = await get_bank_deposits(bank_id)
        for d in deposits:
            await update_balance(d["user_id"], d["amount"])
            try:
                await bot.send_message(d["user_id"], f"🏦 Банк закрыт. Возврат: {d['amount']} {config.CURRENCY}")
            except Exception:
                pass
        refund = config.BANK_CREATE_PRICE * config.BANK_CLOSE_REFUND // 100
        await update_balance(bank["owner_id"], refund + bank["balance"])
        await close_bank(bank_id)
        await message.answer(f"✅ Банк #{bank_id} закрыт\n💰 Возврат: {refund + bank['balance']} {config.CURRENCY}")
        return

    await message.answer("❓ Напиши <code>/bank</code> для справки")


# ==================== OWNER ====================
@dp.callback_query(F.data == "o_setprio")
async def cb_o_setprio(call: CallbackQuery):
    if not is_owner(call.from_user.id):
        await call.answer("❌", show_alert=True)
        return
    text = "⭐ <b>ВЫДАТЬ ПРИОРИТЕТ</b>\n\nНапиши: <code>/setpriority [ID] [ранг]</code>\n\nРанги:\n"
    for k, p in config.PRIORITIES.items():
        text += f"<code>{k}</code> — {p['name']}\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙", callback_data="m_main")]])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@dp.callback_query(F.data == "o_give")
async def cb_o_give(call: CallbackQuery):
    if not is_owner(call.from_user.id):
        await call.answer("❌", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙", callback_data="m_main")]])
    await call.message.edit_text("💸 Напиши: <code>/give [ID] [сумма]</code>", reply_markup=kb)
    await call.answer()


@dp.message(Command("setpriority"))
async def cmd_setprio(message: Message):
    if not is_owner(message.from_user.id):
        await message.answer("❌ Нет доступа")
        return
    args = message.text.split()
    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
        rank = args[1].lower() if len(args) > 1 else None
    elif len(args) >= 3:
        try:
            target_id = int(args[1])
        except ValueError:
            await message.answer("❌ ID — число")
            return
        rank = args[2].lower()
    else:
        await message.answer("Использование: <code>/setpriority [ID] [ранг]</code>")
        return
    if rank not in config.PRIORITIES:
        await message.answer(f"❌ Ранг <code>{rank}</code> не найден")
        return
    await get_user(target_id)
    await set_priority(target_id, rank)
    await message.answer(f"✅ {config.PRIORITIES[rank]['name']} выдан <code>{target_id}</code>")
    try:
        await bot.send_message(target_id, f"⭐ Тебе выдан: <b>{config.PRIORITIES[rank]['name']}</b>")
    except Exception:
        pass


@dp.message(Command("takepriority"))
async def cmd_takeprio(message: Message):
    if not is_owner(message.from_user.id):
        return
    args = message.text.split()
    if message.reply_to_message:
        target_