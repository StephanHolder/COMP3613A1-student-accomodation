from typing import Literal

from fastapi import Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.dependencies.session import SessionDep
from app.dependencies.auth import AdminDep
from app.repositories.listing import ListingRepository
from app.repositories.user import UserRepository
from app.services.listing_service import ListingService
from app.utilities.flash import flash
from . import router, templates


@router.get(
    "/admin/listings/pending",
    name="admin_pending_listings_view",
    response_class=HTMLResponse,
)
async def admin_pending_listings_view(
    request: Request,
    admin: AdminDep,
    db: SessionDep,
    page: int = Query(default=1, ge=1),
    order: Literal["newest", "oldest"] = Query(default="newest"),
):
    service = ListingService(ListingRepository(db))
    try:
        listings, pagination = service.get_pending_listings(
            admin=admin,
            page=page,
            limit=5,
            newest_first=order == "newest",
        )
        photos_by_listing = {
            listing.id: service.get_listing_photo_names(listing)
            for listing in listings
            if listing.id is not None
        }
        user_repository = UserRepository(db)
        landlord_usernames = {}
        for listing in listings:
            landlord = user_repository.get_by_id(listing.landlord_id)
            if landlord is not None:
                landlord_usernames[listing.landlord_id] = landlord.username
    except ValueError as error:
        flash(request, str(error), "danger")
        return RedirectResponse(request.url_for("admin_home_view"), status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="admin-pending-listings.html",
        context={
            "user": admin,
            "listings": listings,
            "pagination": pagination,
            "order": order,
            "photos_by_listing": photos_by_listing,
            "landlord_usernames": landlord_usernames,
        },
    )


@router.get("/admin", response_class=HTMLResponse)
async def admin_home_view(
    request: Request,
    user: AdminDep,
    db: SessionDep,
):
    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "user": user
        }
    )


@router.post(
    "/admin/listings/{listing_id}/decision",
    name="submit_listing_decision",
)
def submit_listing_decision(
    request: Request,
    admin: AdminDep,
    db: SessionDep,
    listing_id: int,
    decision: str = Form(),
    rejection_reason: str = Form(default=""),
):
    # BEGIN STUDENT SNIPPET: complete the thin admin decision handler
    repository = ListingRepository(db)
    service = ListingService(repository)
    try:
        service.decide_listing(
            admin=admin,
            listing_id=listing_id,
            decision=decision,
            rejection_reason=rejection_reason,
        )
        flash(request, "Listing decision submitted successfully.")
    except ValueError as error:
        flash(request, str(error), "danger")
    return RedirectResponse(
        request.url_for("admin_pending_listings_view"), status_code=303
    )
    # END STUDENT SNIPPET
