from fastapi import FastAPI, Depends, HTTPException, Query, Request, status, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
import os
import uuid
from datetime import datetime, timedelta
from typing import List, Optional
from enum import Enum
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()


import models
from database import SessionLocal, engine, Base

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="SRO Bot API Documentation",
    description="""
    ## SRO Plugins Lisans ve Dosya Yönetim Sistemi
    Bu API dokümantasyonu botun (client) sunucu ile kuracağı iletişimi simüle etmenizi ve test etmenizi sağlar.
    
    ### Temel Özellikler:
    * **Lisans Doğrulama:** Public ID kontrolü.
    * **Dosya İndirme:** Bot için kervan ve SC scriptlerini sunar.
    * **Oturum Yönetimi:** 2 karakter limiti kontrolü.
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)


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

@app.get("/", include_in_schema=False)
async def root_redirect(request: Request):
    session_id = request.cookies.get("admin_session")
    if session_id and session_id in active_admin_sessions:
        return RedirectResponse(url="/admin")
    return FileResponse("public/login.html")


@app.post("/auth/login", include_in_schema=False)
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

@app.post("/auth/logout", include_in_schema=False)
async def logout(request: Request, response: Response):
    session_id = request.cookies.get("admin_session")
    if session_id in active_admin_sessions:
        active_admin_sessions.remove(session_id)
    response.delete_cookie("admin_session")
    return {"message": "Logged out"}


# Dependency



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
    session_count: int = 0

    @classmethod
    def from_orm(cls, obj: models.User):
        user_res = cls(
            id=obj.id,
            username=obj.username,
            public_id=obj.public_id,
            created_at=obj.created_at,
            is_active=obj.is_active,
            session_count=len(obj.sessions)
        )
        return user_res

    class Config:
        from_attributes = True

class FileType(str, Enum):
    CARAVAN = "CARAVAN"
    SC = "SC"

# --- ADMIN ROUTES ---

@app.post("/admin/api/users", response_model=UserResponse, include_in_schema=False)
def create_user(user: UserCreate, db: Session = Depends(get_db), auth: bool = Depends(authenticate_admin)):
    db_user = models.User(username=user.username)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@app.get("/admin/api/users", include_in_schema=False)
def get_users(db: Session = Depends(get_db), auth: bool = Depends(authenticate_admin)):
    db_users = db.query(models.User).all()
    return [UserResponse.from_orm(user) for user in db_users]


@app.delete("/admin/api/users/{user_id}", include_in_schema=False)
def delete_user(user_id: int, db: Session = Depends(get_db), auth: bool = Depends(authenticate_admin)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"message": "User deleted"}


@app.get("/admin/api/sessions/{user_id}", include_in_schema=False)
def get_user_sessions(user_id: int, db: Session = Depends(get_db), auth: bool = Depends(authenticate_admin)):
    return db.query(models.ActiveSession).filter(models.ActiveSession.user_id == user_id).all()

@app.delete("/admin/api/sessions/{session_id}", include_in_schema=False)
def delete_session(session_id: int, db: Session = Depends(get_db), auth: bool = Depends(authenticate_admin)):
    session = db.query(models.ActiveSession).filter(models.ActiveSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    db.delete(session)
    db.commit()
    return {"message": "Session deleted"}

@app.delete("/admin/api/sessions/user/{user_id}", include_in_schema=False)
def delete_all_user_sessions(user_id: int, db: Session = Depends(get_db), auth: bool = Depends(authenticate_admin)):
    db.query(models.ActiveSession).filter(models.ActiveSession.user_id == user_id).delete()
    db.commit()
    return {"message": "All sessions cleared"}

@app.get("/admin/api/files", include_in_schema=False)
def list_available_files(auth: bool = Depends(authenticate_admin)):
    """List all files in caravan and sc directories."""
    files = {
        "CARAVAN": os.listdir("files/caravan") if os.path.exists("files/caravan") else [],
        "SC": os.listdir("files/sc") if os.path.exists("files/sc") else []
    }
    # Filter only .txt or .json files to keep it clean if needed
    files["CARAVAN"] = [f for f in files["CARAVAN"] if f.endswith(('.txt', '.json'))]
    files["SC"] = [f for f in files["SC"] if f.endswith(('.txt', '.json'))]
    return files


# --- PUBLIC API ROUTES ---

enum_files = {
    "CARAVAN": "files/caravan",
    "SC": "files/sc"
}

def cleanup_sessions(db: Session, user_id: int):
    """Delete sessions that haven't been active for more than 5 minutes."""
    expiry_time = datetime.utcnow() - timedelta(minutes=5)
    db.query(models.ActiveSession).filter(
        models.ActiveSession.user_id == user_id,
        models.ActiveSession.last_active < expiry_time
    ).delete()
    db.commit()

@app.get("/api/download", tags=["Bot API"], summary="Dosya İndirme", description="Botun script ve ayar dosyalarını indirmesini sağlar. Lisans kontrolü ve IP sınırlaması içerir.")
async def download_file(
    publicId: str = Query(..., description="Kullanıcının lisans anahtarı (Public ID)"), 
    ip: str = Query(..., description="Botun çalıştığı karakterin IP adresi"), 
    type: FileType = Query(..., description="Dosya türü"), 
    filename: str = Query(..., description="İndirilmek istenen dosya adı"),
    db: Session = Depends(get_db)
):

    # 1. Validate User
    user = db.query(models.User).filter(models.User.public_id == publicId, models.User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid Public ID")

    # 2. Cleanup stale sessions
    cleanup_sessions(db, user.id)

    # 3. Check/Update Session
    session = db.query(models.ActiveSession).filter(
        models.ActiveSession.user_id == user.id,
        models.ActiveSession.ip_address == ip
    ).first()

    if not session:
        # Check active sessions count
        active_count = db.query(models.ActiveSession).filter(models.ActiveSession.user_id == user.id).count()
        
        if active_count >= 2:
            # Delete the oldest session to make room
            oldest_session = db.query(models.ActiveSession).filter(
                models.ActiveSession.user_id == user.id
            ).order_by(models.ActiveSession.last_active.asc()).first()
            if oldest_session:
                db.delete(oldest_session)
                db.commit()
        
        # Create new session
        session = models.ActiveSession(user_id=user.id, ip_address=ip)
        db.add(session)
        db.commit()
        db.refresh(session)
    else:
        # Session exists, update activity
        session.last_active = datetime.utcnow()
        db.commit()

    # 4. Serve File
    if type.upper() not in enum_files:
        raise HTTPException(status_code=400, detail="Invalid enum type. Use CARAVAN or SC.")
    
    file_dir = enum_files[type.upper()]
    file_path = os.path.join(file_dir, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(file_path)

@app.get("/api/validate", tags=["Bot API"], summary="Bağlantı Doğrulama", description="Botun hala aktif bir oturuma sahip olup olmadığını kontrol eder. 2 karakter limiti aşıldığında burası hata döner.")
async def validate_connection(
    publicId: str = Query(..., description="Kullanıcının lisans anahtarı"), 
    ip: str = Query(..., description="Karakter IP adresi"), 
    db: Session = Depends(get_db)
):

    user = db.query(models.User).filter(models.User.public_id == publicId, models.User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid Public ID")

    # Cleanup stale sessions
    cleanup_sessions(db, user.id)

    session = db.query(models.ActiveSession).filter(
        models.ActiveSession.user_id == user.id,
        models.ActiveSession.ip_address == ip
    ).first()

    if not session:
        # Try to create a session if there's room
        active_count = db.query(models.ActiveSession).filter(models.ActiveSession.user_id == user.id).count()
        if active_count < 2:
            session = models.ActiveSession(user_id=user.id, ip_address=ip)
            db.add(session)
            db.commit()
            return {"status": "ok", "message": "Authorized (New session)"}
        else:
            raise HTTPException(status_code=401, detail="Session terminated and limit reached")

    session.last_active = datetime.utcnow()
    db.commit()
    return {"status": "ok", "message": "Authorized"}

@app.get("/api/list", tags=["Bot API"], summary="Dosya Listesi", description="Sunucuda bulunan güncel script ve ayar dosyalarının listesini döndürür.")
async def list_files_public(
    publicId: str = Query(..., description="Lisans anahtarı"), 
    ip: str = Query(..., description="IP adresi"), 
    type: FileType = Query(..., description="İndirilebilir dosya türü"), 
    db: Session = Depends(get_db)
):

    """Public endpoint for the bot to list files of a certain type."""
    # Validate License
    user = db.query(models.User).filter(models.User.public_id == publicId, models.User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Cleanup stale sessions
    cleanup_sessions(db, user.id)

    # Check session
    session = db.query(models.ActiveSession).filter(
        models.ActiveSession.user_id == user.id,
        models.ActiveSession.ip_address == ip
    ).first()
    if not session:
        # Try to create a session if there's room
        active_count = db.query(models.ActiveSession).filter(models.ActiveSession.user_id == user.id).count()
        if active_count < 2:
            session = models.ActiveSession(user_id=user.id, ip_address=ip)
            db.add(session)
            db.commit()
        else:
            raise HTTPException(status_code=401, detail="No active session and limit reached")
    else:
        # Update activity
        session.last_active = datetime.utcnow()
        db.commit()

    # List files
    if type.upper() not in enum_files:
        raise HTTPException(status_code=400, detail="Invalid type")
    
    file_dir = enum_files[type.upper()]
    if not os.path.exists(file_dir):
        return []
    
    files = os.listdir(file_dir)
    # Filter for scripts/jsons
    files = [f for f in files if f.endswith(('.txt', '.json'))]
    return sorted(files)

# Serve static files (Mounting at the end to avoid capturing API routes)

app.mount("/static", StaticFiles(directory="public"), name="static")
app.mount("/admin", StaticFiles(directory="public", html=True), name="admin")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
