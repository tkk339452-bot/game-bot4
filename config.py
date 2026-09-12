import os

BOT_TOKEN = "8906175524:AAET7eq3Wa7cqadY7zA-7D-s2VjYE7KKnlg"
OWNER_ID = 6993435162

CURRENCY = "💰"
START_BALANCE = 100

WORK_COOLDOWN = 60
WORK_MIN = 10
WORK_MAX = 50
WORK_VALVE_CHANCE = 0.03
WORK_BIG_BONUS_CHANCE = 0.05
WORK_SMALL_BONUS_CHANCE = 0.25
WORK_BIG_BONUS = 200
WORK_SMALL_BONUS = 50

DAILY_COOLDOWN = 86400
DAILY_REWARD = 200

PRIORITIES = {
    "none":   {"name": "🚫 Нет приоритета", "bonus_income": 0,  "tax_discount": 0},
    "bronze": {"name": "🥉 Бронза",         "bonus_income": 5,  "tax_discount": 10},
    "silver": {"name": "🥈 Серебро",        "bonus_income": 10, "tax_discount": 20},
    "gold":   {"name": "🥇 Золото",         "bonus_income": 20, "tax_discount": 30},
    "legend": {"name": "👑 Легенда",        "bonus_income": 50, "tax_discount": 50},
    "cmb":    {"name": "⭐ Престиж CMB",    "bonus_income": 100,"tax_discount": 80},
}
OWNER_ONLY_PRIORITIES = ["cmb", "legend"]

BASE_TAX_PERCENT = 15
COLLECT_COOLDOWN = 3600

BUSINESSES = {
    "🍋 Лимонадный ларёк":   {"price": 500,    "income": 20,    "description": "Продаёшь лимонад"},
    "🌭 Ларёк с хот-догами": {"price": 1500,   "income": 60,    "description": "Вкусные хот-доги"},
    "☕ Кофейня":            {"price": 5000,   "income": 200,   "description": "Уютная кофейня"},
    "🍔 Ресторан":           {"price": 20000,  "income": 800,   "description": "Респектабельный ресторан"},
    "🏢 Бизнес-центр":       {"price": 100000, "income": 4000,  "description": "Сдаёшь офисы"},
}

TRANSPORT = {
    "🚲 Велосипед": {"price": 1000,    "income": 30,    "description": "Простой"},
    "🏍️ Мотоцикл":  {"price": 5000,    "income": 150,   "description": "Быстрый"},
    "🚗 Машина":    {"price": 20000,   "income": 600,   "description": "Крутая"},
    "🏎️ Спорткар":  {"price": 100000,  "income": 3000,  "description": "Скорость"},
    "🛥️ Яхта":      {"price": 500000,  "income": 15000, "description": "Отдых"},
    "✈️ Самолёт":   {"price": 2000000, "income": 60000, "description": "Летаешь"},
}

ITEMS = {
    "⚔️ Меч":   {"price": 500,   "description": "Увеличивает силу"},
    "🛡️ Щит":   {"price": 450,   "description": "Защищает"},
    "💎 Алмаз": {"price": 1000,  "description": "Редкий камень"},
    "👑 Корона":{"price": 50000, "description": "Для королей"},
}

FOOD = {
    "🍔 Бургер": {"price": 100, "description": "Энергия — /work без кулдауна", "effect": "energy", "value": 1, "uses": 1},
    "🍕 Пицца":  {"price": 50,  "description": "Удача +5% в казино на 3 игры", "effect": "luck", "value": 5,  "uses": 3},
    "🍣 Суши":   {"price": 200, "description": "Удача +10% в казино на 5 игр",  "effect": "luck", "value": 10, "uses": 5},
    "🍰 Торт":   {"price": 500, "description": "Удача +20% в казино на 10 игр", "effect": "luck", "value": 20, "uses": 10},
}

BUSINESS_MAX_LEVEL = 10
BUSINESS_UPGRADE_COST = 0.5
BUSINESS_UPGRADE_BONUS = 0.25

SELL_PERCENT = 80

CASINO_MIN_BET = 10
CASINO_MAX_BET = 10000
CASINO_GAMES = {
    "dice":  {"name": "🎲 Кости",   "chance": 0.45, "multiplier": 2.0},
    "coin":  {"name": "🪙 Монетка", "chance": 0.48, "multiplier": 2.0},
    "darts": {"name": "🎯 Дартс",   "chance": 0.40, "multiplier": 2.5},
    "cards": {"name": "🃏 Карты",   "chance": 0.45, "multiplier": 2.0},
    "mines": {"name": "💎 Мины",    "chance": 0.50, "multiplier": 1.8},
    "slots": {"name": "🎰 Слоты",   "chance": 0.30, "multiplier": 3.0},
}

SUGGEST_COOLDOWN = 300
SUGGEST_MAX_LENGTH = 500

REFERRAL_BONUS_INVITER = 500
REFERRAL_BONUS_NEW = 200

DUEL_MIN_BET = 50
DUEL_MAX_BET = 50000

MIN_BANK_DEPOSIT = 100
BANK_CREATE_PRICE = 50000
BANK_INTEREST_DEFAULT = 5
BANK_INTEREST_MIN = 1
BANK_INTEREST_MAX = 20
BANK_CLOSE_REFUND = 50

LOAN_MIN = 100
LOAN_MAX = 100000
LOAN_INTEREST = 10
LOAN_DURATION = 86400
LOAN_PENALTY = 20

LOTTERY_TICKET_PRICE = 100
LOTTERY_MIN_PLAYERS = 2