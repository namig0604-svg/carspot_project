"""
Все модели собраны здесь, чтобы Base.metadata знал обо всех таблицах
перед вызовом create_all().
"""
from app.models.business import Business, BusinessFavorite, BusinessReview
from app.models.booking import BusinessBooking
from app.models.car import Car, CarLike
from app.models.chat import ChatMember, ChatMessage, ChatRoom
from app.models.club import Club, ClubFavorite, ClubMember
from app.models.coin_transaction import CoinTransaction
from app.models.comment import Comment
from app.models.event import Event, EventFavorite, EventParticipant
from app.models.friendship import Friendship
from app.models.forum import ForumReply, ForumTopic
from app.models.notification import DeviceToken, Notification
from app.models.payment import PremiumPayment
from app.models.photo import Photo, PhotoLike
from app.models.rating import EventRating, SpotRating, UserRating
from app.models.report import Report
from app.models.story import Story, StoryView
from app.models.user import PasswordResetToken, ProfileView, User, UserLike
from app.models.parking import ParkingSpot
from app.models.maintenance import MaintenanceRecord
from app.models.car_document import CarDocument
from app.models.car_expense import CarExpense
from app.models.hazard import RoadHazard, RoadHazardVote
from app.models.part_listing import PartListing
from app.models.ride_pool import RideOffer, RideBooking

__all__ = [
    "User",
    "Car",
    "Event",
    "EventParticipant",
    "EventFavorite",
    "Club",
    "ClubMember",
    "ClubFavorite",
    "ChatRoom",
    "ChatMember",
    "ChatMessage",
    "Comment",
    "Friendship",
    "ForumTopic",
    "ForumReply",
    "Notification",
    "DeviceToken",
    "PremiumPayment",
    "CoinTransaction",
    "Photo",
    "PhotoLike",
    "EventRating",
    "UserRating",
    "SpotRating",
    "Business",
    "BusinessReview",
    "BusinessFavorite",
    "BusinessBooking",
    "Report",
    "Story",
    "StoryView",
    "CarLike",
    "UserLike",
    "ProfileView",
    "PasswordResetToken",
    "ParkingSpot",
    "MaintenanceRecord",
    "CarDocument",
    "CarExpense",
    "RoadHazard",
    "RoadHazardVote",
    "PartListing",
    "RideOffer",
    "RideBooking",
]

