"""Request and response bodies for the JSON API under /api."""

from datetime import date
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


class RegisterRequest(BaseModel):
    username: str = Field(min_length=1)
    email: EmailStr
    password: str = Field(min_length=1)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    email: EmailStr
    role: str


class ListingCreate(BaseModel):
    address: str
    room_type: str
    amenities: str
    price: Decimal
    security_fee: Decimal


class ListingOut(BaseModel):
    id: int
    address: str
    room_type: str
    amenities: str
    price: float
    security_fee: float
    photos: list[str]
    verification_status: str
    rejection_reason: Optional[str] = None
    availability: bool
    landlord_id: int


class VerificationDecision(BaseModel):
    decision: Literal["approve", "reject"]
    rejection_reason: str = ""


class ApplicationCreate(BaseModel):
    preferred_start_date: date


class ApplicationDetails(BaseModel):
    student_name: str
    student_age: int
    purpose_of_stay: str


class ApplicationDecision(BaseModel):
    decision: Literal["Accepted", "Declined"]
    decline_reason: str = ""


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    listing_id: int
    student_id: int
    status: str
    preferred_start_date: date
    student_name: Optional[str] = None
    student_age: Optional[int] = None
    purpose_of_stay: Optional[str] = None
    decline_reason: Optional[str] = None


class PaymentCreate(BaseModel):
    payment_method: str


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    booking_id: int
    student_id: int
    type: str
    amount: float
    paid: bool
    payment_date: date


class MoveOutNotice(BaseModel):
    move_out_date: date


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    application_id: int
    listing_id: int
    student_id: int
    start_date: date
    move_out_date: Optional[date] = None
    status: str


class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str


class ReviewOut(BaseModel):
    id: int
    booking_id: int
    listing_id: int
    reviewer: str
    rating: int
    comment: Optional[str] = None
    review_date: date


class ReviewPage(BaseModel):
    items: list[ReviewOut]
    average_rating: Optional[float] = None
    page: int
    total_pages: int
    total_count: int
    limit: int


class Page(BaseModel):
    items: list
    page: int
    total_pages: int
    total_count: int
    limit: int
