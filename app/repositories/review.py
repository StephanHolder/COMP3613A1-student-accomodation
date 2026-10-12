import logging

from sqlmodel import Session, func, select

from app.models.booking import Booking
from app.models.listing import Listing
from app.models.review import Review
from app.models.user import User
from app.utilities.pagination import Pagination

logger = logging.getLogger(__name__)


class ReviewRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_booking(self, booking_id: int) -> Booking | None:
        return self.db.get(Booking, booking_id)

    def get_listing(self, listing_id: int) -> Listing | None:
        return self.db.get(Listing, listing_id)

    def get_for_booking(self, booking_id: int) -> Review | None:
        statement = select(Review).where(Review.booking_id == booking_id)
        return self.db.exec(statement).first()

    def get_for_listing(
        self, listing_id: int, page: int, limit: int
    ) -> tuple[list[tuple[Review, User]], Pagination, float | None]:
        total_count = self.db.exec(
            select(func.count()).select_from(Review).where(
                Review.listing_id == listing_id
            )
        ).one()
        pagination = Pagination(
            total_count=total_count,
            current_page=page,
            limit=limit,
        )
        safe_page = min(pagination.page, max(pagination.total_pages, 1))
        pagination = Pagination(
            total_count=total_count,
            current_page=safe_page,
            limit=limit,
        )
        statement = (
            select(Review, User)
            .join(User, Review.student_id == User.id)
            .where(Review.listing_id == listing_id)
            .order_by(Review.review_date.desc(), Review.id.desc())
            .offset((pagination.page - 1) * limit)
            .limit(limit)
        )
        reviews = list(self.db.exec(statement).all())
        average = self.db.exec(
            select(func.avg(Review.rating)).where(Review.listing_id == listing_id)
        ).one()
        if average is not None:
            average = float(average)
        return reviews, pagination, average

    def create(self, review: Review) -> Review:
        try:
            self.db.add(review)
            self.db.commit()
            self.db.refresh(review)
            return review
        except Exception:
            logger.exception("Failed to save review")
            self.db.rollback()
            raise
