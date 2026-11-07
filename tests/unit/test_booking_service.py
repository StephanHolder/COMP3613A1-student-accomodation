"""BookingService rules: payment, move-out notice, completion, access."""

from datetime import date
from decimal import Decimal

import pytest

from app.services.booking_service import BookingService
from app.services.errors import ConflictError, ForbiddenError, NotFoundError


@pytest.fixture()
def service(booking_repo):
    return BookingService(booking_repo)


@pytest.fixture()
def awaiting(service, booking, listing):
    booking.status = "Awaiting Payment"
    service.booking_repo.get_by_id.return_value = booking
    service.booking_repo.get_listing.return_value = listing
    return booking


class TestPayment:
    def test_total_is_rent_plus_security_fee(self, service, student, awaiting, listing):
        _booking, _listing, total = service.get_for_payment(student, 5)
        assert total == listing.price + listing.security_fee == Decimal("3000")

    def test_payment_records_amount_method_and_paid_flag(self, service, student, awaiting):
        payment = service.submit_payment(student, 5, " card ")
        assert payment.paid is True
        assert payment.type == "card"
        assert payment.amount == Decimal("3000")
        assert payment.booking_id == 5
        assert payment.student_id == student.id
        assert payment.payment_date == date.today()

    def test_payment_confirms_through_the_repository(self, service, student, awaiting):
        service.submit_payment(student, 5, "cash")
        service.booking_repo.confirm_payment.assert_called_once()

    def test_blank_method_is_rejected(self, service, student, awaiting):
        with pytest.raises(ValueError, match="method"):
            service.submit_payment(student, 5, "  ")
        service.booking_repo.confirm_payment.assert_not_called()

    def test_only_students_pay(self, service, landlord):
        with pytest.raises(ForbiddenError):
            service.get_for_payment(landlord, 5)

    def test_unknown_booking(self, service, student):
        service.booking_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            service.get_for_payment(student, 5)

    def test_only_the_booked_student_pays(self, service, other_student, awaiting):
        with pytest.raises(ForbiddenError, match="student on this booking"):
            service.get_for_payment(other_student, 5)

    def test_cannot_pay_twice(self, service, student, booking):
        booking.status = "Confirmed"
        service.booking_repo.get_by_id.return_value = booking
        with pytest.raises(ConflictError, match="awaiting payment"):
            service.get_for_payment(student, 5)

    def test_missing_listing(self, service, student, awaiting):
        service.booking_repo.get_listing.return_value = None
        with pytest.raises(NotFoundError):
            service.get_for_payment(student, 5)


class TestMoveOutNotice:
    @pytest.fixture(autouse=True)
    def _confirmed(self, service, booking):
        booking.status = "Confirmed"
        service.booking_repo.get_by_id.return_value = booking

    def test_notice_sets_date_and_status(self, service, student):
        result = service.submit_move_out_notice(student, 5, date(2027, 6, 1))
        assert result.status == "Notice Given"
        assert result.move_out_date == date(2027, 6, 1)

    def test_move_out_must_be_after_start(self, service, student):
        with pytest.raises(ValueError, match="after"):
            service.submit_move_out_notice(student, 5, date(2027, 1, 10))

    def test_only_confirmed_bookings(self, service, student, booking):
        booking.status = "Awaiting Payment"
        with pytest.raises(ConflictError, match="confirmed"):
            service.submit_move_out_notice(student, 5, date(2027, 6, 1))

    def test_only_the_booked_student(self, service, other_student):
        with pytest.raises(ForbiddenError):
            service.submit_move_out_notice(other_student, 5, date(2027, 6, 1))

    def test_landlords_cannot_give_notice(self, service, landlord):
        with pytest.raises(ForbiddenError):
            service.submit_move_out_notice(landlord, 5, date(2027, 6, 1))

    def test_unknown_booking(self, service, student):
        service.booking_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            service.submit_move_out_notice(student, 5, date(2027, 6, 1))


class TestCompleteBooking:
    @pytest.fixture(autouse=True)
    def _notice_given(self, service, booking, listing, application):
        booking.status = "Notice Given"
        listing.availability = False
        application.status = "Accepted"
        service.booking_repo.get_by_id.return_value = booking
        service.booking_repo.get_listing.return_value = listing
        service.booking_repo.get_application.return_value = application

    def test_completion_frees_the_listing_and_closes_the_application(
        self, service, landlord, listing, application
    ):
        result = service.complete_booking(landlord, 5)
        assert result.status == "Completed"
        assert listing.availability is True
        assert application.status == "Completed"

    def test_only_after_notice_given(self, service, landlord, booking):
        booking.status = "Confirmed"
        with pytest.raises(ConflictError, match="move-out notice"):
            service.complete_booking(landlord, 5)

    def test_only_the_listing_owner(self, service, other_landlord):
        with pytest.raises(ForbiddenError, match="own"):
            service.complete_booking(other_landlord, 5)

    def test_students_cannot_complete(self, service, student):
        with pytest.raises(ForbiddenError):
            service.complete_booking(student, 5)

    def test_unknown_booking(self, service, landlord):
        service.booking_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            service.complete_booking(landlord, 5)


class TestGetBooking:
    @pytest.fixture(autouse=True)
    def _wire(self, service, booking, listing):
        service.booking_repo.get_by_id.return_value = booking
        service.booking_repo.get_listing.return_value = listing

    def test_the_booked_student_can_view(self, service, student, booking):
        assert service.get_booking(student, 5) is booking

    def test_the_listing_owner_can_view(self, service, landlord, booking):
        assert service.get_booking(landlord, 5) is booking

    def test_other_users_cannot_view(self, service, other_student, other_landlord, admin):
        for outsider in (other_student, other_landlord, admin):
            with pytest.raises(ForbiddenError):
                service.get_booking(outsider, 5)

    def test_unknown_booking(self, service, student):
        service.booking_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            service.get_booking(student, 5)
