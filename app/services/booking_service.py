from datetime import date
from decimal import Decimal

from app.models.payment import Payment
from app.models.user import User
from app.repositories.booking import BookingRepository
from app.services.errors import ConflictError, ForbiddenError, NotFoundError


class BookingService:
    def __init__(self, booking_repo: BookingRepository):
        self.booking_repo = booking_repo

    def get_booking(self, user: User, booking_id: int):
        """Return a booking to its student or to the landlord who owns the listing."""
        booking = self.booking_repo.get_by_id(booking_id)
        if booking is None:
            raise NotFoundError("Booking not found.")
        if user.role == "regular_user" and booking.student_id == user.id:
            return booking
        listing = self.booking_repo.get_listing(booking.listing_id)
        if user.role == "landlord" and listing is not None and listing.landlord_id == user.id:
            return booking
        raise ForbiddenError("You are not a party to this booking.")

    def get_for_payment(
        self, student: User, booking_id: int
    ):
        if student.id is None or student.role != "regular_user":
            raise ForbiddenError("Only a registered student can make a payment.")
        booking = self.booking_repo.get_by_id(booking_id)
        if booking is None:
            raise NotFoundError("Booking not found.")
        if booking.student_id != student.id:
            raise ForbiddenError("You are not the student on this booking.")
        if booking.status != "Awaiting Payment":
            raise ConflictError("This booking is not awaiting payment.")
        listing = self.booking_repo.get_listing(booking.listing_id)
        if listing is None:
            raise NotFoundError("Listing not found for this booking.")
        payment_total = listing.security_fee + listing.price
        return booking, listing, payment_total

    def submit_payment(
        self,
        student: User,
        booking_id: int,
        payment_method: str,
    ) -> Payment:
        booking, listing, payment_total = self.get_for_payment(
            student=student,
            booking_id=booking_id,
        )
        method = payment_method.strip()
        if not method:
            raise ValueError("Payment method must be provided.")
        payment = Payment(
            booking_id=booking.id,
            student_id=student.id,
            type=method,
            amount=Decimal(payment_total),
            paid=True,
            payment_date=date.today(),
        )
        return self.booking_repo.confirm_payment(booking, listing, payment)

    def submit_move_out_notice(
        self,
        student: User,
        booking_id: int,
        move_out_date: date,
    ):
        if student.id is None or student.role != "regular_user":
            raise ForbiddenError("Only a registered student can give move-out notice.")
        booking = self.booking_repo.get_by_id(booking_id)
        if booking is None:
            raise NotFoundError("Booking not found.")
        if booking.student_id != student.id:
            raise ForbiddenError("You are not the student on this booking.")
        if booking.status != "Confirmed":
            raise ConflictError("Move-out notice can only be given for confirmed bookings.")
        if move_out_date <= booking.start_date:
            raise ValueError("Move-out date must be after the booking start date.")
        booking.move_out_date = move_out_date
        booking.status = "Notice Given"
        return self.booking_repo.save_status_change(booking)

    def complete_booking(self, landlord: User, booking_id: int):
        if landlord.id is None or landlord.role != "landlord":
            raise ForbiddenError("Only a landlord can complete a booking.")
        booking = self.booking_repo.get_by_id(booking_id)
        if booking is None:
            raise NotFoundError("Booking not found.")
        listing = self.booking_repo.get_listing(booking.listing_id)
        if listing is None:
            raise NotFoundError("Listing not found for this booking.")
        if listing.landlord_id != landlord.id:
            raise ForbiddenError("You do not own this booking's listing.")
        if booking.status != "Notice Given":
            raise ConflictError("Only bookings with move-out notice can be completed.")
        application = self.booking_repo.get_application(booking.application_id)
        if application is None:
            raise NotFoundError("Application not found for this booking.")
        booking.status = "Completed"
        application.status = "Completed"
        listing.availability = True
        return self.booking_repo.save_status_change(booking, listing, application)
