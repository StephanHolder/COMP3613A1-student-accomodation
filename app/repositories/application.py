import logging

from sqlmodel import Session, func, select

from app.models.application import Application
from app.models.listing import Listing
from app.utilities.pagination import Pagination

logger = logging.getLogger(__name__)


class ApplicationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_active_for_student_listing(
        self, student_id: int, listing_id: int
    ) -> Application | None:
        statement = (
            select(Application)
            .where(
                Application.student_id == student_id,
                Application.listing_id == listing_id,
                Application.status.notin_(("Declined", "Completed")),
            )
            .order_by(Application.id.desc())
        )
        return self.db.exec(statement).first()

    def get_by_id(self, application_id: int) -> Application | None:
        return self.db.get(Application, application_id)

    def update(self, application: Application) -> Application:
        if application.id is None:
            raise ValueError("Cannot update an application without an ID.")
        existing = self.db.get(Application, application.id)
        if existing is None:
            raise ValueError("Application not found.")
        try:
            existing.student_name = application.student_name
            existing.student_age = application.student_age
            existing.purpose_of_stay = application.purpose_of_stay
            existing.status = application.status
            existing.decline_reason = application.decline_reason
            self.db.commit()
            self.db.refresh(existing)
            return existing
        except Exception:
            logger.exception("Failed to update application")
            self.db.rollback()
            raise

    def create(self, application: Application) -> Application:
        try:
            self.db.add(application)
            self.db.commit()
            self.db.refresh(application)
            return application
        except Exception:
            logger.exception("Failed to save application")
            self.db.rollback()
            raise

    def get_for_student(
        self, student_id: int, page: int, limit: int
    ) -> tuple[list[Application], Pagination]:
        # BEGIN STUDENT SNIPPET: query this student's applications and paginate them
        filters = Application.student_id == student_id
        total_count = self.db.exec(
            select(func.count()).select_from(Application).where(filters)
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
            select(Application)
            .where(filters)
            .order_by(Application.id.desc())
            .offset((pagination.page - 1) * limit)
            .limit(limit)
        )
        return list(self.db.exec(statement).all()), pagination
        # END STUDENT SNIPPET

    def get_for_landlord(
        self, landlord_id: int, page: int, limit: int
    ) -> tuple[list[Application], Pagination]:
        # BEGIN STUDENT SNIPPET: retrieve this landlord's applications with pagination
        filters = Listing.landlord_id == landlord_id
        total_count = self.db.exec(
            select(func.count())
            .select_from(Application)
            .join(Listing, Application.listing_id == Listing.id)
            .where(filters)
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
            select(Application)
            .join(Listing, Application.listing_id == Listing.id)
            .where(filters)
            .order_by(Application.id.desc())
            .offset((pagination.page - 1) * limit)
            .limit(limit)
        )
        return list(self.db.exec(statement).all()), pagination
        # END STUDENT SNIPPET
