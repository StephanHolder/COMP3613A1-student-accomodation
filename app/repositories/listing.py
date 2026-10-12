import logging

from decimal import Decimal
from typing import Sequence

from sqlmodel import Session, func, select

from app.models.listing import Listing
from app.utilities.pagination import Pagination

logger = logging.getLogger(__name__)


class ListingRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, listing: Listing) -> Listing:
        try:
            self.db.add(listing)
            self.db.commit()
            self.db.refresh(listing)
            return listing
        except Exception:
            logger.exception("Failed to save listing")
            self.db.rollback()
            raise

    def get_by_id(self, listing_id: int) -> Listing | None:
        return self.db.get(Listing, listing_id)

    def get_pending_listings(
        self, page: int, limit: int, newest_first: bool = True
    ) -> tuple[list[Listing], Pagination]:
        # BEGIN STUDENT SNIPPET: query pending listings with pagination and ordering
        filters = Listing.verification_status == "Pending"
        total_count = self.db.exec(
            select(func.count()).select_from(Listing).where(filters)
        ).one()
        pagination = Pagination(
            total_count=total_count,
            current_page=page,
            limit=limit,
        )
        safe_page = min(pagination.page, max(pagination.total_pages, 1))
        pagination = Pagination(
            total_count=total_count,
            current_page=safe_page,
            limit=limit,
        )
        listings = self.db.exec(   
            select(Listing)
            .where(filters)
            .order_by(Listing.id.desc() if newest_first else Listing.id.asc())
            .offset((pagination.page - 1) * limit)
            .limit(limit)
        ).all()
        return listings, pagination
        # END STUDENT SNIPPET

    def update(self, listing: Listing) -> Listing:
        if listing.id is None:
            raise ValueError("Cannot update a listing without an ID.")
        existing = self.db.get(Listing, listing.id)
        if existing is None:
            raise ValueError("Listing not found.")
        try:
            existing.verification_status = listing.verification_status
            existing.rejection_reason = listing.rejection_reason
            self.db.commit()
            self.db.refresh(existing)
            return existing
        except Exception:
            logger.exception("Failed to update listing")
            self.db.rollback()
            raise

    def get_by_ids(self, listing_ids: Sequence[int]) -> dict[int, Listing]:
        if not listing_ids:
            return {}
        statement = select(Listing).where(Listing.id.in_(listing_ids))
        listings = self.db.exec(statement).all()
        return {listing.id: listing for listing in listings if listing.id is not None}

    def search_verified(
        self,
        page: int,
        limit: int,
        address: str = "",
        room_type: str = "",
        amenities: Sequence[str] = (),
        min_price: Decimal | None = None,
        max_price: Decimal | None = None,
    ) -> tuple[list[Listing], Pagination]:
        filters = [Listing.verification_status == "Verified"]
        if address.strip():
            filters.append(Listing.address.ilike(f"%{address.strip()}%"))
        if room_type.strip():
            filters.append(Listing.room_type.ilike(f"%{room_type.strip()}%"))
        for amenity in amenities:
            if amenity.strip():
                filters.append(Listing.amenities.ilike(f"%{amenity.strip()}%"))
        if min_price is not None:
            filters.append(Listing.price >= min_price)
        if max_price is not None:
            filters.append(Listing.price <= max_price)

        total_count = self.db.exec(
            select(func.count()).select_from(Listing).where(*filters)
        ).one()
        pagination = Pagination(
            total_count=total_count,
            current_page=page,
            limit=limit,
        )
        safe_page = min(pagination.page, max(pagination.total_pages, 1))
        pagination = Pagination(
            total_count=total_count,
            current_page=safe_page,
            limit=limit,
        )
        statement = (
            select(Listing)
            .where(*filters)
            .order_by(Listing.id.desc())
            .offset((pagination.page - 1) * limit)
            .limit(limit)
        )
        return list(self.db.exec(statement).all()), pagination

    def get_verified_room_types(self) -> list[str]:
        statement = (
            select(Listing.room_type)
            .where(Listing.verification_status == "Verified")
            .distinct()
            .order_by(Listing.room_type)
        )
        return list(self.db.exec(statement).all())

    def get_by_landlord_id(
        self, landlord_id: int, page: int, limit: int
    ) -> tuple[list[Listing], Pagination]:
        filters = Listing.landlord_id == landlord_id
        total_count = self.db.exec(
            select(func.count()).select_from(Listing).where(filters)
        ).one()
        pagination = Pagination(
            total_count=total_count,
            current_page=page,
            limit=limit,
        )
        safe_page = min(pagination.page, max(pagination.total_pages, 1))
        pagination = Pagination(
            total_count=total_count,
            current_page=safe_page,
            limit=limit,
        )
        statement = (
            select(Listing)
            .where(filters)
            .order_by(Listing.id.desc())
            .offset((pagination.page - 1) * limit)
            .limit(limit)
        )
        return list(self.db.exec(statement).all()), pagination
