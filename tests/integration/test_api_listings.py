"""Listing endpoints: posting, admin verification, public search, landlord views."""

NEW_LISTING = {
    "address": "5 Coffee Street, San Fernando",
    "room_type": "Studio",
    "amenities": "Washing machine",
    "price": 2500,
    "security_fee": 500,
}


class TestPostListing:
    def test_landlord_posts_a_pending_listing(self, client, users, auth):
        response = client.post("/api/listings", json=NEW_LISTING, headers=auth(users["landlord"]))
        assert response.status_code == 201
        body = response.json()
        assert body["verification_status"] == "Pending"
        assert body["availability"] is True
        assert body["landlord_id"] == users["landlord"].id
        assert body["price"] == 2500.0
        assert body["photos"] == []

    def test_decimal_prices_are_kept(self, client, users, auth):
        body = {**NEW_LISTING, "price": 2500.75, "security_fee": 0}
        response = client.post("/api/listings", json=body, headers=auth(users["landlord"]))
        assert response.status_code == 201
        assert response.json()["price"] == 2500.75

    def test_requires_a_token(self, client):
        assert client.post("/api/listings", json=NEW_LISTING).status_code == 401

    def test_students_and_admins_cannot_post(self, client, users, auth):
        for who in ("bob", "admin"):
            response = client.post("/api/listings", json=NEW_LISTING, headers=auth(users[who]))
            assert response.status_code == 403

    def test_negative_price_is_rejected(self, client, users, auth):
        body = {**NEW_LISTING, "price": -10}
        response = client.post("/api/listings", json=body, headers=auth(users["landlord"]))
        assert response.status_code == 422

    def test_zero_price_is_rejected(self, client, users, auth):
        body = {**NEW_LISTING, "price": 0}
        response = client.post("/api/listings", json=body, headers=auth(users["landlord"]))
        assert response.status_code == 422

    def test_blank_address_is_rejected(self, client, users, auth):
        body = {**NEW_LISTING, "address": "   "}
        response = client.post("/api/listings", json=body, headers=auth(users["landlord"]))
        assert response.status_code == 422

    def test_missing_field_is_rejected(self, client, users, auth):
        body = {k: v for k, v in NEW_LISTING.items() if k != "room_type"}
        response = client.post("/api/listings", json=body, headers=auth(users["landlord"]))
        assert response.status_code == 422


class TestAdminVerification:
    def verify(self, client, headers, listing_id, **body):
        return client.put(f"/api/listings/{listing_id}/verification", json=body, headers=headers)

    def test_pending_listing_is_hidden_until_approved(
        self, client, users, auth, make_listing
    ):
        listing = make_listing(users["landlord"], status="Pending")
        assert client.get(f"/api/listings/{listing.id}").status_code == 404
        assert client.get("/api/listings").json()["total_count"] == 0

        response = self.verify(client, auth(users["admin"]), listing.id, decision="approve")
        assert response.status_code == 200
        assert response.json()["verification_status"] == "Verified"
        assert client.get(f"/api/listings/{listing.id}").status_code == 200
        assert client.get("/api/listings").json()["total_count"] == 1

    def test_rejection_stores_the_reason_for_the_landlord(
        self, client, users, auth, make_listing
    ):
        listing = make_listing(users["landlord"], status="Pending")
        response = self.verify(
            client, auth(users["admin"]), listing.id, decision="reject", rejection_reason="Blurry photos"
        )
        assert response.status_code == 200
        mine = client.get("/api/landlord/listings", headers=auth(users["landlord"])).json()
        assert mine["items"][0]["verification_status"] == "Rejected"
        assert mine["items"][0]["rejection_reason"] == "Blurry photos"
        assert client.get(f"/api/listings/{listing.id}").status_code == 404

    def test_rejection_needs_a_reason(self, client, users, auth, make_listing):
        listing = make_listing(users["landlord"], status="Pending")
        response = self.verify(client, auth(users["admin"]), listing.id, decision="reject")
        assert response.status_code == 422

    def test_decision_must_be_approve_or_reject(self, client, users, auth, make_listing):
        listing = make_listing(users["landlord"], status="Pending")
        response = self.verify(client, auth(users["admin"]), listing.id, decision="maybe")
        assert response.status_code == 422

    def test_non_admins_are_forbidden(self, client, users, auth, make_listing):
        listing = make_listing(users["landlord"], status="Pending")
        for who in ("landlord", "bob"):
            response = self.verify(client, auth(users[who]), listing.id, decision="approve")
            assert response.status_code == 403

    def test_requires_a_token(self, client, users, make_listing):
        listing = make_listing(users["landlord"], status="Pending")
        response = client.put(
            f"/api/listings/{listing.id}/verification", json={"decision": "approve"}
        )
        assert response.status_code == 401

    def test_unknown_listing_is_404(self, client, users, auth):
        assert self.verify(client, auth(users["admin"]), 9999, decision="approve").status_code == 404

    def test_a_decided_listing_cannot_be_decided_again(self, client, users, auth, make_listing):
        listing = make_listing(users["landlord"], status="Verified")
        response = self.verify(client, auth(users["admin"]), listing.id, decision="reject", rejection_reason="x")
        assert response.status_code == 409


class TestPendingQueue:
    def test_admin_sees_pending_newest_first(self, client, users, auth, make_listing):
        first = make_listing(users["landlord"], status="Pending", address="First")
        second = make_listing(users["landlord"], status="Pending", address="Second")
        make_listing(users["landlord"], status="Verified", address="Verified one")
        body = client.get("/api/admin/listings/pending", headers=auth(users["admin"])).json()
        assert [i["id"] for i in body["items"]] == [second.id, first.id]
        oldest = client.get(
            "/api/admin/listings/pending?order=oldest", headers=auth(users["admin"])
        ).json()
        assert [i["id"] for i in oldest["items"]] == [first.id, second.id]

    def test_queue_pages_hold_five(self, client, users, auth, make_listing):
        for index in range(7):
            make_listing(users["landlord"], status="Pending", address=f"Pending {index}")
        headers = auth(users["admin"])
        page1 = client.get("/api/admin/listings/pending", headers=headers).json()
        page2 = client.get("/api/admin/listings/pending?page=2", headers=headers).json()
        assert (len(page1["items"]), len(page2["items"])) == (5, 2)
        assert page1["total_pages"] == 2 and page1["total_count"] == 7

    def test_queue_is_admin_only(self, client, users, auth):
        assert client.get("/api/admin/listings/pending", headers=auth(users["landlord"])).status_code == 403
        assert client.get("/api/admin/listings/pending").status_code == 401

    def test_bad_order_value_is_422(self, client, users, auth):
        response = client.get("/api/admin/listings/pending?order=sideways", headers=auth(users["admin"]))
        assert response.status_code == 422


class TestPublicSearch:
    def test_only_verified_listings_appear(self, client, users, make_listing):
        make_listing(users["landlord"], status="Verified", address="Visible")
        make_listing(users["landlord"], status="Pending", address="Hidden pending")
        make_listing(users["landlord"], status="Rejected", address="Hidden rejected")
        items = client.get("/api/listings").json()["items"]
        assert [i["address"] for i in items] == ["Visible"]

    def test_search_is_public(self, client, users, make_listing):
        make_listing(users["landlord"])
        assert client.get("/api/listings").status_code == 200

    def test_filters_by_address_case_insensitively(self, client, users, make_listing):
        make_listing(users["landlord"], address="1 Palm Avenue, Chaguanas")
        make_listing(users["landlord"], address="2 Oak Road, Arima")
        items = client.get("/api/listings?address=palm").json()["items"]
        assert [i["address"] for i in items] == ["1 Palm Avenue, Chaguanas"]

    def test_filters_by_room_type(self, client, users, make_listing):
        make_listing(users["landlord"], room_type="Studio")
        make_listing(users["landlord"], room_type="Shared room")
        assert client.get("/api/listings?room_type=shared").json()["total_count"] == 1

    def test_filters_by_price_range(self, client, users, make_listing):
        for price in ("1500", "2500", "3500"):
            make_listing(users["landlord"], price=price)
        body = client.get("/api/listings?min_price=2000&max_price=3000").json()
        assert [i["price"] for i in body["items"]] == [2500.0]

    def test_filters_by_amenity(self, client, users, make_listing):
        make_listing(users["landlord"], amenities="Wi-Fi, Dryer")
        make_listing(users["landlord"], amenities="Wi-Fi")
        assert client.get("/api/listings?amenities=dryer").json()["total_count"] == 1

    def test_amenity_filters_combine(self, client, users, make_listing):
        make_listing(users["landlord"], amenities="Wi-Fi, Dryer")
        make_listing(users["landlord"], amenities="Dryer")
        assert client.get("/api/listings?amenities=dryer&amenities=wi-fi").json()["total_count"] == 1

    def test_results_page_five_at_a_time_newest_first(self, client, users, make_listing):
        ids = [make_listing(users["landlord"], address=f"Home {i}").id for i in range(7)]
        page1 = client.get("/api/listings").json()
        page2 = client.get("/api/listings?page=2").json()
        assert [i["id"] for i in page1["items"]] == ids[::-1][:5]
        assert [i["id"] for i in page2["items"]] == ids[::-1][5:]
        assert page1["total_pages"] == 2

    def test_page_past_the_end_shows_the_last_page(self, client, users, make_listing):
        for i in range(6):
            make_listing(users["landlord"], address=f"Home {i}")
        body = client.get("/api/listings?page=99").json()
        assert body["page"] == 2 and len(body["items"]) == 1

    def test_min_above_max_is_422(self, client):
        assert client.get("/api/listings?min_price=900&max_price=100").status_code == 422

    def test_non_numeric_price_is_422(self, client):
        assert client.get("/api/listings?min_price=cheap").status_code == 422

    def test_page_zero_is_422(self, client):
        assert client.get("/api/listings?page=0").status_code == 422


class TestListingDetail:
    def test_returns_a_verified_listing(self, client, users, make_listing):
        listing = make_listing(users["landlord"])
        body = client.get(f"/api/listings/{listing.id}").json()
        assert body["address"] == listing.address
        assert body["security_fee"] == 500.0

    def test_unknown_listing_is_404(self, client):
        assert client.get("/api/listings/9999").status_code == 404

    def test_non_integer_id_is_422(self, client):
        assert client.get("/api/listings/abc").status_code == 422


class TestLandlordListings:
    def test_shows_only_own_listings_two_per_page(self, client, users, auth, make_listing):
        for i in range(3):
            make_listing(users["landlord"], address=f"Mine {i}", status="Pending")
        make_listing(users["landlord2"], address="Someone else's")
        headers = auth(users["landlord"])
        page1 = client.get("/api/landlord/listings", headers=headers).json()
        page2 = client.get("/api/landlord/listings?page=2", headers=headers).json()
        assert (len(page1["items"]), len(page2["items"])) == (2, 1)
        assert page1["total_count"] == 3

    def test_students_are_forbidden(self, client, users, auth):
        assert client.get("/api/landlord/listings", headers=auth(users["bob"])).status_code == 403

    def test_requires_a_token(self, client):
        assert client.get("/api/landlord/listings").status_code == 401
