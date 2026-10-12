from datetime import date
from typing import Optional

from sqlmodel import Field, SQLModel


class Booking(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    # BEGIN STUDENT SNIPPET: add Booking fields and the accepted-Application link
    application_id: int = Field(foreign_key="application.id", unique=True)
    start_date: date
    move_out_date: Optional[date] = None
    student_id: int = Field(foreign_key="user.id")
    listing_id: int = Field(foreign_key="listing.id")
    status: str = Field(default="Awaiting Payment")  # Possible values: "Awaiting Payment", "Confirmed", "Notice Given", "Completed" 
    # END STUDENT SNIPPET
