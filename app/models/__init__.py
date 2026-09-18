"""
Все модели собраны здесь, чтобы Base.metadata знал обо всех таблицах
перед вызовом create_all().
"""
from app.models.business import Business, BusinessFavorite, BusinessReview
from app.models.car import Car, CarLike
from app.models.chat import ChatMember, ChatMessage, ChatRoom
from app.models.club import Club, ClubMember
from app.models.event import Event, EventParticipant
from app.models.friendship import Friendship
from app.models.notification import Notification
from app.models.payment import PremiumPayment
from app.models.photo import Photo, PhotoLike
from app.models.rating import EventRating, SpotRating, UserRating
from app.models.report import Report
from app.models.user import ProfileView, User, UserLike

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
    "Friendship",
    "Notification",
    "PremiumPayment",
    "Photo",
    "PhotoLike",
    "EventRating",
    "UserRating",
    "SpotRating",
    "Business",
    "BusinessReview",
    "BusinessFavorite",
    "Report",
    "CarLike",
    "UserLike",
    "ProfileView",
]
