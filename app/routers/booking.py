from datetime import date

from fastapi import Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.dependencies import SessionDep
from app.dependencies.auth import AuthDep
from app.repositories.booking import BookingRepository
from app.services.booking_service import BookingService
from app.utilities.flash import flash
from . import router, templates


@router.get(
    "/bookings/{booking_id}/payment",
    name="booking_payment_view",
    response_class=HTMLResponse,
)
async def booking_payment_view(
    request: Request,
    student: AuthDep,
    db: SessionDep,
    booking_id: int,
):
    # BEGIN STUDENT SNIPPET: keep this handler thin and call BookingService
    booking_repo = BookingRepository(db)
    service = BookingService(booking_repo)
    try:
        booking, listing, payment_total = service.get_for_payment(student=student, booking_id=booking_id)
    except ValueError as error:
        flash(request, str(error), "danger")
        return RedirectResponse(
            request.url_for("student_applications"), status_code=303
        )
    return templates.TemplateResponse(
        request=request,
        name="booking-payment.html",
        context={
            "user": student,
            "booking": booking,
            "listing": listing,
            "payment_total": payment_total,
        },
    )
    # END STUDENT SNIPPET


@router.post("/bookings/{booking_id}/payment", name="submit_booking_payment")
def submit_booking_payment(
    request: Request,
    student: AuthDep,
    db: SessionDep,
    booking_id: int,
    payment_method: str = Form(),
):
    booking_repo = BookingRepository(db)
    service = BookingService(booking_repo)
    try:
        service.submit_payment(
            student=student,
            booking_id=booking_id,
            payment_method=payment_method,
        )
        flash(request, "Payment submitted successfully.", "success")
    except ValueError as exc:
        flash(request, str(exc), "danger")
    return RedirectResponse(
        request.url_for("student_applications"), status_code=303
    )


@router.post("/bookings/{booking_id}/move-out", name="submit_move_out_notice")
def submit_move_out_notice(
    request: Request,
    student: AuthDep,
    db: SessionDep,
    booking_id: int,
    move_out_date: date = Form(),
):
    service = BookingService(BookingRepository(db))
    try:
        service.submit_move_out_notice(student, booking_id, move_out_date)
        flash(request, "Move-out notice submitted.", "success")
    except ValueError as exc:
        flash(request, str(exc), "danger")
    return RedirectResponse(
        request.url_for("student_applications"), status_code=303
    )


@router.post("/bookings/{booking_id}/complete", name="complete_booking")
def complete_booking(
    request: Request,
    landlord: AuthDep,
    db: SessionDep,
    booking_id: int,
):
    service = BookingService(BookingRepository(db))
    try:
        service.complete_booking(landlord, booking_id)
        flash(request, "Booking marked as completed.", "success")
    except ValueError as exc:
        flash(request, str(exc), "danger")
    return RedirectResponse(
        request.url_for("current_listings_view"), status_code=303
    )
