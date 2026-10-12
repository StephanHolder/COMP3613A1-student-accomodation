from datetime import date
from typing import Optional

from sqlmodel import Field, SQLModel


class Application(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    # BEGIN STUDENT SNIPPET: add Application fields and User/Listing foreign keys from docs/report.md
    student_name: Optional[str] = Field(default=None)
    student_age: Optional[int] = Field(default=None)
    purpose_of_stay: Optional[str] = Field(default=None)
    preferred_start_date: date
    status: str = Field(default="Applied")
    decline_reason: Optional[str] = Field(default=None)
    listing_id: int = Field(foreign_key="listing.id")
    student_id: int = Field(foreign_key="user.id")
    # END STUDENT SNIPPET
