from datetime import date
from typing import Optional

from sqlmodel import Field, SQLModel


class Review(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    # BEGIN STUDENT SNIPPET: add Review fields and foreign keys from docs/report.md
    booking_id: int = Field(foreign_key="booking.id", unique=True)
    student_id: int = Field(foreign_key="user.id")
    listing_id: int = Field(foreign_key="listing.id")
    rating: int
    comment: Optional[str] = None
    review_date: date = Field(default_factory=date.today)
    # END STUDENT SNIPPET
