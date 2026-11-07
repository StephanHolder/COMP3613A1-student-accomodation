"""JSON REST API for the three named workflows.

Every handler stays thin: it calls a service, and ``service_errors`` turns the
service's exceptions into HTTP status codes. Resources are nouns; actions that
change a record are ``PUT`` on a sub-resource, creations are ``POST`` -> 201.

    NotFoundError -> 404    ForbiddenError / PermissionError -> 403
    ConflictError -> 409    ValueError (bad input) -> 422
"""

from contextlib import contextmanager
from typing import Literal

from fastapi import HTTPException, Query, status
from sqlalchemy.exc import IntegrityError

from app.dependencies import SessionDep
from app.dependencies.auth import AuthDep
from app.repositories.application import ApplicationRepository
from app.repositories.booking import BookingRepository
from app.repositories.listing import ListingRepository
from app.repositories.review import ReviewRepository
from app.repositories.user import UserRepository
from app.schemas import api as schemas
from app.services.application_service import ApplicationService
from app.services.auth_service import AuthService
from app.services.booking_service import BookingService
from app.services.errors import ConflictError, ForbiddenError, NotFoundError
from app.services.listing_service import ListingService
from app.services.review_service import ReviewService

from . import api_router


@contextmanager
def service_errors():
    """Translate service exceptions into HTTP errors."""
    try:
        yield
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except (ForbiddenError, PermissionError) as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc


def listing_out(listing) -> dict:
    return {
        "id": listing.id,
        "address": listing.address,
        "room_type": listing.room_type,
        "amenities": listing.amenities,
        "price": float(listing.price),
        "security_fee": float(listing.security_fee),
        "photos": ListingService.get_listing_photo_names(listing),
        "verification_status": listing.verification_status,
        "rejection_reason": listing.rejection_reason,
        "availability": listing.availability,
        "landlord_id": listing.landlord_id,
    }


def page_out(items: list, pagination) -> dict:
    return {
        "items": items,
        "page": pagination.page,
        "total_pages": pagination.total_pages,
        "total_count": pagination.total_count,
        "limit": pagination.limit,
    }


def application_service(db) -> ApplicationService:
    return ApplicationService(
        ApplicationRepository(db), ListingRepository(db), BookingRepository(db)
    )


# --------------------------------------------------------------------- auth


@api_router.post(
    "/auth/register",
    response_model=schemas.UserOut,
    status_code=status.HTTP_201_CREATED,
)
def register(body: schemas.RegisterRequest, db: SessionDep):
    service = AuthService(UserRepository(db))
    try:
        return service.register_user(body.username, body.email, body.password)
    except IntegrityError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Username or email already exists"
        ) from exc


@api_router.post("/auth/login", response_model=schemas.TokenResponse)
def login(body: schemas.LoginRequest, db: SessionDep):
    repo = UserRepository(db)
    token = AuthService(repo).authenticate_user(body.username, body.password)
    if not token:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = repo.get_by_username(body.username)
    return {"access_token": token, "username": user.username, "role": user.role}


@api_router.get("/auth/me", response_model=schemas.UserOut)
def me(user: AuthDep):
    return user


# ----------------------------------------------------------------- listings


@api_router.get("/listings")
def search_listings(
    db: SessionDep,
    page: int = Query(default=1, ge=1),
    address: str = "",
    room_type: str = "",
    amenities: list[str] = Query(default=[]),
    min_price: str = "",
    max_price: str = "",
):
    service = ListingService(ListingRepository(db))
    with service_errors():
        listings, pagination = service.search_verified_listings(
            page=page,
            address=address,
            room_type=room_type,
            amenities=amenities,
            min_price=min_price,
            max_price=max_price,
        )
        return page_out([listing_out(item) for item in listings], pagination)


@api_router.get("/listings/{listing_id}", response_model=schemas.ListingOut)
def get_listing(listing_id: int, db: SessionDep):
    service = ListingService(ListingRepository(db))
    with service_errors():
        listing, _photos = service.get_public_listing(listing_id)
        return listing_out(listing)


@api_router.get("/listings/{listing_id}/reviews", response_model=schemas.ReviewPage)
def get_listing_reviews(
    listing_id: int, db: SessionDep, page: int = Query(default=1, ge=1)
):
    listing_service = ListingService(ListingRepository(db))
    review_service = ReviewService(ReviewRepository(db))
    with service_errors():
        listing_service.get_public_listing(listing_id)
        rows, pagination, average = review_service.get_listing_reviews(
            listing_id, page=page, limit=5
        )
    items = [
        {
            "id": review.id,
            "booking_id": review.booking_id,
            "listing_id": review.listing_id,
            "reviewer": reviewer.username,
            "rating": review.rating,
            "comment": review.comment,
            "review_date": review.review_date,
        }
        for review, reviewer in rows
    ]
    return {**page_out(items, pagination), "average_rating": average}


@api_router.post(
    "/listings",
    response_model=schemas.ListingOut,
    status_code=status.HTTP_201_CREATED,
)
def create_listing(body: schemas.ListingCreate, landlord: AuthDep, db: SessionDep):
    service = ListingService(ListingRepository(db))
    with service_errors():
        listing = service.submit_listing(
            landlord=landlord,
            address=body.address,
            room_type=body.room_type,
            amenities=body.amenities,
            price=format(body.price, "f"),
            security_fee=format(body.security_fee, "f"),
            photos=[],
        )
        return listing_out(listing)


@api_router.get("/landlord/listings")
def landlord_listings(
    landlord: AuthDep, db: SessionDep, page: int = Query(default=1, ge=1)
):
    service = ListingService(ListingRepository(db))
    with service_errors():
        listings, pagination = service.get_landlord_listings(landlord, page)
        return page_out([listing_out(item) for item in listings], pagination)


@api_router.get("/admin/listings/pending")
def pending_listings(
    admin: AuthDep,
    db: SessionDep,
    page: int = Query(default=1, ge=1),
    order: Literal["newest", "oldest"] = Query(default="newest"),
):
    service = ListingService(ListingRepository(db))
    with service_errors():
        listings, pagination = service.get_pending_listings(
            admin=admin, page=page, limit=5, newest_first=order == "newest"
        )
        return page_out([listing_out(item) for item in listings], pagination)


@api_router.put("/listings/{listing_id}/verification", response_model=schemas.ListingOut)
def verify_listing(
    listing_id: int,
    body: schemas.VerificationDecision,
    admin: AuthDep,
    db: SessionDep,
):
    service = ListingService(ListingRepository(db))
    with service_errors():
        listing = service.decide_listing(
            admin=admin,
            listing_id=listing_id,
            decision=body.decision,
            rejection_reason=body.rejection_reason,
        )
        return listing_out(listing)


# ------------------------------------------------------------- applications


@api_router.post(
    "/listings/{listing_id}/applications",
    response_model=schemas.ApplicationOut,
    status_code=status.HTTP_201_CREATED,
)
def apply_to_listing(
    listing_id: int,
    body: schemas.ApplicationCreate,
    student: AuthDep,
    db: SessionDep,
):
    with service_errors():
        return application_service(db).submit_application(
            student=student,
            listing_id=listing_id,
            preferred_start_date=body.preferred_start_date,
        )


@api_router.get("/applications")
def student_applications(
    student: AuthDep, db: SessionDep, page: int = Query(default=1, ge=1)
):
    with service_errors():
        applications, pagination = application_service(db).get_student_applications(
            student, page=page, limit=5
        )
        items = [
            schemas.ApplicationOut.model_validate(item).model_dump(mode="json")
            for item in applications
        ]
        return page_out(items, pagination)


@api_router.get("/landlord/applications")
def landlord_applications(
    landlord: AuthDep, db: SessionDep, page: int = Query(default=1, ge=1)
):
    with service_errors():
        applications, pagination = application_service(db).get_landlord_applications(
            landlord, page=page, limit=5
        )
        items = [
            schemas.ApplicationOut.model_validate(item).model_dump(mode="json")
            for item in applications
        ]
        return page_out(items, pagination)


@api_router.post(
    "/applications/{application_id}/detail-requests",
    response_model=schemas.ApplicationOut,
    status_code=status.HTTP_201_CREATED,
)
def request_details(application_id: int, landlord: AuthDep, db: SessionDep):
    with service_errors():
        return application_service(db).request_details(landlord, application_id)


@api_router.put(
    "/applications/{application_id}/details",
    response_model=schemas.ApplicationOut,
)
def submit_details(
    application_id: int,
    body: schemas.ApplicationDetails,
    student: AuthDep,
    db: SessionDep,
):
    with service_errors():
        return application_service(db).submit_requested_details(
            student=student,
            application_id=application_id,
            student_name=body.student_name,
            student_age=str(body.student_age),
            purpose_of_stay=body.purpose_of_stay,
        )


@api_router.put(
    "/applications/{application_id}/decision",
    response_model=schemas.ApplicationOut,
)
def decide_application(
    application_id: int,
    body: schemas.ApplicationDecision,
    landlord: AuthDep,
    db: SessionDep,
):
    with service_errors():
        return application_service(db).decide_application(
            landlord=landlord,
            application_id=application_id,
            decision=body.decision,
            decline_reason=body.decline_reason,
        )


# ----------------------------------------------------------------- bookings


@api_router.get("/bookings/{booking_id}", response_model=schemas.BookingOut)
def get_booking(booking_id: int, user: AuthDep, db: SessionDep):
    with service_errors():
        return BookingService(BookingRepository(db)).get_booking(user, booking_id)


@api_router.get("/applications/{application_id}/booking", response_model=schemas.BookingOut)
def get_booking_for_application(application_id: int, user: AuthDep, db: SessionDep):
    repo = BookingRepository(db)
    with service_errors():
        booking = repo.get_for_application(application_id)
        if booking is None:
            raise NotFoundError("No booking exists for this application.")
        return BookingService(repo).get_booking(user, booking.id)


@api_router.post(
    "/bookings/{booking_id}/payments",
    response_model=schemas.PaymentOut,
    status_code=status.HTTP_201_CREATED,
)
def pay_booking(
    booking_id: int, body: schemas.PaymentCreate, student: AuthDep, db: SessionDep
):
    with service_errors():
        return BookingService(BookingRepository(db)).submit_payment(
            student=student,
            booking_id=booking_id,
            payment_method=body.payment_method,
        )


@api_router.put("/bookings/{booking_id}/move-out", response_model=schemas.BookingOut)
def give_move_out_notice(
    booking_id: int, body: schemas.MoveOutNotice, student: AuthDep, db: SessionDep
):
    with service_errors():
        return BookingService(BookingRepository(db)).submit_move_out_notice(
            student, booking_id, body.move_out_date
        )


@api_router.put("/bookings/{booking_id}/completion", response_model=schemas.BookingOut)
def complete_booking(booking_id: int, landlord: AuthDep, db: SessionDep):
    with service_errors():
        return BookingService(BookingRepository(db)).complete_booking(
            landlord, booking_id
        )


@api_router.post(
    "/bookings/{booking_id}/reviews",
    response_model=schemas.ReviewOut,
    status_code=status.HTTP_201_CREATED,
)
def submit_review(
    booking_id: int, body: schemas.ReviewCreate, student: AuthDep, db: SessionDep
):
    with service_errors():
        review = ReviewService(ReviewRepository(db)).submit_review(
            student=student,
            booking_id=booking_id,
            rating=body.rating,
            comment=body.comment,
        )
        return {
            "id": review.id,
            "booking_id": review.booking_id,
            "listing_id": review.listing_id,
            "reviewer": student.username,
            "rating": review.rating,
            "comment": review.comment,
            "review_date": review.review_date,
        }
