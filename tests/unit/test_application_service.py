"""ApplicationService rules: apply, request details, submit details, accept/decline."""

from datetime import date

import pytest

from app.models.booking import Booking
from app.services.application_service import ApplicationService
from app.services.errors import ConflictError, ForbiddenError, NotFoundError

START = date(2027, 1, 10)


@pytest.fixture()
def service(application_repo, listing_repo, booking_repo):
    return ApplicationService(application_repo, listing_repo, booking_repo)


class TestSubmitApplication:
    def test_creates_an_applied_application(self, service, student, listing):
        service.listing_repo.get_by_id.return_value = listing
        service.application_repo.get_active_for_student_listing.return_value = None
        result = service.submit_application(student, 1, START)
        assert result.status == "Applied"
        assert result.student_id == student.id
        assert result.listing_id == 1
        assert result.preferred_start_date == START

    def test_only_students_can_apply(self, service, landlord):
        with pytest.raises(ForbiddenError):
            service.submit_application(landlord, 1, START)

    def test_unknown_listing_is_not_found(self, service, student):
        service.listing_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            service.submit_application(student, 1, START)

    def test_listing_must_be_verified(self, service, student, listing):
        listing.verification_status = "Pending"
        service.listing_repo.get_by_id.return_value = listing
        with pytest.raises(ConflictError, match="verified"):
            service.submit_application(student, 1, START)

    def test_listing_must_be_available(self, service, student, listing):
        listing.availability = False
        service.listing_repo.get_by_id.return_value = listing
        with pytest.raises(ConflictError, match="available"):
            service.submit_application(student, 1, START)

    def test_cannot_apply_to_own_listing(self, service, student, listing):
        listing.landlord_id = student.id
        service.listing_repo.get_by_id.return_value = listing
        with pytest.raises(ForbiddenError, match="own listing"):
            service.submit_application(student, 1, START)

    def test_active_duplicate_is_blocked(self, service, student, listing, application):
        service.listing_repo.get_by_id.return_value = listing
        service.application_repo.get_active_for_student_listing.return_value = application
        with pytest.raises(ConflictError, match="active application"):
            service.submit_application(student, 1, START)


class TestStudentAndLandlordLists:
    def test_student_list_is_for_students_only(self, service, landlord):
        with pytest.raises(PermissionError):
            service.get_student_applications(landlord, page=1, limit=5)

    def test_student_list_rejects_bad_paging(self, service, student):
        with pytest.raises(ValueError):
            service.get_student_applications(student, page=0, limit=5)

    def test_landlord_list_is_for_landlords_only(self, service, student):
        with pytest.raises(ForbiddenError):
            service.get_landlord_applications(student, page=1, limit=5)

    def test_landlord_list_delegates_to_repository(self, service, landlord):
        service.get_landlord_applications(landlord, page=2, limit=5)
        service.application_repo.get_for_landlord.assert_called_once_with(landlord.id, 2, 5)


class TestRequestDetails:
    def _wire(self, service, application, listing):
        service.application_repo.get_by_id.return_value = application
        service.listing_repo.get_by_id.return_value = listing

    def test_landlord_moves_applied_to_info_requested(
        self, service, landlord, application, listing
    ):
        self._wire(service, application, listing)
        assert service.request_details(landlord, 7).status == "Info Requested"

    def test_only_landlords(self, service, student):
        with pytest.raises(ForbiddenError):
            service.request_details(student, 7)

    def test_unknown_application(self, service, landlord):
        service.application_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            service.request_details(landlord, 7)

    def test_must_own_the_listing(self, service, other_landlord, application, listing):
        self._wire(service, application, listing)
        with pytest.raises(ForbiddenError, match="owner"):
            service.request_details(other_landlord, 7)

    def test_only_from_applied(self, service, landlord, application, listing):
        application.status = "Info Requested"
        self._wire(service, application, listing)
        with pytest.raises(ConflictError):
            service.request_details(landlord, 7)


class TestSubmitRequestedDetails:
    @pytest.fixture(autouse=True)
    def _requested(self, service, application):
        application.status = "Info Requested"
        service.application_repo.get_by_id.return_value = application

    def test_saves_details_and_moves_to_info_submitted(self, service, student):
        result = service.submit_requested_details(student, 7, " Ann ", "21", " Study ")
        assert result.status == "Info Submitted"
        assert (result.student_name, result.student_age, result.purpose_of_stay) == (
            "Ann",
            21,
            "Study",
        )

    def test_only_the_applicant_can_submit(self, service, other_student):
        with pytest.raises(ForbiddenError, match="owner"):
            service.submit_requested_details(other_student, 7, "Ann", "21", "Study")

    def test_only_when_info_was_requested(self, service, student, application):
        application.status = "Applied"
        with pytest.raises(ConflictError):
            service.submit_requested_details(student, 7, "Ann", "21", "Study")

    def test_unknown_application(self, service, student):
        service.application_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            service.submit_requested_details(student, 7, "Ann", "21", "Study")

    def test_name_is_required(self, service, student):
        with pytest.raises(ValueError, match="name"):
            service.submit_requested_details(student, 7, "  ", "21", "Study")

    @pytest.mark.parametrize("age", ["abc", "-3", "2.5", "", "1e2"])
    def test_age_must_be_digits(self, service, student, age):
        with pytest.raises(ValueError, match="digits"):
            service.submit_requested_details(student, 7, "Ann", age, "Study")

    def test_age_must_be_positive(self, service, student):
        with pytest.raises(ValueError, match="positive"):
            service.submit_requested_details(student, 7, "Ann", "0", "Study")

    def test_purpose_is_required(self, service, student):
        with pytest.raises(ValueError, match="Purpose"):
            service.submit_requested_details(student, 7, "Ann", "21", " ")


class TestDecideApplication:
    def _wire(self, service, application, listing, status):
        application.status = status
        service.application_repo.get_by_id.return_value = application
        service.listing_repo.get_by_id.return_value = listing
        service.booking_repo.get_in_progress_for_listing.return_value = None

    def test_accept_creates_a_booking_awaiting_payment(
        self, service, landlord, application, listing
    ):
        self._wire(service, application, listing, "Info Submitted")
        result = service.decide_application(landlord, 7, "Accepted")
        assert result.status == "Accepted"
        _app, booking = service.booking_repo.create_for_application.call_args.args
        assert isinstance(booking, Booking)
        assert booking.status == "Awaiting Payment"
        assert booking.start_date == application.preferred_start_date
        assert booking.student_id == application.student_id

    def test_accept_requires_info_submitted(self, service, landlord, application, listing):
        self._wire(service, application, listing, "Applied")
        with pytest.raises(ConflictError, match="Info Submitted"):
            service.decide_application(landlord, 7, "Accepted")
        service.booking_repo.create_for_application.assert_not_called()

    def test_accept_blocked_when_listing_unavailable(
        self, service, landlord, application, listing
    ):
        listing.availability = False
        self._wire(service, application, listing, "Info Submitted")
        with pytest.raises(ConflictError, match="available"):
            service.decide_application(landlord, 7, "Accepted")

    def test_accept_blocked_by_an_active_booking(
        self, service, landlord, application, listing, booking
    ):
        self._wire(service, application, listing, "Info Submitted")
        service.booking_repo.get_in_progress_for_listing.return_value = booking
        with pytest.raises(ConflictError, match="active booking"):
            service.decide_application(landlord, 7, "Accepted")

    @pytest.mark.parametrize("status", ["Applied", "Info Requested", "Info Submitted"])
    def test_decline_is_allowed_before_acceptance(
        self, service, landlord, application, listing, status
    ):
        self._wire(service, application, listing, status)
        result = service.decide_application(landlord, 7, "Declined", " Not a fit ")
        assert result.status == "Declined"
        assert result.decline_reason == "Not a fit"

    def test_decline_needs_a_reason(self, service, landlord, application, listing):
        self._wire(service, application, listing, "Applied")
        with pytest.raises(ValueError, match="reason"):
            service.decide_application(landlord, 7, "Declined", "")

    def test_cannot_decline_after_acceptance(self, service, landlord, application, listing):
        self._wire(service, application, listing, "Accepted")
        with pytest.raises(ConflictError):
            service.decide_application(landlord, 7, "Declined", "Changed mind")

    def test_decision_value_is_validated(self, service, landlord):
        with pytest.raises(ValueError, match="Accepted"):
            service.decide_application(landlord, 7, "Maybe")

    def test_only_landlords_decide(self, service, student):
        with pytest.raises(ForbiddenError):
            service.decide_application(student, 7, "Accepted")

    def test_only_the_listing_owner_decides(
        self, service, other_landlord, application, listing
    ):
        self._wire(service, application, listing, "Info Submitted")
        with pytest.raises(ForbiddenError, match="owner"):
            service.decide_application(other_landlord, 7, "Accepted")

    def test_unknown_application(self, service, landlord):
        service.application_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            service.decide_application(landlord, 7, "Accepted")
