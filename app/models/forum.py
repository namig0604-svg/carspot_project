"""
Forum - temy po kategoriyam (fiksirovannyy nabor, kak EVENT_TYPES/
BUSINESS_CATEGORIES, otdelnoy tablicy net - kategorii ne redaktiruyutsya
polzovatelyami) i otvety v nih. Temu mozhno privyazat k strane (country) -
togda ona vidna tolko v etoy strane pri filtratsii na klientе; bez strany -
obshchaya tema, vidna vezde.
"""
from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, Text

from app.database import Base
from app.models.base import new_id, utcnow

FORUM_CATEGORIES = (
    "events",     # Vstrechi i sobytiya
    "tuning",     # Tyuning i zapchasti
    "questions",  # Voprosy i pomoshch
    "market",     # Kupit / Prodat
)


class ForumTopic(Base):
    __tablename__ = "forum_topics"

    id = Column(String(36), primary_key=True, default=new_id)
    category = Column(String(20), nullable=False, index=True)
    country = Column(String(2), nullable=True, index=True)
    author_id = Column(String(36), index=True, nullable=False)
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    replies_count = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=utcnow, nullable=False)


class ForumReply(Base):
    __tablename__ = "forum_replies"

    id = Column(String(36), primary_key=True, default=new_id)
    topic_id = Column(String(36), index=True, nullable=False)
    author_id = Column(String(36), index=True, nullable=False)
    body = Column(Text, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)


Index("ix_forum_topics_category_created", ForumTopic.category, ForumTopic.created_at)
Index("ix_forum_replies_topic_created", ForumReply.topic_id, ForumReply.created_at)
