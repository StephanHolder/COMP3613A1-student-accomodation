from datetime import date

from app.models.review import Review
from app.models.user import User
from app.repositories.review import ReviewRepository


class ReviewService:
    def __init__(self, review_repo: ReviewRepository):
        self.review_repo = review_repo

    def get_for_submission(self, student: User, booking_id: int):
        self._require_student(student)
        booking = self.review_repo.get_booking(booking_id)
        if booking is None:
            raise ValueError("Booking not found.")
        if booking.student_id != student.id:
            raise ValueError("You are not the student on this booking.")
        if booking.status != "Completed":
            raise ValueError("Reviews can only be submitted for completed stays.")
        if self.review_repo.get_for_booking(booking_id) is not None:
            raise ValueError("A review has already been submitted for this booking.")
        listing = self.review_repo.get_listing(booking.listing_id)
        if listing is None:
            raise ValueError("Listing not found for this booking.")
        return booking, listing

    def get_listing_reviews(
        self, listing_id: int, page: int, limit: int
    ):
        if page < 1 or limit < 1:
            raise ValueError("Page and page size must be positive.")
        return self.review_repo.get_for_listing(listing_id, page, limit)

    def submit_review(
        self,
        student: User,
        booking_id: int,
        rating: int,
        comment: str,
    ) -> Review:
        booking, listing = self.get_for_submission(student, booking_id)
        if rating < 1 or rating > 5:
            raise ValueError("Rating must be between 1 and 5.")
        text = comment.strip()
        if not text:
            raise ValueError("Written review must be provided.")
        review = Review(
            booking_id=booking.id,
            student_id=student.id,
            listing_id=listing.id,
            rating=rating,
            comment=text,
            review_date=date.today(),
        )
        return self.review_repo.create(review)

    @staticmethod
    def _require_student(student: User) -> None:
        if student.id is None or student.role != "regular_user":
            raise ValueError("Only a registered student can submit a review.")
