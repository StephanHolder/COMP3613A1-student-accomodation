"""The three named workflows end to end, plus their negative paths, through the API.

1. Post listing detail for verification (Landlord) -> Verify (Admin)
2. Apply to listed accommodation (Student) -> landlord review -> payment
3. Submit review of completed stay (Student)
"""

import pytest

START = "2027-01-10"
MOVE_OUT = "2027-06-30"


def apply(client, headers, listing_id, start=START):
    return client.post(
        f"/api/listings/{listing_id}/applications",
        json={"preferred_start_date": start},
        headers=headers,
    )


def details_body(**overrides):
    body = {"student_name": "Bob Smith", "student_age": 21, "purpose_of_stay": "Study at UWI"}
    body.update(overrides)
    return body


# ------------------------------------------------------------ happy path


def test_full_lifecycle_from_posting_to_review(client, users, auth):
    landlord, admin, bob = auth(users["landlord"]), auth(users["admin"]), auth(users["bob"])

    # Workflow 1: landlord posts, admin verifies
    posted = client.post(
        "/api/listings",
        json={
            "address": "5 Coffee Street",
            "room_type": "Studio",
            "amenities": "Wi-Fi",
            "price": 2500,
            "security_fee": 500,
        },
        headers=landlord,
    )
    assert posted.status_code == 201
    listing_id = posted.json()["id"]
    approved = client.put(
        f"/api/listings/{listing_id}/verification", json={"decision": "approve"}, headers=admin
    )
    assert approved.json()["verification_status"] == "Verified"

    # Workflow 2: student applies, landlord requests details, student submits, landlord accepts
    applied = apply(client, bob, listing_id)
    assert applied.status_code == 201
    assert applied.json()["status"] == "Applied"
    application_id = applied.json()["id"]

    inbox = client.get("/api/landlord/applications", headers=landlord).json()
    assert [a["id"] for a in inbox["items"]] == [application_id]

    requested = client.post(f"/api/applications/{application_id}/detail-requests", headers=landlord)
    assert (requested.status_code, requested.json()["status"]) == (201, "Info Requested")

    submitted = client.put(
        f"/api/applications/{application_id}/details", json=details_body(), headers=bob
    )
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "Info Submitted"
    assert submitted.json()["student_age"] == 21

    accepted = client.put(
        f"/api/applications/{application_id}/decision", json={"decision": "Accepted"}, headers=landlord
    )
    assert accepted.json()["status"] == "Accepted"

    booking = client.get(f"/api/applications/{application_id}/booking", headers=bob).json()
    assert booking["status"] == "Awaiting Payment"
    assert booking["start_date"] == START
    booking_id = booking["id"]

    paid = client.post(
        f"/api/bookings/{booking_id}/payments", json={"payment_method": "card"}, headers=bob
    )
    assert paid.status_code == 201
    assert paid.json()["amount"] == 3000.0 and paid.json()["paid"] is True
    assert client.get(f"/api/bookings/{booking_id}", headers=bob).json()["status"] == "Confirmed"
    assert client.get(f"/api/listings/{listing_id}").json()["availability"] is False

    # Stay ends
    notice = client.put(
        f"/api/bookings/{booking_id}/move-out", json={"move_out_date": MOVE_OUT}, headers=bob
    )
    assert (notice.status_code, notice.json()["status"]) == (200, "Notice Given")
    done = client.put(f"/api/bookings/{booking_id}/completion", headers=landlord)
    assert (done.status_code, done.json()["status"]) == (200, "Completed")
    assert client.get(f"/api/listings/{listing_id}").json()["availability"] is True

    # Workflow 3: student reviews the completed stay
    review = client.post(
        f"/api/bookings/{booking_id}/reviews",
        json={"rating": 5, "comment": "Quiet and clean"},
        headers=bob,
    )
    assert review.status_code == 201
    assert review.json()["reviewer"] == "bob"
    reviews = client.get(f"/api/listings/{listing_id}/reviews").json()
    assert reviews["average_rating"] == 5.0
    assert [r["comment"] for r in reviews["items"]] == ["Quiet and clean"]


# ------------------------------------------------------------- applying


class TestApply:
    def test_requires_a_token(self, client, users, make_listing):
        listing = make_listing(users["landlord"])
        response = client.post(
            f"/api/listings/{listing.id}/applications", json={"preferred_start_date": START}
        )
        assert response.status_code == 401

    def test_landlords_cannot_apply(self, client, users, auth, make_listing):
        listing = make_listing(users["landlord"])
        assert apply(client, auth(users["landlord2"]), listing.id).status_code == 403

    def test_unknown_listing_is_404(self, client, users, auth):
        assert apply(client, auth(users["bob"]), 9999).status_code == 404

    def test_unverified_listing_conflicts(self, client, users, auth, make_listing):
        listing = make_listing(users["landlord"], status="Pending")
        assert apply(client, auth(users["bob"]), listing.id).status_code == 409

    def test_unavailable_listing_conflicts(self, client, users, auth, make_listing):
        listing = make_listing(users["landlord"], available=False)
        assert apply(client, auth(users["bob"]), listing.id).status_code == 409

    def test_duplicate_active_application_conflicts(self, client, users, auth, make_listing):
        listing = make_listing(users["landlord"])
        assert apply(client, auth(users["bob"]), listing.id).status_code == 201
        assert apply(client, auth(users["bob"]), listing.id).status_code == 409

    def test_two_students_can_apply_to_the_same_listing(self, client, users, auth, make_listing):
        listing = make_listing(users["landlord"])
        assert apply(client, auth(users["bob"]), listing.id).status_code == 201
        assert apply(client, auth(users["fred"]), listing.id).status_code == 201

    def test_declined_student_may_apply_again(
        self, client, users, auth, make_listing, make_application
    ):
        listing = make_listing(users["landlord"])
        make_application(users["bob"], listing, status="Declined")
        assert apply(client, auth(users["bob"]), listing.id).status_code == 201

    def test_bad_date_is_422(self, client, users, auth, make_listing):
        listing = make_listing(users["landlord"])
        assert apply(client, auth(users["bob"]), listing.id, start="soon").status_code == 422

    def test_student_sees_only_own_applications(
        self, client, users, auth, make_listing, make_application
    ):
        listing = make_listing(users["landlord"])
        make_application(users["bob"], listing)
        make_application(users["fred"], listing)
        body = client.get("/api/applications", headers=auth(users["bob"])).json()
        assert body["total_count"] == 1
        assert body["items"][0]["student_id"] == users["bob"].id

    def test_landlords_cannot_use_the_student_list(self, client, users, auth):
        assert client.get("/api/applications", headers=auth(users["landlord"])).status_code == 403

    def test_students_cannot_use_the_landlord_inbox(self, client, users, auth):
        assert client.get("/api/landlord/applications", headers=auth(users["bob"])).status_code == 403

    def test_landlord_inbox_hides_other_landlords_applications(
        self, client, users, auth, make_listing, make_application
    ):
        mine = make_listing(users["landlord"])
        theirs = make_listing(users["landlord2"])
        make_application(users["bob"], mine)
        make_application(users["bob"], theirs)
        body = client.get("/api/landlord/applications", headers=auth(users["landlord"])).json()
        assert [a["listing_id"] for a in body["items"]] == [mine.id]


# --------------------------------------------------- landlord review steps


class TestLandlordReview:
    def test_other_landlord_cannot_request_details(
        self, client, users, auth, make_listing, make_application
    ):
        application = make_application(users["bob"], make_listing(users["landlord"]))
        response = client.post(
            f"/api/applications/{application.id}/detail-requests", headers=auth(users["landlord2"])
        )
        assert response.status_code == 403

    def test_students_cannot_request_details(
        self, client, users, auth, make_listing, make_application
    ):
        application = make_application(users["bob"], make_listing(users["landlord"]))
        response = client.post(
            f"/api/applications/{application.id}/detail-requests", headers=auth(users["fred"])
        )
        assert response.status_code == 403

    def test_details_can_only_be_requested_once(
        self, client, users, auth, make_listing, make_application
    ):
        application = make_application(
            users["bob"], make_listing(users["landlord"]), status="Info Requested"
        )
        response = client.post(
            f"/api/applications/{application.id}/detail-requests", headers=auth(users["landlord"])
        )
        assert response.status_code == 409

    def test_unknown_application_is_404(self, client, users, auth):
        response = client.post("/api/applications/9999/detail-requests", headers=auth(users["landlord"]))
        assert response.status_code == 404

    def test_cannot_accept_before_details_are_submitted(
        self, client, users, auth, make_listing, make_application
    ):
        application = make_application(users["bob"], make_listing(users["landlord"]))
        response = client.put(
            f"/api/applications/{application.id}/decision",
            json={"decision": "Accepted"},
            headers=auth(users["landlord"]),
        )
        assert response.status_code == 409

    def test_decline_needs_a_reason(self, client, users, auth, make_listing, make_application):
        application = make_application(users["bob"], make_listing(users["landlord"]))
        response = client.put(
            f"/api/applications/{application.id}/decision",
            json={"decision": "Declined"},
            headers=auth(users["landlord"]),
        )
        assert response.status_code == 422

    def test_decline_with_a_reason_is_visible_to_the_student(
        self, client, users, auth, make_listing, make_application
    ):
        application = make_application(users["bob"], make_listing(users["landlord"]))
        response = client.put(
            f"/api/applications/{application.id}/decision",
            json={"decision": "Declined", "decline_reason": "Room taken"},
            headers=auth(users["landlord"]),
        )
        assert response.status_code == 200
        mine = client.get("/api/applications", headers=auth(users["bob"])).json()["items"][0]
        assert (mine["status"], mine["decline_reason"]) == ("Declined", "Room taken")

    def test_other_landlord_cannot_decide(
        self, client, users, auth, make_listing, make_application
    ):
        application = make_application(
            users["bob"], make_listing(users["landlord"]), status="Info Submitted"
        )
        response = client.put(
            f"/api/applications/{application.id}/decision",
            json={"decision": "Accepted"},
            headers=auth(users["landlord2"]),
        )
        assert response.status_code == 403

    def test_unknown_decision_value_is_422(
        self, client, users, auth, make_listing, make_application
    ):
        application = make_application(users["bob"], make_listing(users["landlord"]))
        response = client.put(
            f"/api/applications/{application.id}/decision",
            json={"decision": "Perhaps"},
            headers=auth(users["landlord"]),
        )
        assert response.status_code == 422

    def test_accepting_a_second_application_is_blocked_while_one_is_in_progress(
        self, client, users, auth, make_listing, make_application, make_booking
    ):
        listing = make_listing(users["landlord"])
        first = make_application(users["bob"], listing, status="Accepted")
        make_booking(first, status="Awaiting Payment")
        second = make_application(users["fred"], listing, status="Info Submitted")
        response = client.put(
            f"/api/applications/{second.id}/decision",
            json={"decision": "Accepted"},
            headers=auth(users["landlord"]),
        )
        assert response.status_code == 409


class TestStudentDetails:
    def test_other_student_cannot_submit(self, client, users, auth, make_listing, make_application):
        application = make_application(
            users["bob"], make_listing(users["landlord"]), status="Info Requested"
        )
        response = client.put(
            f"/api/applications/{application.id}/details", json=details_body(), headers=auth(users["fred"])
        )
        assert response.status_code == 403

    def test_cannot_submit_before_details_are_requested(
        self, client, users, auth, make_listing, make_application
    ):
        application = make_application(users["bob"], make_listing(users["landlord"]))
        response = client.put(
            f"/api/applications/{application.id}/details", json=details_body(), headers=auth(users["bob"])
        )
        assert response.status_code == 409

    def test_non_numeric_age_is_422(self, client, users, auth, make_listing, make_application):
        application = make_application(
            users["bob"], make_listing(users["landlord"]), status="Info Requested"
        )
        response = client.put(
            f"/api/applications/{application.id}/details",
            json=details_body(student_age="twenty"),
            headers=auth(users["bob"]),
        )
        assert response.status_code == 422

    def test_zero_age_is_422(self, client, users, auth, make_listing, make_application):
        application = make_application(
            users["bob"], make_listing(users["landlord"]), status="Info Requested"
        )
        response = client.put(
            f"/api/applications/{application.id}/details",
            json=details_body(student_age=0),
            headers=auth(users["bob"]),
        )
        assert response.status_code == 422

    def test_blank_name_is_422(self, client, users, auth, make_listing, make_application):
        application = make_application(
            users["bob"], make_listing(users["landlord"]), status="Info Requested"
        )
        response = client.put(
            f"/api/applications/{application.id}/details",
            json=details_body(student_name="  "),
            headers=auth(users["bob"]),
        )
        assert response.status_code == 422


# --------------------------------------------------------------- bookings


class TestPaymentAndBookings:
    def make_awaiting(self, users, make_listing, make_application, make_booking):
        listing = make_listing(users["landlord"])
        application = make_application(users["bob"], listing, status="Accepted")
        return listing, make_booking(application, status="Awaiting Payment")

    def pay(self, client, headers, booking_id, method="card"):
        return client.post(
            f"/api/bookings/{booking_id}/payments", json={"payment_method": method}, headers=headers
        )

    def test_payment_confirms_the_booking_and_blocks_the_listing(
        self, client, users, auth, make_listing, make_application, make_booking
    ):
        listing, booking = self.make_awaiting(users, make_listing, make_application, make_booking)
        response = self.pay(client, auth(users["bob"]), booking.id, "cash")
        assert response.status_code == 201
        assert response.json()["type"] == "cash"
        assert client.get(f"/api/bookings/{booking.id}", headers=auth(users["bob"])).json()["status"] == "Confirmed"
        assert client.get(f"/api/listings/{listing.id}").json()["availability"] is False

    def test_other_student_cannot_pay(
        self, client, users, auth, make_listing, make_application, make_booking
    ):
        _l, booking = self.make_awaiting(users, make_listing, make_application, make_booking)
        assert self.pay(client, auth(users["fred"]), booking.id).status_code == 403

    def test_landlord_cannot_pay(
        self, client, users, auth, make_listing, make_application, make_booking
    ):
        _l, booking = self.make_awaiting(users, make_listing, make_application, make_booking)
        assert self.pay(client, auth(users["landlord"]), booking.id).status_code == 403

    def test_cannot_pay_twice(
        self, client, users, auth, make_listing, make_application, make_booking
    ):
        _l, booking = self.make_awaiting(users, make_listing, make_application, make_booking)
        assert self.pay(client, auth(users["bob"]), booking.id).status_code == 201
        assert self.pay(client, auth(users["bob"]), booking.id).status_code == 409

    def test_blank_payment_method_is_422(
        self, client, users, auth, make_listing, make_application, make_booking
    ):
        _l, booking = self.make_awaiting(users, make_listing, make_application, make_booking)
        assert self.pay(client, auth(users["bob"]), booking.id, "  ").status_code == 422

    def test_unknown_booking_is_404(self, client, users, auth):
        assert self.pay(client, auth(users["bob"]), 9999).status_code == 404

    def test_outsiders_cannot_view_a_booking(
        self, client, users, auth, make_listing, make_application, make_booking
    ):
        _l, booking = self.make_awaiting(users, make_listing, make_application, make_booking)
        for who in ("fred", "landlord2", "admin"):
            response = client.get(f"/api/bookings/{booking.id}", headers=auth(users[who]))
            assert response.status_code == 403
        assert client.get(f"/api/bookings/{booking.id}", headers=auth(users["landlord"])).status_code == 200

    def test_booking_lookup_for_an_application_without_one_is_404(
        self, client, users, auth, make_listing, make_application
    ):
        application = make_application(users["bob"], make_listing(users["landlord"]))
        response = client.get(f"/api/applications/{application.id}/booking", headers=auth(users["bob"]))
        assert response.status_code == 404


class TestMoveOutAndCompletion:
    def confirmed(self, users, make_listing, make_application, make_booking, status="Confirmed"):
        listing = make_listing(users["landlord"], available=False)
        application = make_application(users["bob"], listing, status="Accepted")
        return listing, make_booking(application, status=status)

    def move_out(self, client, headers, booking_id, date=MOVE_OUT):
        return client.put(
            f"/api/bookings/{booking_id}/move-out", json={"move_out_date": date}, headers=headers
        )

    def test_move_out_must_be_after_the_start_date(
        self, client, users, auth, make_listing, make_application, make_booking
    ):
        _l, booking = self.confirmed(users, make_listing, make_application, make_booking)
        same_day = booking.start_date.isoformat()
        response = self.move_out(client, auth(users["bob"]), booking.id, date=same_day)
        assert response.status_code == 422

    def test_move_out_needs_a_confirmed_booking(
        self, client, users, auth, make_listing, make_application, make_booking
    ):
        _l, booking = self.confirmed(
            users, make_listing, make_application, make_booking, status="Awaiting Payment"
        )
        assert self.move_out(client, auth(users["bob"]), booking.id).status_code == 409

    def test_only_the_booked_student_gives_notice(
        self, client, users, auth, make_listing, make_application, make_booking
    ):
        _l, booking = self.confirmed(users, make_listing, make_application, make_booking)
        assert self.move_out(client, auth(users["fred"]), booking.id).status_code == 403

    def test_completion_needs_notice_first(
        self, client, users, auth, make_listing, make_application, make_booking
    ):
        _l, booking = self.confirmed(users, make_listing, make_application, make_booking)
        response = client.put(f"/api/bookings/{booking.id}/completion", headers=auth(users["landlord"]))
        assert response.status_code == 409

    def test_only_the_owning_landlord_completes(
        self, client, users, auth, make_listing, make_application, make_booking
    ):
        _l, booking = self.confirmed(
            users, make_listing, make_application, make_booking, status="Notice Given"
        )
        for who in ("landlord2", "bob"):
            response = client.put(f"/api/bookings/{booking.id}/completion", headers=auth(users[who]))
            assert response.status_code == 403

    def test_completion_reopens_the_listing_and_allows_a_new_application(
        self, client, users, auth, make_listing, make_application, make_booking
    ):
        listing, booking = self.confirmed(
            users, make_listing, make_application, make_booking, status="Notice Given"
        )
        done = client.put(f"/api/bookings/{booking.id}/completion", headers=auth(users["landlord"]))
        assert done.status_code == 200
        assert client.get(f"/api/listings/{listing.id}").json()["availability"] is True
        assert apply(client, auth(users["bob"]), listing.id).status_code == 201


# ---------------------------------------------------------------- reviews


class TestReviews:
    def completed_booking(self, users, make_listing, make_application, make_booking, student="bob"):
        listing = make_listing(users["landlord"])
        application = make_application(users[student], listing, status="Completed")
        return listing, make_booking(application, status="Completed")

    def review(self, client, headers, booking_id, rating=4, comment="Good"):
        return client.post(
            f"/api/bookings/{booking_id}/reviews",
            json={"rating": rating, "comment": comment},
            headers=headers,
        )

    def test_cannot_review_before_the_stay_is_completed(
        self, client, users, auth, make_listing, make_application, make_booking
    ):
        application = make_application(users["bob"], make_listing(users["landlord"]), status="Accepted")
        booking = make_booking(application, status="Confirmed")
        assert self.review(client, auth(users["bob"]), booking.id).status_code == 409

    def test_one_review_per_booking(
        self, client, users, auth, make_listing, make_application, make_booking
    ):
        _l, booking = self.completed_booking(users, make_listing, make_application, make_booking)
        assert self.review(client, auth(users["bob"]), booking.id).status_code == 201
        assert self.review(client, auth(users["bob"]), booking.id).status_code == 409

    def test_only_the_booked_student_can_review(
        self, client, users, auth, make_listing, make_application, make_booking
    ):
        _l, booking = self.completed_booking(users, make_listing, make_application, make_booking)
        assert self.review(client, auth(users["fred"]), booking.id).status_code == 403
        assert self.review(client, auth(users["landlord"]), booking.id).status_code == 403

    def test_rating_outside_one_to_five_is_422(
        self, client, users, auth, make_listing, make_application, make_booking
    ):
        _l, booking = self.completed_booking(users, make_listing, make_application, make_booking)
        for rating in (0, 6, -2):
            assert self.review(client, auth(users["bob"]), booking.id, rating=rating).status_code == 422

    def test_blank_comment_is_422(
        self, client, users, auth, make_listing, make_application, make_booking
    ):
        _l, booking = self.completed_booking(users, make_listing, make_application, make_booking)
        assert self.review(client, auth(users["bob"]), booking.id, comment="  ").status_code == 422

    def test_unknown_booking_is_404(self, client, users, auth):
        assert self.review(client, auth(users["bob"]), 9999).status_code == 404

    def test_requires_a_token(self, client, users, make_listing, make_application, make_booking):
        _l, booking = self.completed_booking(users, make_listing, make_application, make_booking)
        response = client.post(f"/api/bookings/{booking.id}/reviews", json={"rating": 4, "comment": "x"})
        assert response.status_code == 401

    def test_reviews_are_paged_five_at_a_time_newest_first_with_overall_average(
        self, client, users, db, make_listing, make_application, make_booking, make_review
    ):
        listing = make_listing(users["landlord"])
        ratings = [5, 4, 3, 2, 1, 5]
        for index, rating in enumerate(ratings):
            student = users["bob" if index % 2 == 0 else "fred"]
            application = make_application(student, listing, status="Completed")
            booking = make_booking(application, status="Completed")
            make_review(booking, rating=rating, comment=f"Review {index}")
        page1 = client.get(f"/api/listings/{listing.id}/reviews").json()
        page2 = client.get(f"/api/listings/{listing.id}/reviews?page=2").json()
        assert [r["comment"] for r in page1["items"]] == [f"Review {i}" for i in (5, 4, 3, 2, 1)]
        assert [r["comment"] for r in page2["items"]] == ["Review 0"]
        assert page1["total_pages"] == 2 and page1["total_count"] == 6
        assert page1["average_rating"] == pytest.approx(sum(ratings) / 6)
        assert page2["average_rating"] == pytest.approx(sum(ratings) / 6)
        assert page1["items"][0]["reviewer"] == "fred"

    def test_listing_with_no_reviews_has_no_average(self, client, users, make_listing):
        listing = make_listing(users["landlord"])
        body = client.get(f"/api/listings/{listing.id}/reviews").json()
        assert body["items"] == [] and body["average_rating"] is None

    def test_reviews_of_an_unverified_listing_are_404(self, client, users, make_listing):
        listing = make_listing(users["landlord"], status="Pending")
        assert client.get(f"/api/listings/{listing.id}/reviews").status_code == 404
