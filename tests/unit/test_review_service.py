"""ReviewService rules: one review per completed booking, rating range, paging."""

from datetime import date

import pytest

from app.services.errors import ConflictError, ForbiddenError, NotFoundError
from app.services.review_service import ReviewService


@pytest.fixture()
def service(review_repo):
    return ReviewService(review_repo)


@pytest.fixture()
def completed(service, booking, listing):
    booking.status = "Completed"
    service.review_repo.get_booking.return_value = booking
    service.review_repo.get_for_booking.return_value = None
    service.review_repo.get_listing.return_value = listing
    return booking


class TestSubmitReview:
    def test_creates_a_review_for_the_booking(self, service, student, completed):
        review = service.submit_review(student, 5, rating=4, comment=" Nice and quiet ")
        assert review.booking_id == 5
        assert review.listing_id == 1
        assert review.student_id == student.id
        assert review.rating == 4
        assert review.comment == "Nice and quiet"
        assert review.review_date == date.today()

    @pytest.mark.parametrize("rating", [1, 5])
    def test_boundary_ratings_are_accepted(self, service, student, completed, rating):
        assert service.submit_review(student, 5, rating, "ok").rating == rating

    @pytest.mark.parametrize("rating", [0, 6, -1])
    def test_rating_must_be_between_one_and_five(self, service, student, completed, rating):
        with pytest.raises(ValueError, match="between 1 and 5"):
            service.submit_review(student, 5, rating, "ok")
        service.review_repo.create.assert_not_called()

    def test_comment_is_required(self, service, student, completed):
        with pytest.raises(ValueError, match="Written review"):
            service.submit_review(student, 5, 4, "   ")

    def test_only_after_the_stay_is_completed(self, service, student, booking):
        booking.status = "Confirmed"
        service.review_repo.get_booking.return_value = booking
        with pytest.raises(ConflictError, match="completed"):
            service.submit_review(student, 5, 4, "ok")

    def test_one_review_per_booking(self, service, student, completed):
        service.review_repo.get_for_booking.return_value = object()
        with pytest.raises(ConflictError, match="already"):
            service.submit_review(student, 5, 4, "ok")

    def test_only_the_booked_student_can_review(self, service, other_student, completed):
        with pytest.raises(ForbiddenError, match="student on this booking"):
            service.submit_review(other_student, 5, 4, "ok")

    def test_landlords_cannot_review(self, service, landlord):
        with pytest.raises(ForbiddenError):
            service.submit_review(landlord, 5, 4, "ok")

    def test_unknown_booking(self, service, student):
        service.review_repo.get_booking.return_value = None
        with pytest.raises(NotFoundError):
            service.submit_review(student, 5, 4, "ok")

    def test_missing_listing(self, service, student, completed):
        service.review_repo.get_listing.return_value = None
        with pytest.raises(NotFoundError):
            service.submit_review(student, 5, 4, "ok")


class TestListingReviews:
    def test_delegates_paging_to_the_repository(self, service):
        service.get_listing_reviews(3, page=2, limit=5)
        service.review_repo.get_for_listing.assert_called_once_with(3, 2, 5)

    @pytest.mark.parametrize("page,limit", [(0, 5), (1, 0), (-1, 5)])
    def test_rejects_non_positive_paging(self, service, page, limit):
        with pytest.raises(ValueError):
            service.get_listing_reviews(3, page=page, limit=limit)
