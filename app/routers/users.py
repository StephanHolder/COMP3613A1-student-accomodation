from fastapi import HTTPException, Request, status

from app.dependencies import SessionDep
from app.dependencies.auth import AuthDep
from . import api_router
from app.services.user_service import UserService
from app.repositories.user import UserRepository
from app.schemas import UserResponse


# API endpoint for listing users (admin only: it exposes every account's email)
@api_router.get("/users", response_model=list[UserResponse])
async def list_users(request: Request, db: SessionDep, user: AuthDep):
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an admin can list users.",
        )
    user_repo = UserRepository(db)
    user_service = UserService(user_repo)
    return user_service.get_all_users()
