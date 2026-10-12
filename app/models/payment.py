from datetime import date
from decimal import Decimal
from typing import Optional

from sqlmodel import Field, SQLModel


class Payment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    # BEGIN STUDENT SNIPPET: add the Payment fields from docs/report.md
    student_id: int = Field(foreign_key="user.id")
    booking_id: int = Field(foreign_key="booking.id")
    type: str
    paid: bool
    amount: Decimal
    payment_date: date
    # END STUDENT SNIPPET
