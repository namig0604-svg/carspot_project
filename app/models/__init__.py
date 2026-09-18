"""
Все модели собраны здесь, чтобы Base.metadata знал обо всех таблицах
перед вызовом create_all().
"""
from app.models.business import Business, BusinessFavorite, BusinessReview
from app.models.car import Car
from app.models.chat import ChatMember, ChatMessage, ChatRoom
from app.models.club import Club, ClubMember
from app.models.event import Event, EventParticipant
from app.models.photo import Photo, PhotoLike
from app.models.rating import EventRating, SpotRating, UserRating
from app.models.user import User

__all__ = [
    "User",
    "Car",
    "Event",
    "EventParticipant",
    "Club",
    "ClubMember",
    "ChatRoom",
    "ChatMember",
    "ChatMessage",
    "Photo",
    "PhotoLike",
    "EventRating",
    "UserRating",
    "SpotRating",
    "Business",
    "BusinessReview",
    "BusinessFavorite",
]
