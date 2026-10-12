from datetime import date
from decimal import Decimal

from fastapi import Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.dependencies import SessionDep
from app.dependencies.auth import AuthDep, IsUserLoggedIn
from app.repositories.application import ApplicationRepository
from app.repositories.booking import BookingRepository
from app.repositories.listing import ListingRepository
from app.repositories.review import ReviewRepository
from app.services.application_service import ApplicationService
from app.services.listing_service import ListingService
from app.services.review_service import ReviewService
from app.utilities.flash import flash
from . import router, templates


@router.get("/listings", name="search_listings", response_class=HTMLResponse)
async def search_listings(
    request: Request,
    db: SessionDep,
    user_logged_in: IsUserLoggedIn,
    page: int = Query(default=1, ge=1),
    address: str = "",
    room_type: str = "",
    amenities: list[str] = Query(default=[]),
    min_price: str = "",
    max_price: str = "",
):
    listing_repo = ListingRepository(db)
    service = ListingService(listing_repo)
    try:
        listings, pagination = service.search_verified_listings(
            page=page,
            address=address,
            room_type=room_type,
            amenities=amenities,
            min_price=min_price,
            max_price=max_price,
        )
        room_types = service.get_verified_room_types()
    except ValueError as exc:
        flash(request, str(exc), "danger")
        return RedirectResponse(request.url_for("search_listings"), status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="listing-search.html",
        context={
            "listings": listings,
            "pagination": pagination,
            "room_types": room_types,
            "user_logged_in": user_logged_in,
            "filters": {
                "address": address,
                "room_type": room_type,
                "amenities": amenities,
                "min_price": min_price,
                "max_price": max_price,
            },
        },
    )


@router.get(
    "/listings/{listing_id}",
    name="listing_detail_view",
    response_class=HTMLResponse,
)
async def listing_detail_view(
    request: Request,
    listing_id: int,
    db: SessionDep,
    user_logged_in: IsUserLoggedIn,
    reviews_page: int = Query(default=1, ge=1),
):
    service = ListingService(ListingRepository(db))
    review_service = ReviewService(ReviewRepository(db))
    try:
        listing, photos = service.get_public_listing(listing_id)
        reviews, reviews_pagination, average_rating = (
            review_service.get_listing_reviews(
                listing_id, page=reviews_page, limit=5
            )
        )
    except ValueError as exc:
        flash(request, str(exc), "danger")
        return RedirectResponse(request.url_for("search_listings"), status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="listing-detail.html",
        context={
            "listing": listing,
            "photos": photos,
            "reviews": reviews,
            "reviews_pagination": reviews_pagination,
            "average_rating": average_rating,
            "user_logged_in": user_logged_in,
        },
    )


@router.get("/applications", name="student_applications", response_class=HTMLResponse)
async def student_applications(
    request: Request,
    student: AuthDep,
    db: SessionDep,
    page: int = Query(default=1, ge=1),
):
    application_repo = ApplicationRepository(db)
    listing_repo = ListingRepository(db)
    service = ApplicationService(
        application_repo, listing_repo, BookingRepository(db)
    )
    try:
        applications, pagination = service.get_student_applications(
            student, page=page, limit=5
        )
    except PermissionError as exc:
        flash(request, str(exc), "danger")
        return RedirectResponse(request.url_for("user_home_view"), status_code=303)
    listings_by_id = listing_repo.get_by_ids(
        [application.listing_id for application in applications]
    )
    booking_repo = BookingRepository(db)
    review_repo = ReviewRepository(db)
    bookings_by_application = {
        booking.application_id: booking
        for application in applications
        if application.id is not None
        and (booking := booking_repo.get_for_application(application.id)) is not None
    }
    reviews_by_booking = {
        booking.id: review_repo.get_for_booking(booking.id)
        for booking in bookings_by_application.values()
        if booking.id is not None
    }
    return templates.TemplateResponse(
        request=request,
        name="student-applications.html",
        context={
            "user": student,
            "applications": applications,
            "listings_by_id": listings_by_id,
            "bookings_by_application": bookings_by_application,
            "reviews_by_booking": reviews_by_booking,
            "pagination": pagination,
        },
    )


@router.post("/listings/{listing_id}/apply", name="submit_application")
def submit_application(
    request: Request,
    student: AuthDep,
    db: SessionDep,
    listing_id: int,
    preferred_start_date: date = Form(),
):
    # BEGIN STUDENT SNIPPET: keep this handler thin and call ApplicationService
    application_repo = ApplicationRepository(db)
    listing_repo = ListingRepository(db)
    service = ApplicationService(
        application_repo, listing_repo, BookingRepository(db)
    )
    try:
        service.submit_application(
            student=student,
            listing_id=listing_id,
            preferred_start_date=preferred_start_date,
        )
        flash(request, "Your application was successfully sent.")
        return RedirectResponse(
            request.url_for("student_applications"), status_code=303
        )
    except ValueError as error:
        flash(request, str(error), "danger")
        return RedirectResponse(
            request.url_for("listing_detail_view", listing_id=listing_id),
            status_code=303,
        )
    # END STUDENT SNIPPET


@router.post(
    "/applications/{application_id}/details",
    name="submit_requested_details",
)
def submit_requested_details(
    request: Request,
    student: AuthDep,
    db: SessionDep,
    application_id: int,
    student_name: str = Form(),
    student_age: str = Form(),
    purpose_of_stay: str = Form(),
):
    # BEGIN STUDENT SNIPPET: submit requested details through the service
    application_repo = ApplicationRepository(db)
    listing_repo = ListingRepository(db)
    service = ApplicationService(
        application_repo, listing_repo, BookingRepository(db)
    )
    try:
        service.submit_requested_details(
            student=student,
            application_id=application_id,
            student_name=student_name,
            student_age=student_age,
            purpose_of_stay=purpose_of_stay,
        )
        flash(request, "Your requested details were submitted.")
        return RedirectResponse(
            request.url_for("student_applications"), status_code=303
        )
    except ValueError as error:
        flash(request, str(error), "danger")
        return RedirectResponse(
            request.url_for("student_applications"), status_code=303
        )
    # END STUDENT SNIPPET


@router.post(
    "/applications/{application_id}/request-details",
    name="request_application_details",
)
def request_application_details(
    request: Request,
    landlord: AuthDep,
    db: SessionDep,
    application_id: int,
):
    application_repo = ApplicationRepository(db)
    listing_repo = ListingRepository(db)
    service = ApplicationService(
        application_repo, listing_repo, BookingRepository(db)
    )
    try:
        service.request_details(landlord, application_id)
        flash(request, "Application details were requested from the student.")
    except ValueError as exc:
        flash(request, str(exc), "danger")
    return RedirectResponse(
        request.url_for("current_listings_view"), status_code=303
    )


@router.post(
    "/applications/{application_id}/decide",
    name="decide_application",
)
def decide_application(
    request: Request,
    landlord: AuthDep,
    db: SessionDep,
    application_id: int,
    decision: str = Form(),
    decline_reason: str = Form(default=""),
):
    application_repo = ApplicationRepository(db)
    listing_repo = ListingRepository(db)
    service = ApplicationService(
        application_repo, listing_repo, BookingRepository(db)
    )
    try:
        service.decide_application(
            landlord=landlord,
            application_id=application_id,
            decision=decision,
            decline_reason=decline_reason,
        )
        if decision == "Accepted":
            flash(request, "Application accepted and booking created.")
        else:
            flash(request, "Application declined.")
    except ValueError as exc:
        flash(request, str(exc), "danger")
    return RedirectResponse(
        request.url_for("current_listings_view"), status_code=303
    )
