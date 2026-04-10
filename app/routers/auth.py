from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app.core.security import create_access_token, get_current_user, TokenData
from app.models.schemas import LoginResponse

router = APIRouter(prefix="/auth", tags=["auth"])

# ── Demo users (hardcoded) ────────────────────────────────────────────────────
# In production these would be looked up from Supabase

DEMO_USERS = {
    "admin@academiq.demo": {
        "password": "admin123",
        "role": "admin",
        "name": "Admin User",
        "id": "demo-admin-001",
    },
    "mentor@academiq.demo": {
        "password": "mentor123",
        "role": "mentor",
        "name": "Dr. Sarah Chen",
        "id": "demo-mentor-001",
    },
    "student@academiq.demo": {
        "password": "student123",
        "role": "student",
        "name": "Alex Johnson",
        "id": "demo-student-001",
    },
}


@router.post("/login", response_model=LoginResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    OAuth2 password flow. Accepts application/x-www-form-urlencoded.
    username = email address.
    """
    user = DEMO_USERS.get(form_data.username)
    if not user or user["password"] != form_data.password:
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    token = create_access_token({
        "sub": user["id"],
        "role": user["role"],
        "name": user["name"],
        "email": form_data.username,
    })

    return LoginResponse(
        access_token=token,
        role=user["role"],
        name=user["name"],
    )


@router.get("/me")
async def me(current_user: TokenData = Depends(get_current_user)):
    """Return current user info from JWT."""
    return {
        "id": current_user.sub,
        "role": current_user.role,
        "name": current_user.name,
    }


@router.post("/logout")
async def logout():
    """
    JWT is stateless — logout is handled client-side by deleting the token.
    This endpoint exists for frontend compatibility.
    """
    return {"message": "Logged out successfully"}
