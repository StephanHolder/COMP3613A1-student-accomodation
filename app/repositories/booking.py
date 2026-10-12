import logging

from sqlmodel import Session, select

from app.models.application import Application
from app.models.booking import Booking
from app.models.listing import Listing
from app.models.payment import Payment

logger = logging.getLogger(__name__)


class BookingRepository:
    IN_PROGRESS_STATUSES = ("Awaiting Payment", "Confirmed", "Notice Given")

    def __init__(self, db: Session):
        self.db = db

    def get_in_progress_for_listing(self, listing_id: int) -> Booking | None:
        statement = (
            select(Booking)
            .where(
                Booking.listing_id == listing_id,
                Booking.status.in_(self.IN_PROGRESS_STATUSES),
            )
            .order_by(Booking.id.desc())
        )
        return self.db.exec(statement).first()

    def get_by_id(self, booking_id: int) -> Booking | None:
        return self.db.get(Booking, booking_id)

    def get_application(self, application_id: int) -> Application | None:
        return self.db.get(Application, application_id)

    def get_for_application(self, application_id: int) -> Booking | None:
        statement = select(Booking).where(Booking.application_id == application_id)
        return self.db.exec(statement).first()

    def get_listing(self, listing_id: int) -> Listing | None:
        return self.db.get(Listing, listing_id)

    def confirm_payment(
        self,
        booking: Booking,
        listing: Listing,
        payment: Payment,
    ) -> Payment:
        try:
            booking.status = "Confirmed"
            listing.availability = False
            self.db.add(payment)
            self.db.add(booking)
            self.db.add(listing)
            self.db.commit()
            self.db.refresh(payment)
            self.db.refresh(booking)
            self.db.refresh(listing)
            return payment
        except Exception:
            logger.exception("Failed to confirm booking payment")
            self.db.rollback()
            raise

    def save_status_change(
        self,
        booking: Booking,
        listing: Listing | None = None,
        application: Application | None = None,
    ) -> Booking:
        try:
            self.db.add(booking)
            if listing is not None:
                self.db.add(listing)
            if application is not None:
                self.db.add(application)
            self.db.commit()
            self.db.refresh(booking)
            return booking
        except Exception:
            logger.exception("Failed to save booking status change")
            self.db.rollback()
            raise

    def create_for_application(
        self, application: Application, booking: Booking
    ) -> Booking:
        try:
            self.db.add(application)
            self.db.add(booking)
            self.db.commit()
            self.db.refresh(application)
            self.db.refresh(booking)
            return booking
        except Exception:
            logger.exception("Failed to create a booking for an accepted application")
            self.db.rollback()
            raise
