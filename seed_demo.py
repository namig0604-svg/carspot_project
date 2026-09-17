"""
Наполняет базу демо-данными, чтобы было что смотреть в приложении.

Создаёт: 4 пользователей, 6 машин, 5 сходок в Тбилиси и Батуми,
2 клуба, участников, оценки и сообщения в чатах.

Запуск:
    python seed_demo.py

Логин любого демо-пользователя: пароль Demo12345
"""
import sys
from datetime import timedelta

from app.database import SessionLocal, init_db
from app.models.base import utcnow
from app.models.car import Car
from app.models.club import Club, ClubMember
from app.models.event import Event, EventParticipant
from app.models.rating import EventRating, UserRating
from app.models.user import User
from app.security import hash_password
from app.services import (
    add_room_member,
    get_or_create_club_room,
    get_or_create_event_room,
    recalc_event_rating,
    recalc_user_rating,
)

DEMO_PASSWORD = "Demo12345"

USERS = [
    ("namig", "namig@carspot.app", "Namig Nabiev", "Georgia", "Tbilisi", "Дрифт и JDM"),
    ("dato", "dato@carspot.app", "Dato Beridze", "Georgia", "Tbilisi", "Stance culture"),
    ("aysel", "aysel@carspot.app", "Aysel Mammadova", "Azerbaijan", "Baku", "Люблю немецкий автопром"),
    ("giorgi", "giorgi@carspot.app", "Giorgi Kapanadze", "Georgia", "Batumi", "Offroad и экспедиции"),
]

CARS = [
    # (индекс владельца, марка, модель, год, двигатель, л.с., привод, цвет, тюнинг)
    (0, "Nissan", "Silvia S15", 1999, "SR20DET", 450, "RWD", "Midnight Purple",
     "Garrett GT2871R, HKS coilovers, Work Meister S1, сварной квайф"),
    (0, "Toyota", "Supra MK4", 1997, "2JZ-GTE", 700, "RWD", "Белый",
     "Precision 6266, кованый низ, Motec M150"),
    (1, "BMW", "E36 Coupe", 1995, "M50B28 Turbo", 420, "RWD", "Чёрный",
     "Air Lift Performance, BBS RS, кастомный впуск"),
    (1, "Honda", "Civic EK9", 1998, "B18C", 220, "FWD", "Championship White",
     "Spoon Sports, ITB, Volk TE37"),
    (2, "Mercedes-Benz", "W124 500E", 1992, "M119 5.0 V8", 326, "RWD", "Серебристый",
     "Полная реставрация, Bilstein B6"),
    (3, "Toyota", "Land Cruiser 80", 1995, "1HD-FT", 170, "AWD", "Песочный",
     "Лифт 4\", лебёдка, шноркель, BFGoodrich KM3"),
]

EVENTS = [
    # (создатель, название, тип, город, широта, долгота, через сколько дней, место)
    (0, "Ночная сходка на Ваке", "meetup", "Tbilisi", 41.7151, 44.7671, 5, "Vake Park"),
    (1, "Stance Meet у Динамо", "show", "Tbilisi", 41.7280, 44.7900, 9, "Dinamo Arena"),
    (0, "Дрифт-тренировка в Рустави", "drift", "Rustavi", 41.5495, 45.0000, 12, "Rustavi Motorpark"),
    (3, "Офф-роуд выезд в Гонио", "offroad", "Batumi", 41.5730, 41.5700, 16, "Gonio"),
    (2, "Утренние покатушки по Баку", "cruise", "Baku", 40.4093, 49.8671, 20, "Приморский бульвар"),
]


def main() -> int:
    init_db()
    db = SessionLocal()

    try:
        if db.query(User).filter(User.username == "namig").first():
            print("Демо-данные уже загружены. Сначала выполните reset_db.py")
            return 1

        print("Создаю пользователей...")
        users = []
        for username, email, full_name, country, city, bio in USERS:
            user = User(
                username=username,
                email=email,
                hashed_password=hash_password(DEMO_PASSWORD),
                full_name=full_name,
                country=country,
                city=city,
                bio=bio,
                is_verified=True,
            )
            db.add(user)
            users.append(user)
        db.flush()

        print("Наполняю гаражи...")
        for owner_idx, make, model, year, engine, power, drivetrain, color, mods in CARS:
            owner = users[owner_idx]
            is_first = owner.cars_count == 0
            db.add(
                Car(
                    user_id=owner.id,
                    make=make,
                    model=model,
                    year=year,
                    engine=engine,
                    power_hp=power,
                    drivetrain=drivetrain,
                    transmission="manual",
                    fuel_type="petrol",
                    color=color,
                    mods=mods,
                    is_primary=is_first,
                )
            )
            owner.cars_count += 1
        db.flush()

        print("Создаю сходки...")
        events = []
        now = utcnow()
        for creator_idx, title, event_type, city, lat, lon, days, place in EVENTS:
            creator = users[creator_idx]
            event = Event(
                creator_id=creator.id,
                title=title,
                description=f"Встречаемся в месте «{place}». Приезжайте на своих машинах.",
                event_type=event_type,
                country="Georgia" if city != "Baku" else "Azerbaijan",
                city=city,
                location_name=place,
                latitude=lat,
                longitude=lon,
                event_date=now + timedelta(days=days),
                event_time="20:00",
                duration_minutes=180,
            )
            db.add(event)
            db.flush()

            db.add(EventParticipant(event_id=event.id, user_id=creator.id, status="going"))
            event.participants_count = 1
            creator.events_created += 1
            creator.events_attended += 1

            get_or_create_event_room(db, event)
            events.append(event)
        db.flush()

        print("Добавляю участников...")
        joins = [(0, 1), (0, 2), (0, 3), (1, 0), (1, 3), (2, 1), (3, 0), (4, 1)]
        for event_idx, user_idx in joins:
            event, user = events[event_idx], users[user_idx]
            db.add(EventParticipant(event_id=event.id, user_id=user.id, status="going"))
            event.participants_count += 1
            user.events_attended += 1

            room = get_or_create_event_room(db, event)
            add_room_member(db, room.id, user.id)
        db.flush()

        print("Создаю клубы...")
        club1 = Club(
            owner_id=users[0].id,
            name="Tbilisi JDM Crew",
            description="Клуб любителей японских автомобилей в Тбилиси",
            country="Georgia",
            city="Tbilisi",
            tags="JDM,Drift,Turbo",
            is_public=True,
            members_count=1,
        )
        club2 = Club(
            owner_id=users[3].id,
            name="Caucasus Offroad",
            description="Экспедиции по горам Кавказа",
            country="Georgia",
            city="Batumi",
            tags="Offroad,4x4,Expedition",
            is_public=True,
            members_count=1,
        )
        db.add_all([club1, club2])
        db.flush()

        for club, owner_idx in ((club1, 0), (club2, 3)):
            db.add(
                ClubMember(
                    club_id=club.id,
                    user_id=users[owner_idx].id,
                    role="owner",
                    status="approved",
                )
            )
            get_or_create_club_room(db, club.id, club.name, users[owner_idx].id)
        db.flush()

        for club, member_idx in ((club1, 1), (club1, 2), (club2, 0)):
            db.add(
                ClubMember(
                    club_id=club.id,
                    user_id=users[member_idx].id,
                    role="member",
                    status="approved",
                )
            )
            club.members_count += 1
            room = get_or_create_club_room(db, club.id, club.name, club.owner_id)
            add_room_member(db, room.id, users[member_idx].id)
        db.flush()

        print("Ставлю оценки...")
        for event_idx, user_idx, value, review in (
            (0, 1, 5, "Отличная сходка, много интересных машин"),
            (0, 2, 4, "Хорошо, но мало места для парковки"),
            (1, 0, 5, "Организация на высоте"),
        ):
            db.add(
                EventRating(
                    event_id=events[event_idx].id,
                    user_id=users[user_idx].id,
                    rating=value,
                    review=review,
                    atmosphere_rating=value,
                    organization_rating=value,
                    location_rating=value,
                )
            )
        db.flush()
        for event in events:
            recalc_event_rating(db, event.id)

        for rated_idx, rater_idx, value, review in (
            (0, 1, 5, "Отличный организатор, всё чётко"),
            (0, 2, 5, "Рекомендую"),
            (1, 0, 4, "Приятный человек"),
        ):
            db.add(
                UserRating(
                    rated_user_id=users[rated_idx].id,
                    rater_user_id=users[rater_idx].id,
                    rating=value,
                    review=review,
                )
            )
        db.flush()
        for user in users:
            recalc_user_rating(db, user.id)

        db.commit()

        print("\nГотово. Демо-данные загружены:")
        print(f"  пользователей: {len(users)}")
        print(f"  машин:         {len(CARS)}")
        print(f"  сходок:        {len(events)}")
        print("  клубов:        2")
        print(f"\nВход в любой аккаунт — пароль: {DEMO_PASSWORD}")
        print("Логины: " + ", ".join(u[0] for u in USERS))
        return 0

    except Exception as exc:  # noqa: BLE001
        db.rollback()
        print(f"Ошибка: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
