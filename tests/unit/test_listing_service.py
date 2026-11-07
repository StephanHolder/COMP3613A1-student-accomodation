"""ListingService rules: posting, photo handling, admin verification, search."""

import io
import json
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services import listing_service as listing_module
from app.services.errors import ConflictError, ForbiddenError, NotFoundError
from app.services.listing_service import ListingService


def fake_photo(name="room.jpg", content_type="image/jpeg", data=b"image-bytes"):
    return SimpleNamespace(filename=name, content_type=content_type, file=io.BytesIO(data))


def valid_fields(**overrides):
    fields = dict(
        address="12 Main Street",
        room_type="Studio",
        amenities="Wi-Fi",
        price="2500",
        security_fee="500",
        photos=[],
    )
    fields.update(overrides)
    return fields


@pytest.fixture()
def service(listing_repo):
    return ListingService(listing_repo)


@pytest.fixture()
def upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(listing_module, "UPLOAD_DIR", tmp_path)
    return tmp_path


class TestSubmitListing:
    def test_creates_a_pending_available_listing(self, service, landlord):
        listing = service.submit_listing(landlord=landlord, **valid_fields())
        assert listing.verification_status == "Pending"
        assert listing.availability is True
        assert listing.landlord_id == landlord.id
        assert listing.price == Decimal("2500")

    def test_trims_whitespace_from_text_fields(self, service, landlord):
        listing = service.submit_listing(landlord=landlord, **valid_fields(address="  1 Rd  "))
        assert listing.address == "1 Rd"

    def test_only_landlords_can_post(self, service, student):
        with pytest.raises(PermissionError):
            service.submit_listing(landlord=student, **valid_fields())

    @pytest.mark.parametrize("field", ["address", "room_type", "amenities"])
    def test_blank_text_fields_are_rejected(self, service, landlord, field):
        with pytest.raises(ValueError, match="required"):
            service.submit_listing(landlord=landlord, **valid_fields(**{field: "   "}))

    @pytest.mark.parametrize("bad", ["abc", "-5", "1e3", "1.2.3", "", "5,00"])
    def test_price_must_be_plain_decimal_digits(self, service, landlord, bad):
        with pytest.raises(ValueError, match="Price"):
            service.submit_listing(landlord=landlord, **valid_fields(price=bad))

    def test_security_fee_must_be_plain_decimal_digits(self, service, landlord):
        with pytest.raises(ValueError, match="Security fee"):
            service.submit_listing(landlord=landlord, **valid_fields(security_fee="-1"))

    def test_price_must_be_positive(self, service, landlord):
        with pytest.raises(ValueError, match="positive"):
            service.submit_listing(landlord=landlord, **valid_fields(price="0"))

    def test_zero_security_fee_is_allowed(self, service, landlord):
        listing = service.submit_listing(landlord=landlord, **valid_fields(security_fee="0"))
        assert listing.security_fee == Decimal("0")

    def test_more_than_five_photos_is_rejected(self, service, landlord, upload_dir):
        photos = [fake_photo(f"{i}.jpg") for i in range(6)]
        with pytest.raises(ValueError, match="five"):
            service.submit_listing(landlord=landlord, **valid_fields(photos=photos))

    def test_photos_are_saved_and_listed_as_json(self, service, landlord, upload_dir):
        listing = service.submit_listing(
            landlord=landlord, **valid_fields(photos=[fake_photo(), fake_photo("b.png", "image/png")])
        )
        names = json.loads(listing.photos)
        assert len(names) == 2
        assert names[0].endswith(".jpg") and names[1].endswith(".png")
        assert all((upload_dir / name).exists() for name in names)

    def test_non_image_upload_is_rejected(self, service, landlord, upload_dir):
        with pytest.raises(ValueError, match="JPEG"):
            service.submit_listing(
                landlord=landlord,
                **valid_fields(photos=[fake_photo("x.pdf", "application/pdf")]),
            )

    def test_empty_upload_is_rejected(self, service, landlord, upload_dir):
        with pytest.raises(ValueError, match="empty"):
            service.submit_listing(
                landlord=landlord, **valid_fields(photos=[fake_photo(data=b"")])
            )

    def test_oversized_upload_is_rejected(self, service, landlord, upload_dir, monkeypatch):
        monkeypatch.setattr(listing_module, "MAX_PHOTO_SIZE", 10)
        with pytest.raises(ValueError, match="5 MB"):
            service.submit_listing(
                landlord=landlord, **valid_fields(photos=[fake_photo(data=b"x" * 11)])
            )

    def test_files_are_cleaned_up_when_a_later_photo_fails(
        self, service, landlord, upload_dir
    ):
        photos = [fake_photo(), fake_photo("bad.pdf", "application/pdf")]
        with pytest.raises(ValueError):
            service.submit_listing(landlord=landlord, **valid_fields(photos=photos))
        assert list(upload_dir.iterdir()) == []


class TestDecideListing:
    def test_admin_approves_a_pending_listing(self, service, admin, listing):
        listing.verification_status = "Pending"
        service.listing_repo.get_by_id.return_value = listing
        result = service.decide_listing(admin, 1, "approve")
        assert result.verification_status == "Verified"
        assert result.rejection_reason is None

    def test_rejection_needs_a_reason(self, service, admin, listing):
        listing.verification_status = "Pending"
        service.listing_repo.get_by_id.return_value = listing
        with pytest.raises(ValueError, match="reason"):
            service.decide_listing(admin, 1, "reject", "   ")
        assert listing.verification_status == "Pending"

    def test_rejection_stores_the_reason(self, service, admin, listing):
        listing.verification_status = "Pending"
        service.listing_repo.get_by_id.return_value = listing
        result = service.decide_listing(admin, 1, "reject", " Photos unclear ")
        assert result.verification_status == "Rejected"
        assert result.rejection_reason == "Photos unclear"

    def test_only_admins_can_decide(self, service, landlord):
        with pytest.raises(ForbiddenError):
            service.decide_listing(landlord, 1, "approve")

    def test_decision_must_be_approve_or_reject(self, service, admin):
        with pytest.raises(ValueError, match="approve or reject"):
            service.decide_listing(admin, 1, "maybe")

    def test_missing_listing_is_not_found(self, service, admin):
        service.listing_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            service.decide_listing(admin, 1, "approve")

    def test_listing_already_decided_conflicts(self, service, admin, listing):
        service.listing_repo.get_by_id.return_value = listing  # already Verified
        with pytest.raises(ConflictError):
            service.decide_listing(admin, 1, "approve")


class TestQueriesAndSearch:
    def test_public_listing_must_be_verified(self, service, listing):
        listing.verification_status = "Pending"
        service.listing_repo.get_by_id.return_value = listing
        with pytest.raises(NotFoundError):
            service.get_public_listing(1)

    def test_public_listing_returns_photo_names(self, service, listing):
        listing.photos = json.dumps(["a.jpg"])
        service.listing_repo.get_by_id.return_value = listing
        _listing, photos = service.get_public_listing(1)
        assert photos == ["a.jpg"]

    def test_corrupt_photo_json_is_reported(self, listing):
        listing.photos = "not json"
        with pytest.raises(ValueError, match="photos"):
            ListingService.get_listing_photo_names(listing)

    def test_pending_queue_is_admin_only(self, service, landlord):
        with pytest.raises(ForbiddenError):
            service.get_pending_listings(landlord, page=1, limit=5)

    def test_pending_queue_rejects_bad_paging(self, service, admin):
        with pytest.raises(ValueError):
            service.get_pending_listings(admin, page=0, limit=5)

    def test_landlord_listings_use_two_per_page(self, service, landlord):
        service.get_landlord_listings(landlord, page=2)
        service.listing_repo.get_by_landlord_id.assert_called_once_with(
            landlord.id, page=2, limit=2
        )

    def test_search_passes_decimal_bounds_and_five_per_page(self, service):
        service.search_verified_listings(page=1, min_price="1000", max_price="3000.50")
        kwargs = service.listing_repo.search_verified.call_args.kwargs
        assert kwargs["min_price"] == Decimal("1000")
        assert kwargs["max_price"] == Decimal("3000.50")
        assert kwargs["limit"] == 5

    def test_search_rejects_min_above_max(self, service):
        with pytest.raises(ValueError, match="Minimum"):
            service.search_verified_listings(page=1, min_price="500", max_price="100")

    @pytest.mark.parametrize("bad", ["abc", "-1", "nan", "inf"])
    def test_search_rejects_invalid_prices(self, service, bad):
        with pytest.raises(ValueError):
            service.search_verified_listings(page=1, min_price=bad)
