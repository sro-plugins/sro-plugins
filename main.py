from fastapi import FastAPI, Depends, HTTPException, Query, Request, status, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
import os
import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()


import models
from database import SessionLocal, engine, Base

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="SRO User Manager System")

# Simple In-Memory Session Storage (For production, use Redis or DB)
active_admin_sessions = set()

# Admin Credentials from .env
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "sro123456")

class LoginRequest(BaseModel):
    username: str
    password: str

def authenticate_admin(request: Request):
    session_id = request.cookies.get("admin_session")
    if not session_id or session_id not in active_admin_sessions:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return True

@app.get("/")
async def root_redirect(request: Request):
    session_id = request.cookies.get("admin_session")
    if session_id and session_id in active_admin_sessions:
        return RedirectResponse(url="/admin")
    return FileResponse("public/login.html")

@app.post("/auth/login")
async def login(response: Response, login_data: LoginRequest):
    if login_data.username == ADMIN_USERNAME and login_data.password == ADMIN_PASSWORD:
        session_id = str(uuid.uuid4())
        active_admin_sessions.add(session_id)
        response.set_cookie(
            key="admin_session", 
            value=session_id, 
            httponly=True, 
            samesite="lax",
            max_age=3600 * 24 # 24 hours
        )
        return {"message": "Logged in"}
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.post("/auth/logout")
async def logout(request: Request, response: Response):
    session_id = request.cookies.get("admin_session")
    if session_id in active_admin_sessions:
        active_admin_sessions.remove(session_id)
    response.delete_cookie("admin_session")
    return {"message": "Logged out"}

# Serve static files for admin dashboard
app.mount("/admin", StaticFiles(directory="public", html=True), name="admin")


# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic models
class UserCreate(BaseModel):
    username: str

class UserResponse(BaseModel):
    id: int
    username: str
    public_id: str
    created_at: datetime
    is_active: bool

    class Config:
        from_attributes = True

# --- ADMIN ROUTES ---

@app.post("/admin/api/users", response_model=UserResponse)
def create_user(user: UserCreate, db: Session = Depends(get_db), auth: bool = Depends(authenticate_admin)):
    db_user = models.User(username=user.username)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.get("/admin/api/users", response_model=List[UserResponse])
def get_users(db: Session = Depends(get_db), auth: bool = Depends(authenticate_admin)):
    return db.query(models.User).all()

@app.delete("/admin/api/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), auth: bool = Depends(authenticate_admin)):


    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"message": "User deleted"}

# --- PUBLIC API ROUTES ---

enum_files = {
    "CARAVAN": "files/caravan",
    "SC": "files/sc"
}

@app.get("/api/download")
async def download_file(
    publicId: str, 
    ip: str, 
    type: str, 
    filename: str,
    db: Session = Depends(get_db)
):
    # 1. Validate User
    user = db.query(models.User).filter(models.User.public_id == publicId, models.User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid Public ID")

    # 2. Check/Update Session
    session = db.query(models.ActiveSession).filter(
        models.ActiveSession.user_id == user.id,
        models.ActiveSession.ip_address == ip
    ).first()

    if not session:
        # Check active sessions count
        # For simplicity, we consider any session in table as "active". 
        # In a real app, you might check if last_active > 5 mins ago.
        active_count = db.query(models.ActiveSession).filter(models.ActiveSession.user_id == user.id).count()
        
        if active_count >= 2:
            # Invalidate all existing sessions for this user
            db.query(models.ActiveSession).filter(models.ActiveSession.user_id == user.id).delete()
            db.commit()
            # Note: The other 2 will get 401 on their next request because their session won't exist.
        
        # Create new session
        session = models.ActiveSession(user_id=user.id, ip_address=ip)
        db.add(session)
        db.commit()
        db.refresh(session)
    else:
        # Session exists, update activity
        session.last_active = datetime.utcnow()
        db.commit()

    # 3. Serve File
    if type.upper() not in enum_files:
        raise HTTPException(status_code=400, detail="Invalid enum type. Use CARAVAN or SC.")
    
    file_dir = enum_files[type.upper()]
    file_path = os.path.join(file_dir, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(file_path)

@app.get("/api/validate")
async def validate_connection(publicId: str, ip: str, db: Session = Depends(get_db)):
    """Used by the client to check if they are still authorized."""
    user = db.query(models.User).filter(models.User.public_id == publicId, models.User.is_active == True).first()
    if not user:
        return JSONResponse(status_code=401, content={"detail": "Invalid Public ID"})

    session = db.query(models.ActiveSession).filter(
        models.ActiveSession.user_id == user.id,
        models.ActiveSession.ip_address == ip
    ).first()

    if not session:
        return JSONResponse(status_code=401, content={"detail": "Session terminated (Max 2 connections exceeded elsewhere)"})

    session.last_active = datetime.utcnow()
    db.commit()
    return {"status": "ok", "message": "Authorized"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
