import json
import logging
import re
from pathlib import Path
from decimal import Decimal
from decimal import InvalidOperation
from typing import Sequence
from uuid import uuid4

from fastapi import UploadFile

from app.models.listing import Listing
from app.models.user import User
from app.repositories.listing import ListingRepository
from app.utilities.pagination import Pagination

logger = logging.getLogger(__name__)
LANDLORD_LISTINGS_PER_PAGE = 2
UPLOAD_DIR = Path(__file__).resolve().parents[1] / "static" / "uploads"
MAX_PHOTO_COUNT = 5
MAX_PHOTO_SIZE = 5 * 1024 * 1024
PHOTO_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
DECIMAL_INPUT_PATTERN = re.compile(r"^\d+(?:\.\d+)?$")


class ListingService:
    def __init__(self, listing_repo: ListingRepository):
        self.listing_repo = listing_repo

    def submit_listing(
        self,
        landlord: User,
        address: str,
        room_type: str,
        amenities: str,
        price: str,
        security_fee: str,
        photos: Sequence[UploadFile],
    ) -> Listing:
        self.require_landlord(landlord)
        if landlord.id is None:
            raise ValueError("The landlord account is not saved.")
        if not address.strip() or not room_type.strip() or not amenities.strip():
            raise ValueError("Address, room type, and amenities are required.")
        price_value = self._parse_decimal_input(price, "Price")
        security_fee_value = self._parse_decimal_input(security_fee, "Security fee")
        if price_value <= 0 or security_fee_value < 0:
            raise ValueError("Price must be positive and security fee cannot be negative.")
        if len([photo for photo in photos if photo.filename]) > MAX_PHOTO_COUNT:
            raise ValueError("Upload no more than five listing photos.")

        saved_files: list[Path] = []
        try:
            photo_names = self._save_photos(photos, saved_files)
            listing = Listing(
                address=address.strip(),
                room_type=room_type.strip(),
                amenities=amenities.strip(),
                price=price_value,
                security_fee=security_fee_value,
                photos=json.dumps(photo_names),
                verification_status="Pending",
                rejection_reason=None,
                availability=True,
                landlord_id=landlord.id,
            )
            return self.listing_repo.create(listing)
        except Exception:
            for path in saved_files:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    logger.exception("Failed to remove an unreferenced listing photo")
            raise

    @staticmethod
    def _parse_decimal_input(value: str, label: str) -> Decimal:
        if not DECIMAL_INPUT_PATTERN.fullmatch(value):
            raise ValueError(f"{label} must contain only digits and one decimal point.")
        try:
            return Decimal(value)
        except InvalidOperation as exc:
            raise ValueError(f"{label} must be a valid number.") from exc

    def get_landlord_listings(
        self, landlord: User, page: int
    ) -> tuple[list[Listing], Pagination]:
        self.require_landlord(landlord)
        if landlord.id is None:
            raise ValueError("The landlord account is not saved.")
        return self.listing_repo.get_by_landlord_id(
            landlord.id,
            page=page,
            limit=LANDLORD_LISTINGS_PER_PAGE,
        )

    def get_public_listing(self, listing_id: int) -> tuple[Listing, list[str]]:
        listing = self.listing_repo.get_by_id(listing_id)
        if listing is None or listing.verification_status != "Verified":
            raise ValueError("This verified listing could not be found.")
        return listing, self.get_listing_photo_names(listing)

    def get_pending_listings(
        self,
        admin: User,
        page: int,
        limit: int,
        newest_first: bool = True,
    ) -> tuple[list[Listing], Pagination]:
        if admin.role != "admin":
            raise ValueError("Only an admin can view pending listings.")
        if page < 1 or limit < 1:
            raise ValueError("Page and page size must be positive.")
        return self.listing_repo.get_pending_listings(
            page=page,
            limit=limit,
            newest_first=newest_first,
        )

    def decide_listing(
        self,
        admin: User,
        listing_id: int,
        decision: str,
        rejection_reason: str = "",
    ) -> Listing:
        if admin.role != "admin":
            raise ValueError("Only an admin can decide a listing.")
        if decision not in {"approve", "reject"}:
            raise ValueError("Choose either approve or reject.")

        listing = self.listing_repo.get_by_id(listing_id)
        if listing is None:
            raise ValueError("Listing not found.")
        if listing.verification_status != "Pending":
            raise ValueError("Only pending listings can be reviewed.")

        if decision == "approve":
            listing.verification_status = "Verified"
            listing.rejection_reason = None
        else:
            reason = rejection_reason.strip()
            if not reason:
                raise ValueError("Enter a reason for rejecting this listing.")
            listing.verification_status = "Rejected"
            listing.rejection_reason = reason
        return self.listing_repo.update(listing)

    @staticmethod
    def get_listing_photo_names(listing: Listing) -> list[str]:
        try:
            photos = json.loads(listing.photos)
        except (TypeError, json.JSONDecodeError) as exc:
            logger.exception("Invalid photo data for listing %s", listing.id)
            raise ValueError("This listing’s photos could not be loaded.") from exc
        if not isinstance(photos, list) or not all(
            isinstance(photo, str) for photo in photos
        ):
            raise ValueError("This listing’s photos could not be loaded.")
        return photos

    def search_verified_listings(
        self,
        page: int,
        address: str = "",
        room_type: str = "",
        amenities: Sequence[str] = (),
        min_price: str = "",
        max_price: str = "",
    ) -> tuple[list[Listing], Pagination]:
        min_value = self._parse_price(min_price)
        max_value = self._parse_price(max_price)
        if min_value is not None and max_value is not None and min_value > max_value:
            raise ValueError("Minimum price cannot exceed maximum price.")
        return self.listing_repo.search_verified(
            page=page,
            limit=5,
            address=address,
            room_type=room_type,
            amenities=amenities,
            min_price=min_value,
            max_price=max_value,
        )

    def get_verified_room_types(self) -> list[str]:
        return self.listing_repo.get_verified_room_types()

    @staticmethod
    def require_landlord(landlord: User) -> None:
        if landlord.role != "landlord":
            raise PermissionError("Only a landlord account can post a listing.")

    @staticmethod
    def _save_photos(
        photos: Sequence[UploadFile], saved_files: list[Path]
    ) -> list[str]:
        photo_names: list[str] = []
        for photo in photos:
            if not photo.filename:
                continue
            content_type = (photo.content_type or "").split(";", 1)[0].lower()
            extension = PHOTO_TYPES.get(content_type)
            if extension is None:
                raise ValueError("Photos must be JPEG, PNG, WebP, or GIF images.")
            content = photo.file.read(MAX_PHOTO_SIZE + 1)
            if not content:
                raise ValueError("Uploaded photos cannot be empty.")
            if len(content) > MAX_PHOTO_SIZE:
                raise ValueError("Each photo must be 5 MB or smaller.")

            filename = f"{uuid4().hex}{extension}"
            path = UPLOAD_DIR / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            saved_files.append(path)
            path.write_bytes(content)
            photo_names.append(filename)
        return photo_names

    @staticmethod
    def _parse_price(value: str) -> Decimal | None:
        if not value.strip():
            return None
        try:
            price = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError("Enter a valid price range.") from exc
        if not price.is_finite() or price < 0:
            raise ValueError("Enter a finite, non-negative price.")
        return price
