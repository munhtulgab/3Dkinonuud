"""
═══════════════════════════════════════════════════════════
  🎬 Movie Platform - Үндсэн FastAPI Програм
  TMDB + QPay v2 + MongoDB
═══════════════════════════════════════════════════════════
"""

import os
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Depends, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from models import (
    MovieAddRequest, MovieUpdateRequest,
    UserRegisterRequest, UserLoginRequest,
    PurchaseRequest, PaymentCheckRequest,
    generate_invoice_no
)

# ─── Тохиргоо ────────────────────────────────
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ─── Глобал обьектууд ────────────────────────
db = None
qpay = None
tmdb = None
_initialized = False


async def get_services():
    """Lazy initialization — анхны хүсэлтэд л холбогдоно"""
    global db, qpay, tmdb, _initialized
    if _initialized:
        return
    _initialized = True

    from database import Database
    from qpay_service import QPayService
    from tmdb_service import TMDBService

    db = Database(
        mongo_uri=os.getenv("MONGO_URI", "mongodb://localhost:27017"),
        db_name=os.getenv("MONGO_DB_NAME", "movie_platform")
    )
    await db.init_indexes()
    await db.ensure_admin_exists()

    qpay = QPayService(
        username=os.getenv("QPAY_USERNAME", "TEST_MERCHANT"),
        password=os.getenv("QPAY_PASSWORD", "123456"),
        invoice_code=os.getenv("QPAY_INVOICE_CODE", "TEST_INVOICE"),
        auth_url=os.getenv("QPAY_AUTH_URL", "https://merchant.qpay.mn/v2/auth/token"),
        invoice_url=os.getenv("QPAY_INVOICE_URL", "https://merchant.qpay.mn/v2/invoice"),
        payment_check_url=os.getenv("QPAY_PAYMENT_CHECK_URL", "https://merchant.qpay.mn/v2/payment/check"),
        callback_url=os.getenv("QPAY_CALLBACK_URL", "https://3dkinonuud.vercel.app/api/payments/callback"),
    )

    tmdb = TMDBService(
        api_key=os.getenv("TMDB_API_KEY", ""),
        base_url=os.getenv("TMDB_BASE_URL", "https://api.themoviedb.org/3")
    )
    logger.info("Services initialized")


# ─── App үүсгэх ──────────────────────────────
app = FastAPI(
    title="🎬 Movie Platform",
    description="TMDB + QPay v2 Киноны платформ",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def init_middleware(request: Request, call_next):
    await get_services()
    return await call_next(request)

# Template
BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# ─── Энгийн session (Cookie-д user_id хадгалах) ──
def get_current_user_id(request: Request) -> str | None:
    """Cookie-с хэрэглэгчийн ID авах"""
    return request.cookies.get("user_id")


def get_current_user_role(request: Request) -> str | None:
    """Cookie-с хэрэглэгчийн role авах"""
    return request.cookies.get("user_role")


# ═══════════════════════════════════════════════
#  HTML ХУУДСУУД
# ═══════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request):
    """Нүүр хуудас - Киноны жагсаалт"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    """Админ хуудас"""
    role = get_current_user_role(request)
    if role != "admin":
        return templates.TemplateResponse("index.html", {"request": request})
    return templates.TemplateResponse("admin.html", {"request": request})


# ═══════════════════════════════════════════════
#  AUTH API
# ═══════════════════════════════════════════════

@app.post("/api/auth/register")
async def register(req: UserRegisterRequest):
    """Хэрэглэгч бүртгүүлэх"""
    existing = await db.get_user_by_username(req.username)
    if existing:
        raise HTTPException(400, "Энэ нэр аль хэдийн бүртгэлтэй байна")

    user = await db.create_user(req.username, req.email, req.password)
    return {
        "success": True,
        "message": "Амжилттай бүртгэгдлээ",
        "user": {
            "id": user["_id"],
            "username": user["username"],
            "role": user["role"]
        }
    }


@app.post("/api/auth/login")
async def login(req: UserLoginRequest):
    """Хэрэглэгч нэвтрэх"""
    user = await db.get_user_by_username(req.username)
    if not user or not db.verify_password(req.password, user["password_hash"]):
        raise HTTPException(401, "Нэр эсвэл нууц үг буруу")

    response = JSONResponse({
        "success": True,
        "message": "Амжилттай нэвтэрлээ",
        "user": {
            "id": str(user["_id"]),
            "username": user["username"],
            "role": user["role"],
            "purchased_movies": user.get("purchased_movies", [])
        }
    })
    # Cookie тохируулах
    response.set_cookie("user_id", str(user["_id"]), max_age=86400 * 7)
    response.set_cookie("user_role", user["role"], max_age=86400 * 7)
    response.set_cookie("username", user["username"], max_age=86400 * 7)
    return response


@app.post("/api/auth/logout")
async def logout():
    """Гарах"""
    response = JSONResponse({"success": True, "message": "Амжилттай гарлаа"})
    response.delete_cookie("user_id")
    response.delete_cookie("user_role")
    response.delete_cookie("username")
    return response


@app.get("/api/auth/me")
async def get_me(request: Request):
    """Одоогийн хэрэглэгчийн мэдээлэл"""
    user_id = get_current_user_id(request)
    if not user_id:
        return {"logged_in": False}

    user = await db.get_user_by_id(user_id)
    if not user:
        return {"logged_in": False}

    return {
        "logged_in": True,
        "user": {
            "id": str(user["_id"]),
            "username": user["username"],
            "role": user["role"],
            "purchased_movies": user.get("purchased_movies", [])
        }
    }


# ═══════════════════════════════════════════════
#  ADMIN: TMDB-ээс кино нэмэх
# ═══════════════════════════════════════════════

@app.post("/api/admin/movies")
async def admin_add_movie(req: MovieAddRequest, request: Request):
    """
    TMDB ID-аар кино нэмэх.
    1. TMDB API-аас мэдээлэл татна
    2. Админы тохируулсан үнэ, линк нэмнэ
    3. MongoDB-д хадгална
    """
    role = get_current_user_role(request)
    if role != "admin":
        raise HTTPException(403, "Зөвхөн админ хандах боломжтой")

    # Аль хэдийн нэмэгдсэн эсэх
    existing = await db.get_movie_by_tmdb_id(req.tmdb_id)
    if existing:
        raise HTTPException(409, f"TMDB ID {req.tmdb_id} бүхий кино аль хэдийн нэмэгдсэн байна")

    # TMDB-ээс мэдээлэл татах
    if not tmdb.api_key:
        raise HTTPException(500, "TMDB API key тохируулаагүй байна (.env файл шалгана уу)")

    try:
        movie_data = await tmdb.fetch_movie(req.tmdb_id)
    except Exception as e:
        raise HTTPException(400, str(e))

    # Админ тохиргоо нэмэх
    movie_data["price"] = req.price
    movie_data["download_url"] = req.download_url

    # MongoDB-д хадгалах
    saved = await db.add_movie(movie_data)

    return {
        "success": True,
        "message": f"'{movie_data['title']}' амжилттай нэмэгдлээ",
        "movie": {
            "tmdb_id": saved["tmdb_id"],
            "title": saved["title"],
            "poster_path": saved["poster_path"],
            "price": saved["price"]
        }
    }


@app.put("/api/admin/movies/{tmdb_id}")
async def admin_update_movie(tmdb_id: int, req: MovieUpdateRequest, request: Request):
    """Киноны үнэ, линк шинэчлэх"""
    role = get_current_user_role(request)
    if role != "admin":
        raise HTTPException(403, "Зөвхөн админ хандах боломжтой")

    update_data = req.dict(exclude_none=True)
    if not update_data:
        raise HTTPException(400, "Шинэчлэх мэдээлэл оруулна уу")

    success = await db.update_movie(tmdb_id, update_data)
    if not success:
        raise HTTPException(404, "Кино олдсонгүй")

    return {"success": True, "message": "Амжилттай шинэчлэгдлээ"}


@app.delete("/api/admin/movies/{tmdb_id}")
async def admin_delete_movie(tmdb_id: int, request: Request):
    """Кино устгах"""
    role = get_current_user_role(request)
    if role != "admin":
        raise HTTPException(403, "Зөвхөн админ хандах боломжтой")

    success = await db.delete_movie(tmdb_id)
    if not success:
        raise HTTPException(404, "Кино олдсонгүй")

    return {"success": True, "message": "Амжилттай устгагдлаа"}


@app.get("/api/admin/tmdb/search")
async def admin_tmdb_search(q: str = Query(..., min_length=1), request: Request = None):
    """TMDB-ээс кино хайх (админ)"""
    if request:
        role = get_current_user_role(request)
        if role != "admin":
            raise HTTPException(403, "Зөвхөн админ хандах боломжтой")

    try:
        results = await tmdb.search_movies(q)
        return results
    except Exception as e:
        raise HTTPException(500, str(e))


# ═══════════════════════════════════════════════
#  MOVIES API (Хэрэглэгч)
# ═══════════════════════════════════════════════

@app.get("/api/movies")
async def get_movies(request: Request):
    """Бүх идэвхтэй киноны жагсаалт"""
    movies = await db.get_all_movies(active_only=True)
    user_id = get_current_user_id(request)

    # Хэрэглэгчийн худалдаж авсан киноны жагсаалт
    purchased = []
    if user_id:
        user = await db.get_user_by_id(user_id)
        if user:
            purchased = user.get("purchased_movies", [])

    # Хариуд is_purchased нэмэх, download_url нууцлах
    result = []
    for m in movies:
        is_purchased = m["tmdb_id"] in purchased
        movie = {
            "tmdb_id": m["tmdb_id"],
            "title": m["title"],
            "original_title": m.get("original_title", ""),
            "overview": m.get("overview", ""),
            "poster_path": m.get("poster_path", ""),
            "backdrop_path": m.get("backdrop_path", ""),
            "vote_average": m.get("vote_average", 0),
            "release_date": m.get("release_date", ""),
            "genres": m.get("genres", []),
            "runtime": m.get("runtime", 0),
            "price": m["price"],
            "is_purchased": is_purchased,
        }
        # Зөвхөн худалдаж авсан бол download_url харуулах
        if is_purchased:
            movie["download_url"] = m.get("download_url", "")
        result.append(movie)

    return {"movies": result}


@app.get("/api/movies/{tmdb_id}")
async def get_movie_detail(tmdb_id: int, request: Request):
    """Нэг киноны дэлгэрэнгүй"""
    movie = await db.get_movie_by_tmdb_id(tmdb_id)
    if not movie:
        raise HTTPException(404, "Кино олдсонгүй")

    user_id = get_current_user_id(request)
    is_purchased = False
    if user_id:
        is_purchased = await db.has_purchased_movie(user_id, tmdb_id)

    result = {
        "tmdb_id": movie["tmdb_id"],
        "title": movie["title"],
        "original_title": movie.get("original_title", ""),
        "overview": movie.get("overview", ""),
        "poster_path": movie.get("poster_path", ""),
        "backdrop_path": movie.get("backdrop_path", ""),
        "vote_average": movie.get("vote_average", 0),
        "release_date": movie.get("release_date", ""),
        "genres": movie.get("genres", []),
        "runtime": movie.get("runtime", 0),
        "price": movie["price"],
        "is_purchased": is_purchased,
    }
    if is_purchased:
        result["download_url"] = movie.get("download_url", "")

    return result


# ═══════════════════════════════════════════════
#  PAYMENT API (QPay v2)
# ═══════════════════════════════════════════════

@app.post("/api/payments/create-invoice")
async def create_payment_invoice(req: PurchaseRequest, request: Request):
    """
    QPay нэхэмжлэх үүсгэх.
    1. Кино мэдээлэл авна
    2. Давтагдашгүй sender_invoice_no үүсгэнэ
    3. QPay API-д нэхэмжлэх үүсгэнэ
    4. MongoDB-д payment бичлэг хадгална
    5. QR код, банкны линкүүд буцаана
    """
    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(401, "Нэвтэрнэ үү")

    # Аль хэдийн авсан эсэх
    already = await db.has_purchased_movie(user_id, req.movie_tmdb_id)
    if already:
        raise HTTPException(400, "Та энэ киног аль хэдийн худалдаж авсан байна")

    # Кино мэдээлэл
    movie = await db.get_movie_by_tmdb_id(req.movie_tmdb_id)
    if not movie:
        raise HTTPException(404, "Кино олдсонгүй")

    # Давтагдашгүй invoice дугаар
    sender_invoice_no = generate_invoice_no()
    description = f"{movie['title']} - {movie['price']} MNT"

    # QPay нэхэмжлэх үүсгэх
    try:
        invoice_data = await qpay.create_invoice(
            sender_invoice_no=sender_invoice_no,
            amount=movie["price"],
            description=description
        )
    except Exception as e:
        raise HTTPException(502, f"QPay нэхэмжлэх үүсгэхэд алдаа: {str(e)}")

    # MongoDB-д хадгалах
    payment_record = {
        "user_id": user_id,
        "movie_tmdb_id": req.movie_tmdb_id,
        "amount": movie["price"],
        "sender_invoice_no": sender_invoice_no,
        "qpay_invoice_id": invoice_data["invoice_id"],
        "qr_text": invoice_data["qr_text"],
        "qr_image": invoice_data["qr_image"],
        "qpay_short_url": invoice_data["qpay_short_url"],
        "qpay_deeplinks": invoice_data["deeplinks"],
    }
    await db.create_payment(payment_record)

    return {
        "success": True,
        "sender_invoice_no": sender_invoice_no,
        "qpay_invoice_id": invoice_data["invoice_id"],
        "qr_image": invoice_data["qr_image"],
        "qpay_short_url": invoice_data["qpay_short_url"],
        "deeplinks": invoice_data["deeplinks"],
        "amount": movie["price"],
        "movie_title": movie["title"]
    }


@app.post("/api/payments/check")
async def check_payment_status(req: PaymentCheckRequest, request: Request):
    """
    Төлбөр шалгах (Interval Polling).
    1. sender_invoice_no-аар payment хайна
    2. QPay payment/check API дуудна
    3. Амжилттай бол user-ийн purchased_movies-д нэмнэ
    """
    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(401, "Нэвтэрнэ үү")

    # Payment бичлэг хайх
    payment = await db.get_payment_by_invoice_no(req.sender_invoice_no)
    if not payment:
        raise HTTPException(404, "Төлбөрийн бичлэг олдсонгүй")

    # Аль хэдийн төлөгдсөн бол
    if payment["status"] == "PAID":
        return {
            "paid": True,
            "message": "Төлбөр аль хэдийн төлөгдсөн",
            "movie_tmdb_id": payment["movie_tmdb_id"]
        }

    # QPay-ээс шалгах
    try:
        check_result = await qpay.check_payment(payment["qpay_invoice_id"])
    except Exception as e:
        raise HTTPException(502, f"QPay шалгахад алдаа: {str(e)}")

    if check_result["paid"]:
        # Төлбөр амжилттай → статус шинэчлэх
        await db.update_payment_status(
            req.sender_invoice_no,
            "PAID",
            payment_id=check_result["payment_id"]
        )
        # Хэрэглэгчийн purchased_movies-д нэмэх
        await db.add_purchased_movie(user_id, payment["movie_tmdb_id"])

        return {
            "paid": True,
            "message": "Төлбөр амжилттай!",
            "movie_tmdb_id": payment["movie_tmdb_id"]
        }
    else:
        return {
            "paid": False,
            "message": "Төлбөр хүлээгдэж байна..."
        }


@app.get("/api/payments/callback")
async def payment_callback(sender_invoice_no: str = Query(None), payment_id: str = Query(None)):
    """
    QPay callback URL.
    Төлбөр амжилттай төлөгдөхөд QPay энэ URL-руу мэдэгдэл илгээнэ.
    """
    logger.info(f"📩 QPay Callback: sender_invoice_no={sender_invoice_no}, payment_id={payment_id}")

    if not sender_invoice_no:
        return {"status": "ignored"}

    payment = await db.get_payment_by_invoice_no(sender_invoice_no)
    if not payment:
        logger.warning(f"⚠️  Callback: payment олдсонгүй - {sender_invoice_no}")
        return {"status": "not_found"}

    if payment["status"] == "PAID":
        return {"status": "already_paid"}

    # QPay-ээс давхар шалгах
    try:
        check_result = await qpay.check_payment(payment["qpay_invoice_id"])
        if check_result["paid"]:
            await db.update_payment_status(
                sender_invoice_no, "PAID",
                payment_id=check_result["payment_id"]
            )
            await db.add_purchased_movie(payment["user_id"], payment["movie_tmdb_id"])
            logger.info(f"✅ Callback: Төлбөр амжилттай - {sender_invoice_no}")
            return {"status": "paid"}
    except Exception as e:
        logger.error(f"❌ Callback шалгахад алдаа: {str(e)}")

    return {"status": "pending"}


@app.get("/api/payments/history")
async def get_payment_history(request: Request):
    """Хэрэглэгчийн төлбөрийн түүх"""
    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(401, "Нэвтэрнэ үү")

    payments = await db.get_user_payments(user_id)
    result = []
    for p in payments:
        result.append({
            "sender_invoice_no": p["sender_invoice_no"],
            "movie_tmdb_id": p["movie_tmdb_id"],
            "amount": p["amount"],
            "status": p["status"],
            "created_at": p["created_at"].isoformat() if p.get("created_at") else "",
            "paid_at": p["paid_at"].isoformat() if p.get("paid_at") else None,
        })

    return {"payments": result}


# ═══════════════════════════════════════════════
#  ADMIN: Бүх кино (идэвхгүй оролцуулаад)
# ═══════════════════════════════════════════════

@app.get("/api/admin/movies")
async def admin_get_all_movies(request: Request):
    """Админ: Бүх кино (идэвхгүй оролцуулаад)"""
    role = get_current_user_role(request)
    if role != "admin":
        raise HTTPException(403, "Зөвхөн админ хандах боломжтой")

    movies = await db.get_all_movies(active_only=False)
    return {"movies": movies}


# ═══════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=True
    )
