"""Browser-facing pages: cookie login, forms, redirects and access control.

These mirror the wireframes: sign in, search and detail pages, landlord posting,
admin queue, student applications/payment/review. Forms redirect with 303.
"""


from sqlmodel import Session, select

from app.models.application import Application
from app.models.booking import Booking
from app.models.listing import Listing
from app.models.review import Review
from tests.conftest import PASSWORD


def login(client, username):
    client.cookies.clear()
    response = client.post(
        "/login", data={"username": username, "password": PASSWORD}, follow_redirects=False
    )
    assert response.status_code == 303, response.text
    return response


def fetch(engine, model, **filters):
    with Session(engine) as session:
        rows = session.exec(select(model).filter_by(**filters)).all()
        for row in rows:
            session.expunge(row)
        return rows


def only(engine, model, **filters):
    rows = fetch(engine, model, **filters)
    assert len(rows) == 1, f"expected one {model.__name__}, found {len(rows)}"
    return rows[0]


class TestLoginAndAccess:
    def test_landing_page_is_public(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "Student Accommodation" in response.text

    def test_login_and_register_pages_render(self, client):
        assert client.get("/login").status_code == 200
        assert client.get("/register").status_code == 200

    def test_student_login_sets_a_cookie_and_goes_to_the_app(self, client, users):
        response = login(client, "bob")
        assert response.headers["location"].endswith("/app")
        assert "access_token" in response.headers["set-cookie"]
        assert client.get("/app").status_code == 200

    def test_admin_login_goes_to_the_admin_home(self, client, users):
        response = login(client, "admin")
        assert response.headers["location"].endswith("/admin")
        assert client.get("/admin").status_code == 200

    def test_wrong_password_returns_to_the_login_page(self, client, users):
        response = client.post(
            "/login", data={"username": "bob", "password": "wrong"}, follow_redirects=False
        )
        assert response.status_code == 303
        assert response.headers["location"].endswith("/login")
        assert "access_token" not in response.headers.get("set-cookie", "")

    def test_signed_out_visitors_get_a_401_page(self, client):
        for path in ("/app", "/admin", "/landlord/listings", "/applications"):
            response = client.get(path)
            assert response.status_code == 401, path
            assert "Sign in required" in response.text

    def test_students_cannot_open_the_admin_pages(self, client, users):
        login(client, "bob")
        assert client.get("/admin").status_code == 401
        assert client.get("/admin/listings/pending").status_code == 401

    def test_logout_ends_the_session(self, client, users):
        login(client, "bob")
        response = client.get("/logout", follow_redirects=False)
        assert response.status_code == 303
        client.cookies.clear()  # the browser drops the deleted cookie
        assert client.get("/app").status_code == 401

    def test_registration_creates_a_student_who_can_sign_in(self, client, engine):
        response = client.post(
            "/register",
            data={"username": "amy", "email": "amy@example.com", "password": "pw12345"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"].endswith("/login")
        client.post("/login", data={"username": "amy", "password": "pw12345"}, follow_redirects=False)
        assert client.get("/app").status_code == 200

    def test_duplicate_registration_returns_to_the_form(self, client, users):
        response = client.post(
            "/register",
            data={"username": "bob", "email": "new@example.com", "password": "pw12345"},
            follow_redirects=False,
        )
        assert response.headers["location"].endswith("/register")

    def test_health_check(self, client):
        assert client.get("/health").json() == {"ok": True}


class TestPublicListingPages:
    def test_search_shows_only_verified_listings(self, client, users, make_listing):
        make_listing(users["landlord"], address="Visible Villa")
        make_listing(users["landlord"], address="Pending Place", status="Pending")
        page = client.get("/listings").text
        assert "Visible Villa" in page and "Pending Place" not in page

    def test_search_filters_apply(self, client, users, make_listing):
        make_listing(users["landlord"], address="Palm House")
        make_listing(users["landlord"], address="Oak Lodge")
        page = client.get("/listings?address=palm").text
        assert "Palm House" in page and "Oak Lodge" not in page

    def test_invalid_price_range_redirects_back_to_search(self, client):
        response = client.get("/listings?min_price=9&max_price=1", follow_redirects=False)
        assert response.status_code == 303

    def test_detail_page_shows_the_listing(self, client, users, make_listing):
        listing = make_listing(users["landlord"], address="Detail Court")
        response = client.get(f"/listings/{listing.id}")
        assert response.status_code == 200 and "Detail Court" in response.text

    def test_unverified_listing_detail_redirects_to_search(self, client, users, make_listing):
        listing = make_listing(users["landlord"], status="Pending")
        response = client.get(f"/listings/{listing.id}", follow_redirects=False)
        assert response.status_code == 303

    def test_detail_page_shows_reviewer_login_rating_and_comment(
        self, client, users, make_listing, make_application, make_booking, make_review
    ):
        listing = make_listing(users["landlord"])
        booking = make_booking(make_application(users["bob"], listing, "Completed"), "Completed")
        make_review(booking, rating=4, comment="Lovely and quiet")
        page = client.get(f"/listings/{listing.id}").text
        assert "bob" in page and "Lovely and quiet" in page


class TestRoleChecksOnForms:
    def test_student_cannot_post_a_listing(self, client, users, engine):
        login(client, "bob")
        response = client.post(
            "/landlord/listings",
            data={"address": "x", "room_type": "y", "amenities": "z", "price": "1", "security_fee": "1"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert fetch(engine, Listing) == []

    def test_landlord_form_rejects_a_bad_price(self, client, users, engine):
        login(client, "landlord")
        response = client.post(
            "/landlord/listings",
            data={"address": "x", "room_type": "y", "amenities": "z", "price": "abc", "security_fee": "1"},
            follow_redirects=False,
        )
        assert response.headers["location"].endswith("/landlord/listings/new")
        assert fetch(engine, Listing) == []

    def test_landlord_cannot_decide_a_listing(self, client, users, make_listing):
        listing = make_listing(users["landlord"], status="Pending")
        login(client, "landlord")
        response = client.post(
            f"/admin/listings/{listing.id}/decision", data={"decision": "approve"}, follow_redirects=False
        )
        assert response.status_code == 401

    def test_empty_rejection_reason_is_refused(self, client, users, engine, make_listing):
        listing = make_listing(users["landlord"], status="Pending")
        login(client, "admin")
        client.post(
            f"/admin/listings/{listing.id}/decision",
            data={"decision": "reject", "rejection_reason": ""},
            follow_redirects=False,
        )
        assert only(engine, Listing, id=listing.id).verification_status == "Pending"

    def test_student_cannot_decide_an_application(
        self, client, users, engine, make_listing, make_application
    ):
        application = make_application(
            users["bob"], make_listing(users["landlord"]), status="Info Submitted"
        )
        login(client, "fred")
        client.post(
            f"/applications/{application.id}/decide", data={"decision": "Accepted"}, follow_redirects=False
        )
        assert only(engine, Application, id=application.id).status == "Info Submitted"


class TestStudentApplicationsPage:
    def test_declined_application_shows_the_landlords_reason(
        self, client, users, make_listing, make_application, db
    ):
        application = make_application(
            users["bob"], make_listing(users["landlord"], address="Declined Court"), status="Declined"
        )
        application.decline_reason = "Room no longer free"
        db.add(application)
        db.commit()
        login(client, "bob")
        page = client.get("/applications").text
        assert "Declined Court" in page
        assert "Decline reason:" in page and "Room no longer free" in page

    def test_reason_is_not_shown_for_other_statuses(
        self, client, users, make_listing, make_application
    ):
        make_application(users["bob"], make_listing(users["landlord"]), status="Applied")
        login(client, "bob")
        assert "Decline reason:" not in client.get("/applications").text


def test_all_three_workflows_through_the_pages(client, users, engine):
    # Workflow 1: landlord posts a listing, admin approves it
    login(client, "landlord")
    response = client.post(
        "/landlord/listings",
        data={
            "address": "9 Browser Lane",
            "room_type": "Studio",
            "amenities": "Wi-Fi",
            "price": "2500",
            "security_fee": "500",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith("/landlord/listings")
    listing = only(engine, Listing, address="9 Browser Lane")
    assert listing.verification_status == "Pending"
    assert "Pending" in client.get("/landlord/listings").text

    login(client, "admin")
    assert "9 Browser Lane" in client.get("/admin/listings/pending").text
    client.post(
        f"/admin/listings/{listing.id}/decision", data={"decision": "approve"}, follow_redirects=False
    )
    assert only(engine, Listing, id=listing.id).verification_status == "Verified"

    # Workflow 2: student applies, landlord reviews, student pays
    login(client, "bob")
    response = client.post(
        f"/listings/{listing.id}/apply", data={"preferred_start_date": "2027-01-10"}, follow_redirects=False
    )
    assert response.headers["location"].endswith("/applications")
    application = only(engine, Application, listing_id=listing.id)
    assert application.status == "Applied"
    assert "9 Browser Lane" in client.get("/applications").text

    login(client, "landlord")
    client.post(f"/applications/{application.id}/request-details", follow_redirects=False)
    assert only(engine, Application, id=application.id).status == "Info Requested"

    login(client, "bob")
    client.post(
        f"/applications/{application.id}/details",
        data={"student_name": "Bob Smith", "student_age": "21", "purpose_of_stay": "Study"},
        follow_redirects=False,
    )
    assert only(engine, Application, id=application.id).status == "Info Submitted"

    login(client, "landlord")
    client.post(
        f"/applications/{application.id}/decide", data={"decision": "Accepted"}, follow_redirects=False
    )
    booking = only(engine, Booking, application_id=application.id)
    assert booking.status == "Awaiting Payment"

    login(client, "bob")
    assert client.get(f"/bookings/{booking.id}/payment").status_code == 200
    client.post(
        f"/bookings/{booking.id}/payment", data={"payment_method": "card"}, follow_redirects=False
    )
    assert only(engine, Booking, id=booking.id).status == "Confirmed"
    assert only(engine, Listing, id=listing.id).availability is False

    # Workflow 3: notice, completion, review
    client.post(
        f"/bookings/{booking.id}/move-out", data={"move_out_date": "2027-06-30"}, follow_redirects=False
    )
    assert only(engine, Booking, id=booking.id).status == "Notice Given"

    login(client, "landlord")
    client.post(f"/bookings/{booking.id}/complete", follow_redirects=False)
    assert only(engine, Booking, id=booking.id).status == "Completed"
    assert only(engine, Listing, id=listing.id).availability is True

    login(client, "bob")
    assert client.get(f"/bookings/{booking.id}/review").status_code == 200
    client.post(
        f"/bookings/{booking.id}/review",
        data={"rating": "5", "comment": "Spotless"},
        follow_redirects=False,
    )
    assert only(engine, Review, booking_id=booking.id).rating == 5

    client.cookies.clear()
    page = client.get(f"/listings/{listing.id}").text
    assert "Spotless" in page and "bob" in page
