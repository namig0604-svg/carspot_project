"""
Иерархия рангов администрации CarSpot — отдельно от User.is_admin.

is_admin остаётся как раньше: общий флаг "есть какие-то права админа",
которым уже гейтятся все существующие ручки /api/admin/* (модерация жалоб,
бан пользователей, импорт автосервисов и т.д.) — не трогаем, чтобы не
сломать то, что уже работает.

admin_rank — более тонкая иерархия поверх него, нужна для чувствительных
операций, которые нельзя доверять любому модератору: ручная выдача монет
и назначение рангов другим. Порядок по возрастанию прав:
  модератор < администратор < тех.администратор < разработчик.
Любой назначенный ранг автоматически включает is_admin=True (см.
app.api.admin.set_admin_rank), но не наоборот — старый is_admin=True без
явного ранга НЕ даёт прав на выдачу монет/рангов.
"""
RANK_MODERATOR = "moderator"
RANK_ADMINISTRATOR = "administrator"
RANK_TECH_ADMIN = "tech_admin"
RANK_DEVELOPER = "developer"

RANK_ORDER = {
    RANK_MODERATOR: 1,
    RANK_ADMINISTRATOR: 2,
    RANK_TECH_ADMIN: 3,
    RANK_DEVELOPER: 4,
}

ALL_RANKS = list(RANK_ORDER.keys())

RANK_TITLES_RU = {
    RANK_MODERATOR: "Модератор",
    RANK_ADMINISTRATOR: "Администратор",
    RANK_TECH_ADMIN: "Тех.администратор",
    RANK_DEVELOPER: "Разработчик",
}


def rank_level(user) -> int:
    """
    0, если явного ранга нет вовсе — сознательно, даже если у пользователя
    старый is_admin=True: право выдавать монеты/ранги требует ЯВНО
    назначенного ранга через app.api.admin.set_admin_rank, а не любого
    is_admin (иначе давние модераторы, отмеченные просто is_admin=True без
    ранга, неожиданно получили бы новые чувствительные права).
    """
    return RANK_ORDER.get(getattr(user, "admin_rank", None), 0)
