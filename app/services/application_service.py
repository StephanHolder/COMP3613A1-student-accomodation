from datetime import date
import re

from app.models.application import Application
from app.models.booking import Booking
from app.models.user import User
from app.repositories.application import ApplicationRepository
from app.repositories.booking import BookingRepository
from app.repositories.listing import ListingRepository
from app.utilities.pagination import Pagination

AGE_INPUT_PATTERN = re.compile(r"^\d+$")


class ApplicationService:
    def __init__(
        self,
        application_repo: ApplicationRepository,
        listing_repo: ListingRepository,
        booking_repo: BookingRepository,
    ):
        self.application_repo = application_repo
        self.listing_repo = listing_repo
        self.booking_repo = booking_repo

    def submit_application(
        self,
        student: User,
        listing_id: int,
        preferred_start_date: date,
    ) -> Application:
        # BEGIN STUDENT SNIPPET: coordinate eligibility, duplicate, and retry rules
        if student.id is None or student.role != "regular_user":
            raise ValueError("Only a registered student can apply.")
        listing = self.listing_repo.get_by_id(listing_id)
        if listing is None:
            raise ValueError("Listing not found.")
        if listing.verification_status != "Verified":
            raise ValueError("This listing is not verified.")
        if not listing.availability:
            raise ValueError("This listing is no longer available.")
        if listing.landlord_id == student.id:
            raise ValueError("You cannot apply to your own listing.")
        existing_application = self.application_repo.get_active_for_student_listing(
            student_id=student.id,
            listing_id=listing_id,
        )
        if existing_application is not None:
            raise ValueError("You already have an active application for this listing.")
        application = Application(
            preferred_start_date=preferred_start_date,
            listing_id=listing_id,
            student_id=student.id,
            status="Applied",
        )
        return self.application_repo.create(application)
        # END STUDENT SNIPPET

    def get_student_applications(
        self, student: User, page: int, limit: int
    ) -> tuple[list[Application], Pagination]:
        if student.id is None or student.role != "regular_user":
            raise PermissionError("Only a registered student can view applications.")
        if page < 1 or limit < 1:
            raise ValueError("Page and page size must be positive.")
        return self.application_repo.get_for_student(student.id, page, limit)

    def request_details(
        self, landlord: User, application_id: int
    ) -> Application:
        # BEGIN STUDENT SNIPPET: coordinate ownership and status for detail requests
        if landlord.id is None or landlord.role != "landlord":
            raise ValueError("Only a landlord can request details.")
        application = self.application_repo.get_by_id(application_id)
        if application is None:
            raise ValueError("Application not found.")
        listing = self.listing_repo.get_by_id(application.listing_id)
        if listing is None:
            raise ValueError("Listing not found for this application.")
        if listing.landlord_id != landlord.id:
            raise ValueError("You are not the owner of this application.") 
        if application.status != "Applied":
            raise ValueError("Details can only be requested for applications that are still Applied.")
        application.status = "Info Requested"
        return self.application_repo.update(application)
        # END STUDENT SNIPPET

    def decide_application(
        self,
        landlord: User,
        application_id: int,
        decision: str,
        decline_reason: str = "",
    ) -> Application:
        # BEGIN STUDENT SNIPPET: coordinate landlord accept or decline behavior
        if landlord.id is None or landlord.role != "landlord":
            raise ValueError("Only a landlord can decide on applications.") 
        if decision not in ["Accepted", "Declined"]:
            raise ValueError("Decision must be either 'Accepted' or 'Declined'.")  
        application = self.application_repo.get_by_id(application_id)
        if application is None:
            raise ValueError("Application not found.")
        listing = self.listing_repo.get_by_id(application.listing_id)
        if listing is None:
            raise ValueError("Listing not found for this application.")
        if listing.landlord_id != landlord.id:
            raise ValueError("You are not the owner of this application.")
        if decision == "Declined":
            if application.status not in ["Applied", "Info Requested", "Info Submitted"]:
                raise ValueError("Only applications that are Applied, Info Requested or Info Submitted can be declined.")
            reason = decline_reason.strip()
            if not reason:
                raise ValueError("Decline reason must be provided when declining an application.")
            application.status = "Declined"
            application.decline_reason = reason
            return self.application_repo.update(application)
        if application.status != "Info Submitted":
            raise ValueError("Only applications with Info Submitted can be accepted.")
        if not listing.availability:
            raise ValueError("This listing is no longer available.")
        if self.booking_repo.get_in_progress_for_listing(listing.id):
            raise ValueError("This listing already has an active booking.")
        application.status = "Accepted"
        booking = Booking(
            application_id=application.id,
            start_date=application.preferred_start_date,
            student_id=application.student_id,
            listing_id=application.listing_id,
            status="Awaiting Payment",
        )
        self.booking_repo.create_for_application(application, booking)
        return application
        # END STUDENT SNIPPET

    def submit_requested_details(
        self,
        student: User,
        application_id: int,
        student_name: str,
        student_age: str,
        purpose_of_stay: str,
    ) -> Application:
        # BEGIN STUDENT SNIPPET: validate and save the requested student details
        if student.id is None or student.role != "regular_user":
            raise ValueError("Only a registered student can submit details.")
        application = self.application_repo.get_by_id(application_id)
        if application is None:
            raise ValueError("Application not found.")
        if application.student_id != student.id:
            raise ValueError("You are not the owner of this application.")
        if application.status != "Info Requested":
            raise ValueError("Details can only be submitted for applications with Info Requested.")
        if not student_name.strip():
            raise ValueError("Student name must be provided.")
        if not AGE_INPUT_PATTERN.fullmatch(student_age):
            raise ValueError("Student age must contain digits only.")
        age = int(student_age)
        if age <= 0:
            raise ValueError("Student age must be a positive integer.")
        if not purpose_of_stay.strip():
            raise ValueError("Purpose of stay must be provided.")
        application.student_name = student_name.strip()
        application.student_age = age
        application.purpose_of_stay = purpose_of_stay.strip()
        application.status = "Info Submitted"
        return self.application_repo.update(application)
        # END STUDENT SNIPPET
