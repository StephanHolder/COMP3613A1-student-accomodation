from decimal import Decimal
from typing import Optional

from sqlmodel import Field, SQLModel


class Listing(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    # BEGIN STUDENT SNIPPET: 
    address: str
    price: Decimal
    security_fee: Decimal
    room_type: str
    amenities: str
    photos: str
    # BEGIN STUDENT SNIPPET: constrain the verification status column
    verification_status: str = Field(default="Pending", max_length=8) 
    # END STUDENT SNIPPET
    rejection_reason: Optional[str] = Field(default=None)
    availability: bool = Field(default=True)
    landlord_id: int = Field(foreign_key="user.id")
    # END STUDENT SNIPPET
