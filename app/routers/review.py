from fastapi import Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.dependencies import SessionDep
from app.dependencies.auth import AuthDep
from app.repositories.review import ReviewRepository
from app.services.review_service import ReviewService
from app.utilities.flash import flash
from . import router, templates


@router.get(
    "/bookings/{booking_id}/review",
    name="review_form_view",
    response_class=HTMLResponse,
)
async def review_form_view(
    request: Request,
    student: AuthDep,
    db: SessionDep,
    booking_id: int,
):
    # BEGIN STUDENT SNIPPET: keep this handler thin and call ReviewService
    review_repo = ReviewRepository(db)
    service = ReviewService(review_repo)
    try:
        booking, listing = service.get_for_submission(student=student, booking_id=booking_id)
    except ValueError as error:
        flash(request, str(error), "danger")
        return RedirectResponse(
            request.url_for("student_applications"), status_code=303
        )
    return templates.TemplateResponse(
        request=request,
        name="review-form.html",
        context={
            "user": student,
            "booking": booking,
            "listing": listing,
        },
    )
    # END STUDENT SNIPPET


@router.post("/bookings/{booking_id}/review", name="submit_review")
def submit_review(
    request: Request,
    student: AuthDep,
    db: SessionDep,
    booking_id: int,
    rating: int = Form(),
    comment: str = Form(),
):
    review_repo = ReviewRepository(db)
    service = ReviewService(review_repo)
    try:
        service.submit_review(
            student=student,
            booking_id=booking_id,
            rating=rating,
            comment=comment,
        )
        flash(request, "Your review was submitted.", "success")
    except ValueError as exc:
        flash(request, str(exc), "danger")
    return RedirectResponse(
        request.url_for("student_applications"), status_code=303
    )
