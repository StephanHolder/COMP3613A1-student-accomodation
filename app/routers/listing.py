from decimal import Decimal

from fastapi import File, Form, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from app.dependencies import SessionDep
from app.dependencies.auth import AuthDep
from app.repositories.application import ApplicationRepository
from app.repositories.booking import BookingRepository
from app.repositories.listing import ListingRepository
from app.services.listing_service import ListingService
from app.utilities.flash import flash
from . import router, templates


@router.get(
    "/landlord/listings/new",
    name="new_listing_view",
    response_class=HTMLResponse,
)
async def new_listing_view(request: Request, landlord: AuthDep):
    try:
        ListingService.require_landlord(landlord)
    except PermissionError as exc:
        flash(request, str(exc), "danger")
        return RedirectResponse(
            request.url_for("user_home_view"), status_code=303
        )

    return templates.TemplateResponse(
        request=request,
        name="landlord-listing-form.html",
        context={"user": landlord},
    )


@router.get(
    "/landlord/listings",
    name="current_listings_view",
    response_class=HTMLResponse,
)
async def current_listings_view(
    request: Request,
    landlord: AuthDep,
    db: SessionDep,
    page: int = Query(default=1, ge=1),
):
    repository = ListingRepository(db)
    service = ListingService(repository)
    try:
        listings, pagination = service.get_landlord_listings(landlord, page)
    except PermissionError as exc:
        flash(request, str(exc), "danger")
        return RedirectResponse(
            request.url_for("user_home_view"), status_code=303
        )

    application_repo = ApplicationRepository(db)
    applications, _ = application_repo.get_for_landlord(landlord.id, page=1, limit=100)
    applications_by_listing = {}
    booking_repo = BookingRepository(db)
    bookings_by_application = {}
    for application in applications:
        applications_by_listing.setdefault(application.listing_id, []).append(application)
        if application.id is not None:
            booking = booking_repo.get_for_application(application.id)
            if booking is not None:
                bookings_by_application[application.id] = booking

    return templates.TemplateResponse(
        request=request,
        name="landlord-current-listings.html",
        context={
            "user": landlord,
            "listings": listings,
            "pagination": pagination,
            "applications_by_listing": applications_by_listing,
            "bookings_by_application": bookings_by_application,
        },
    )


@router.post("/landlord/listings", name="create_listing")
def create_listing(
    request: Request,
    landlord: AuthDep,
    db: SessionDep,
    address: str = Form(),
    room_type: str = Form(),
    amenities: str = Form(),
    price: str = Form(),
    security_fee: str = Form(),
    photos: list[UploadFile] = File(default=[]),
):
    # BEGIN STUDENT SNIPPET: complete this as a thin route calling ListingService
    repository = ListingRepository(db)
    service = ListingService(repository)
    try:
        service.submit_listing(
            landlord=landlord,
            address=address,
            room_type=room_type,
            amenities=amenities,
            price=price,
            security_fee=security_fee,
            photos=photos,
        )
    except (PermissionError, ValueError) as exc:
        flash(request, str(exc), "danger")
        return RedirectResponse(
            request.url_for("new_listing_view"), status_code=303
        )
    flash(request, "Listing submitted successfully!", "success")
    return RedirectResponse(
        request.url_for("current_listings_view"), status_code=303
    )
    # END STUDENT SNIPPET
