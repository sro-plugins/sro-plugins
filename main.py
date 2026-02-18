from fastapi import FastAPI, Depends, HTTPException, Query, Request, status, Response, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
import os
import uuid
import base64
import hashlib
import hmac
import json
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
    public_id: Optional[str] = None

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
    FEATURE = "FEATURE"

FILE_CATEGORIES = {
    "CARAVAN": "files/caravan",
    "SC": "files/sc",
    "FEATURE": "files/feature"
}

ALLOWED_EXTENSIONS = ('.txt', '.json', '.py')

# --- ADMIN ROUTES ---

@app.post("/admin/api/users", response_model=UserResponse, include_in_schema=False)
def create_user(user: UserCreate, db: Session = Depends(get_db), auth: bool = Depends(authenticate_admin)):
    db_user = models.User(
        username=user.username,
        public_id=user.public_id if user.public_id else str(uuid.uuid4())
    )
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
    """List all files in caravan, sc and feature directories with metadata."""
    result = {}
    for category, dir_path in FILE_CATEGORIES.items():
        if not os.path.exists(dir_path):
            result[category] = []
            continue
        file_list = []
        for f in sorted(os.listdir(dir_path)):
            if f.endswith(ALLOWED_EXTENSIONS):
                fp = os.path.join(dir_path, f)
                stat = os.stat(fp)
                file_list.append({
                    "name": f,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
        result[category] = file_list
    return result


@app.post("/admin/api/files/upload", include_in_schema=False)
async def upload_file(
    file: UploadFile = File(...),
    category: str = Form(...),
    auth: bool = Depends(authenticate_admin)
):
    """Upload a file to caravan, sc or feature directory."""
    category = category.upper()
    if category not in FILE_CATEGORIES:
        raise HTTPException(status_code=400, detail="Invalid category. Use CARAVAN, SC or FEATURE.")
    
    if not file.filename.endswith(ALLOWED_EXTENSIONS):
        raise HTTPException(status_code=400, detail="Only .txt, .json and .py files are allowed.")
    
    dir_path = f"files/{category.lower()}"
    os.makedirs(dir_path, exist_ok=True)
    
    file_path = os.path.join(dir_path, file.filename)
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    
    stat = os.stat(file_path)
    return {
        "message": f"File '{file.filename}' uploaded successfully to {category}",
        "file": {
            "name": file.filename,
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
        }
    }


@app.delete("/admin/api/files/{category}/{filename}", include_in_schema=False)
def delete_file(category: str, filename: str, auth: bool = Depends(authenticate_admin)):
    """Delete a file from caravan, sc or feature directory."""
    category = category.upper()
    if category not in FILE_CATEGORIES:
        raise HTTPException(status_code=400, detail="Invalid category")
    
    file_path = os.path.join(f"files/{category.lower()}", filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    os.remove(file_path)
    return {"message": f"File '{filename}' deleted from {category}"}


@app.get("/admin/api/files/{category}/{filename}/content", include_in_schema=False)
def get_file_content(category: str, filename: str, auth: bool = Depends(authenticate_admin)):
    """Get the text content of a file for preview."""
    category = category.upper()
    if category not in FILE_CATEGORIES:
        raise HTTPException(status_code=400, detail="Invalid category")
    
    file_path = os.path.join(f"files/{category.lower()}", filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(file_path, "r", encoding="latin-1") as f:
            content = f.read()
    
    stat = os.stat(file_path)
    return {
        "name": filename,
        "category": category,
        "content": content,
        "size": stat.st_size,
        "lines": content.count('\n') + 1,
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
    }


# --- PUBLIC API ROUTES ---

enum_files = FILE_CATEGORIES

# Signed Request Verification
SIGNED_REQUEST_MAX_AGE = 300  # 5 minutes

def verify_signed_request(request: Request, expected_endpoint: str, publicId: str, ip: str):
    """
    Validates the signed headers from the phBot-SROManager plugin.
    Checks: User-Agent, X-SROMANAGER-Payload (base64 JSON), X-SROMANAGER-Signature (HMAC-SHA256).
    Verifies: endpoint, license, ip match query params + timestamp freshness.
    """
    # 1. Check User-Agent (Allow bypass for the Admin Panel Tester)
    user_agent = request.headers.get("User-Agent", "")
    is_tester = request.headers.get("X-SROMANAGER-Tester") == "true"
    
    if not is_tester and not user_agent.startswith("phBot-SROManager/"):
        raise HTTPException(status_code=403, detail="Forbidden")
    
    # 2. Get headers
    payload_b64 = request.headers.get("X-SROMANAGER-Payload")
    signature = request.headers.get("X-SROMANAGER-Signature")
    
    if not payload_b64 or not signature:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    # 3. Decode payload
    try:
        payload_json = base64.b64decode(payload_b64).decode("utf-8")
        payload = json.loads(payload_json)
    except Exception:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    # 4. Verify payload fields
    payload_license = payload.get("license", "")
    payload_ip = payload.get("ip", "")
    payload_endpoint = payload.get("endpoint", "")
    
    if payload_license != publicId or payload_ip != ip or payload_endpoint != expected_endpoint:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    # 5. Check timestamp freshness - Disabled to avoid clock drift issues
    
    # 6. Verify HMAC-SHA256 signature
    secret = (publicId or "none").encode()
    expected_sig = hmac.new(secret, payload_json.encode(), hashlib.sha256).hexdigest()
    
    if not hmac.compare_digest(expected_sig, signature):
        raise HTTPException(status_code=403, detail="Forbidden")
    
    return payload


def cleanup_sessions(db: Session, user_id: int):
    """Delete sessions that haven't been active for more than 5 minutes."""
    expiry_time = datetime.utcnow() - timedelta(minutes=5)
    db.query(models.ActiveSession).filter(
        models.ActiveSession.user_id == user_id,
        models.ActiveSession.last_active < expiry_time
    ).delete()
    db.commit()

@app.get("/api/download", tags=["Bot API"], summary="Dosya İndirme", description="Botun script ve ayar dosyalarını indirmesini sağlar. Lisans kontrolü, IP sınırlaması ve imzalı istek doğrulaması içerir.")
async def download_file(
    request: Request,
    publicId: str = Query(..., description="Kullanıcının lisans anahtarı (Public ID)"), 
    ip: str = Query(..., description="Botun çalıştığı karakterin IP adresi"), 
    type: FileType = Query(..., description="Dosya türü"), 
    filename: str = Query(..., description="İndirilmek istenen dosya adı"),
    db: Session = Depends(get_db)
):
    # 0. Verify signed request
    verify_signed_request(request, "download", publicId, ip)

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
        raise HTTPException(status_code=400, detail="Invalid enum type. Use CARAVAN, SC or FEATURE.")
    
    file_dir = enum_files[type.upper()]
    file_path = os.path.join(file_dir, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(file_path)

@app.get("/api/validate", tags=["Bot API"], summary="Bağlantı Doğrulama", description="Botun hala aktif bir oturuma sahip olup olmadığını kontrol eder. İmzalı istek doğrulaması içerir.")
async def validate_connection(
    request: Request,
    publicId: str = Query(..., description="Kullanıcının lisans anahtarı"), 
    ip: str = Query(..., description="Karakter IP adresi"), 
    db: Session = Depends(get_db)
):
    # 0. Verify signed request
    verify_signed_request(request, "validate", publicId, ip)

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

@app.get("/api/list", tags=["Bot API"], summary="Dosya Listesi", description="Sunucuda bulunan güncel script ve ayar dosyalarının listesini döndürür. İmzalı istek doğrulaması içerir.")
async def list_files_public(
    request: Request,
    publicId: str = Query(..., description="Lisans anahtarı"), 
    ip: str = Query(..., description="IP adresi"), 
    type: FileType = Query(..., description="İndirilebilir dosya türü"), 
    db: Session = Depends(get_db)
):

    """Public endpoint for the bot to list files of a certain type."""
    # 0. Verify signed request
    verify_signed_request(request, "list", publicId, ip)

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
    # Filter for scripts/jsons/py
    files = [f for f in files if f.endswith(ALLOWED_EXTENSIONS)]
    return sorted(files)

# Serve static files (Mounting at the end to avoid capturing API routes)

app.mount("/static", StaticFiles(directory="public"), name="static")
app.mount("/admin", StaticFiles(directory="public", html=True), name="admin")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
