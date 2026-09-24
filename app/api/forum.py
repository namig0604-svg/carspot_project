"""
Forum: kategorii temy (fiksirovanny nabor FORUM_CATEGORIES), spisok/sozdanie
tem, prosmotr temy s otvetami, dobavlenie otveta.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import Pagination, get_current_active_user
from app.models.base import utcnow
from app.models.forum import FORUM_CATEGORIES, ForumReply, ForumTopic
from app.models.user import User
from app.schemas.forum import (
    ForumCategoryCount,
    ForumReplyCreate,
    ForumReplyOut,
    ForumTopicCreate,
    ForumTopicDetail,
    ForumTopicListResponse,
    ForumTopicOut,
)
from app.schemas.user import UserPublic
from app.services import notify, users_by_ids

router = APIRouter()


@router.get(
    "/categories",
    response_model=List[ForumCategoryCount],
    summary="Kategorii foruma so schetchikom tem",
)
def list_categories(
    country: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(ForumTopic.category, func.count(ForumTopic.id)).filter(
        ForumTopic.is_active.is_(True)
    )
    if country:
        query = query.filter(ForumTopic.country == country)
    counts = dict(query.group_by(ForumTopic.category).all())
    return [
        ForumCategoryCount(category=c, topics_count=counts.get(c, 0))
        for c in FORUM_CATEGORIES
    ]


@router.get("/topics", response_model=ForumTopicListResponse, summary="Spisok tem")
def list_topics(
    category: Optional[str] = None,
    country: Optional[str] = None,
    search: Optional[str] = None,
    page: Pagination = Depends(),
    db: Session = Depends(get_db),
):
    query = db.query(ForumTopic).filter(ForumTopic.is_active.is_(True))
    if category:
        if category not in FORUM_CATEGORIES:
            raise HTTPException(status_code=400, detail=f"category dolzhen byt odnim iz: {', '.join(FORUM_CATEGORIES)}")
        query = query.filter(ForumTopic.category == category)
    if country:
        query = query.filter(ForumTopic.country == country)
    if search:
        like = f"%{search.strip()}%"
        query = query.filter(ForumTopic.title.ilike(like))

    total = query.count()
    rows = (
        query.order_by(ForumTopic.created_at.desc())
        .offset(page.offset)
        .limit(page.limit)
        .all()
    )

    user_map = users_by_ids(db, [r.author_id for r in rows])
    items = []
    for r in rows:
        item = ForumTopicOut.model_validate(r)
        author = user_map.get(r.author_id)
        if author:
            item.author = UserPublic.model_validate(author)
        items.append(item)

    return ForumTopicListResponse(total=total, limit=page.limit, offset=page.offset, items=items)


@router.post("/topics", response_model=ForumTopicOut, status_code=201, summary="Sozdat temu")
def create_topic(
    payload: ForumTopicCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    topic = ForumTopic(
        category=payload.category,
        country=payload.country,
        author_id=current_user.id,
        title=payload.title,
        body=payload.body,
    )
    db.add(topic)
    db.commit()
    db.refresh(topic)

    out = ForumTopicOut.model_validate(topic)
    out.author = UserPublic.model_validate(current_user)
    return out


@router.get("/topics/{topic_id}", response_model=ForumTopicDetail, summary="Tema s otvetami")
def get_topic(
    topic_id: str,
    db: Session = Depends(get_db),
):
    topic = db.query(ForumTopic).filter(ForumTopic.id == topic_id, ForumTopic.is_active.is_(True)).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Tema ne naydena")

    replies = (
        db.query(ForumReply)
        .filter(ForumReply.topic_id == topic_id, ForumReply.is_deleted.is_(False))
        .order_by(ForumReply.created_at.asc())
        .limit(500)
        .all()
    )

    author_ids = [topic.author_id] + [r.author_id for r in replies]
    user_map = users_by_ids(db, author_ids)

    out = ForumTopicDetail.model_validate(topic)
    author = user_map.get(topic.author_id)
    if author:
        out.author = UserPublic.model_validate(author)

    out.replies = []
    for r in replies:
        reply_out = ForumReplyOut.model_validate(r)
        reply_author = user_map.get(r.author_id)
        if reply_author:
            reply_out.author = UserPublic.model_validate(reply_author)
        out.replies.append(reply_out)

    return out


@router.post(
    "/topics/{topic_id}/replies",
    response_model=ForumReplyOut,
    status_code=201,
    summary="Otvetit v teme",
)
def create_reply(
    topic_id: str,
    payload: ForumReplyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    topic = db.query(ForumTopic).filter(ForumTopic.id == topic_id, ForumTopic.is_active.is_(True)).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Tema ne naydena")

    reply = ForumReply(topic_id=topic_id, author_id=current_user.id, body=payload.body)
    db.add(reply)

    topic.replies_count = (topic.replies_count or 0) + 1
    topic.updated_at = utcnow()

    db.flush()

    if topic.author_id != current_user.id:
        notify(
            db,
            user_id=topic.author_id,
            type="forum_reply",
            actor_id=current_user.id,
            target_type="forum_topic",
            target_id=topic_id,
            message=f"{current_user.username} otvetil(a) v teme «{topic.title}»",
        )

    db.commit()
    db.refresh(reply)

    out = ForumReplyOut.model_validate(reply)
    out.author = UserPublic.model_validate(current_user)
    return out
