"""Repositories against a real (in-memory) database."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.payment import Payment
from app.models.review import Review
from app.repositories.application import ApplicationRepository
from app.repositories.booking import BookingRepository
from app.repositories.listing import ListingRepository
from app.repositories.review import ReviewRepository
from app.repositories.user import UserRepository
from app.schemas.user import RegularUserCreate


class TestListingRepository:
    def test_search_returns_only_verified_newest_first(self, db, users, make_listing):
        old = make_listing(users["landlord"], address="Old")
        make_listing(users["landlord"], address="Hidden", status="Pending")
        new = make_listing(users["landlord"], address="New")
        listings, pagination = ListingRepository(db).search_verified(page=1, limit=5)
        assert [l.id for l in listings] == [new.id, old.id]
        assert pagination.total_count == 2

    def test_search_combines_filters(self, db, users, make_listing):
        make_listing(users["landlord"], address="Palm", room_type="Studio", price="2000", amenities="Dryer")
        make_listing(users["landlord"], address="Palm", room_type="Shared", price="2000", amenities="Dryer")
        make_listing(users["landlord"], address="Palm", room_type="Studio", price="4000", amenities="Dryer")
        repo = ListingRepository(db)
        listings, _ = repo.search_verified(
            page=1, limit=5, address="palm", room_type="studio",
            amenities=["dryer"], min_price=Decimal("1000"), max_price=Decimal("3000"),
        )
        assert len(listings) == 1 and listings[0].price == Decimal("2000")

    def test_page_beyond_the_end_is_clamped(self, db, users, make_listing):
        for i in range(3):
            make_listing(users["landlord"], address=f"L{i}")
        listings, pagination = ListingRepository(db).search_verified(page=9, limit=2)
        assert pagination.page == 2 and len(listings) == 1

    def test_pending_queue_orders_by_id(self, db, users, make_listing):
        first = make_listing(users["landlord"], status="Pending")
        second = make_listing(users["landlord"], status="Pending")
        repo = ListingRepository(db)
        newest, _ = repo.get_pending_listings(1, 5, newest_first=True)
        oldest, _ = repo.get_pending_listings(1, 5, newest_first=False)
        assert [l.id for l in newest] == [second.id, first.id]
        assert [l.id for l in oldest] == [first.id, second.id]

    def test_update_changes_only_status_and_reason(self, db, users, make_listing):
        listing = make_listing(users["landlord"], status="Pending", price="1000")
        repo = ListingRepository(db)
        listing.verification_status = "Rejected"
        listing.rejection_reason = "No photos"
        listing.price = Decimal("9999")
        updated = repo.update(listing)
        assert updated.verification_status == "Rejected"
        assert updated.rejection_reason == "No photos"

    def test_update_without_an_id_is_an_error(self, db, users):
        from app.models.listing import Listing

        with pytest.raises(ValueError):
            ListingRepository(db).update(Listing(address="x", price=1, security_fee=1, room_type="r",
                                                  amenities="a", photos="[]", landlord_id=users["landlord"].id))

    def test_update_of_a_missing_listing_is_an_error(self, db, users):
        from app.models.listing import Listing

        ghost = Listing(id=9999, address="x", price=1, security_fee=1, room_type="r",
                        amenities="a", photos="[]", landlord_id=users["landlord"].id)
        with pytest.raises(ValueError, match="not found"):
            ListingRepository(db).update(ghost)

    def test_room_types_are_distinct_sorted_and_verified_only(self, db, users, make_listing):
        make_listing(users["landlord"], room_type="Studio")
        make_listing(users["landlord"], room_type="Studio")
        make_listing(users["landlord"], room_type="Apartment")
        make_listing(users["landlord"], room_type="Secret", status="Pending")
        assert ListingRepository(db).get_verified_room_types() == ["Apartment", "Studio"]

    def test_landlord_listings_are_scoped_to_the_landlord(self, db, users, make_listing):
        mine = make_listing(users["landlord"])
        make_listing(users["landlord2"])
        listings, pagination = ListingRepository(db).get_by_landlord_id(users["landlord"].id, 1, 5)
        assert [l.id for l in listings] == [mine.id] and pagination.total_count == 1

    def test_get_by_ids_handles_empty_input(self, db):
        assert ListingRepository(db).get_by_ids([]) == {}


class TestApplicationRepository:
    def test_active_application_ignores_declined_and_completed(
        self, db, users, make_listing, make_application
    ):
        listing = make_listing(users["landlord"])
        repo = ApplicationRepository(db)
        make_application(users["bob"], listing, "Declined")
        make_application(users["bob"], listing, "Completed")
        assert repo.get_active_for_student_listing(users["bob"].id, listing.id) is None
        live = make_application(users["bob"], listing, "Info Requested")
        assert repo.get_active_for_student_listing(users["bob"].id, listing.id).id == live.id

    def test_student_and_landlord_views_are_scoped(self, db, users, make_listing, make_application):
        mine, theirs = make_listing(users["landlord"]), make_listing(users["landlord2"])
        make_application(users["bob"], mine)
        make_application(users["fred"], mine)
        make_application(users["bob"], theirs)
        repo = ApplicationRepository(db)
        assert repo.get_for_student(users["bob"].id, 1, 10)[1].total_count == 2
        assert repo.get_for_landlord(users["landlord"].id, 1, 10)[1].total_count == 2

    def test_update_of_a_missing_application_is_an_error(self, db, users):
        from app.models.application import Application

        ghost = Application(id=9999, listing_id=1, student_id=users["bob"].id,
                            preferred_start_date=date(2027, 1, 1))
        with pytest.raises(ValueError, match="not found"):
            ApplicationRepository(db).update(ghost)


class TestBookingRepository:
    def test_in_progress_statuses_block_but_completed_does_not(
        self, db, users, make_listing, make_application, make_booking
    ):
        listing = make_listing(users["landlord"])
        repo = BookingRepository(db)
        make_booking(make_application(users["bob"], listing, "Completed"), "Completed")
        assert repo.get_in_progress_for_listing(listing.id) is None
        make_booking(make_application(users["fred"], listing, "Accepted"), "Awaiting Payment")
        assert repo.get_in_progress_for_listing(listing.id) is not None

    def test_confirm_payment_saves_payment_and_blocks_the_listing(
        self, db, users, make_listing, make_application, make_booking
    ):
        listing = make_listing(users["landlord"])
        booking = make_booking(make_application(users["bob"], listing, "Accepted"))
        payment = Payment(
            booking_id=booking.id, student_id=users["bob"].id, type="card",
            amount=Decimal("3000"), paid=True, payment_date=date.today(),
        )
        saved = BookingRepository(db).confirm_payment(booking, listing, payment)
        assert saved.id is not None
        assert booking.status == "Confirmed" and listing.availability is False

    def test_one_booking_per_application(
        self, db, users, make_listing, make_application, make_booking
    ):
        application = make_application(users["bob"], make_listing(users["landlord"]), "Accepted")
        make_booking(application)
        with pytest.raises(IntegrityError):
            make_booking(application)


class TestReviewRepository:
    def _reviews(self, users, make_listing, make_application, make_booking, make_review, ratings):
        listing = make_listing(users["landlord"])
        for rating in ratings:
            booking = make_booking(make_application(users["bob"], listing, "Completed"), "Completed")
            make_review(booking, rating=rating)
        return listing

    def test_average_covers_every_review_not_just_the_page(
        self, db, users, make_listing, make_application, make_booking, make_review
    ):
        listing = self._reviews(users, make_listing, make_application, make_booking, make_review, [5, 5, 5, 5, 5, 1])
        _rows, pagination, average = ReviewRepository(db).get_for_listing(listing.id, 1, 5)
        assert average == pytest.approx(26 / 6) and pagination.total_pages == 2

    def test_rows_carry_the_reviewer(
        self, db, users, make_listing, make_application, make_booking, make_review
    ):
        listing = self._reviews(users, make_listing, make_application, make_booking, make_review, [4])
        rows, _p, _a = ReviewRepository(db).get_for_listing(listing.id, 1, 5)
        review, reviewer = rows[0]
        assert reviewer.username == "bob" and review.rating == 4

    def test_listing_with_no_reviews_has_no_average(self, db, users, make_listing):
        listing = make_listing(users["landlord"])
        rows, pagination, average = ReviewRepository(db).get_for_listing(listing.id, 1, 5)
        assert rows == [] and average is None and pagination.total_count == 0

    def test_page_past_the_end_is_clamped(
        self, db, users, make_listing, make_application, make_booking, make_review
    ):
        listing = self._reviews(users, make_listing, make_application, make_booking, make_review, [3, 4])
        rows, pagination, _a = ReviewRepository(db).get_for_listing(listing.id, 99, 5)
        assert pagination.page == 1 and len(rows) == 2

    def test_a_booking_can_only_be_reviewed_once(
        self, db, users, make_listing, make_application, make_booking, make_review
    ):
        listing = make_listing(users["landlord"])
        booking = make_booking(make_application(users["bob"], listing, "Completed"), "Completed")
        repo = ReviewRepository(db)
        repo.create(Review(booking_id=booking.id, student_id=booking.student_id,
                           listing_id=listing.id, rating=5, comment="a"))
        with pytest.raises(IntegrityError):
            repo.create(Review(booking_id=booking.id, student_id=booking.student_id,
                               listing_id=listing.id, rating=4, comment="b"))


class TestUserRepository:
    def test_create_and_lookup(self, db):
        repo = UserRepository(db)
        created = repo.create(RegularUserCreate(username="amy", email="amy@example.com", password="h"))
        assert repo.get_by_username("amy").id == created.id
        assert repo.get_by_id(created.id).email == "amy@example.com"
        assert repo.get_by_username("ghost") is None

    def test_usernames_are_unique(self, db):
        repo = UserRepository(db)
        repo.create(RegularUserCreate(username="amy", email="a@example.com", password="h"))
        with pytest.raises(IntegrityError):
            repo.create(RegularUserCreate(username="amy", email="b@example.com", password="h"))

    def test_search_matches_username_or_email(self, db, users):
        found, pagination = UserRepository(db).search_users("land")
        assert {u.username for u in found} == {"landlord", "landlord2"}
        assert pagination.total_count == 2

    def test_deleting_a_missing_user_is_an_error(self, db):
        with pytest.raises(Exception, match="doesn't exist"):
            UserRepository(db).delete_user(999)
