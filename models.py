"""
=============================================
  MongoDB Schema & Pydantic Models
  Коллекцуудын бүтэц, баталгаажуулалт
=============================================
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import uuid


# ─────────────────────────────────────────────
#  movies коллекц
# ─────────────────────────────────────────────
# {
#   "_id":            ObjectId,
#   "tmdb_id":        int,          # TMDB дахь киноны ID (550 гэх мэт)
#   "title":          str,          # Англи нэр
#   "original_title": str,          # Эх хэл дээрх нэр
#   "overview":       str,          # Тайлбар
#   "poster_path":    str,          # TMDB poster URL (/abc.jpg)
#   "backdrop_path":  str,          # Арын зураг
#   "vote_average":   float,        # Үнэлгээ (0-10)
#   "release_date":   str,          # Нээлтийн огноо
#   "genres":         list[str],    # Жанрууд
#   "runtime":        int,          # Үргэлжлэх хугацаа (минут)
#   "price":          int,          # Үнэ (MNT)
#   "download_url":   str,          # Татах линк
#   "is_active":      bool,         # Идэвхтэй эсэх
#   "created_at":     datetime,     # Нэмсэн огноо
#   "updated_at":     datetime,     # Шинэчилсэн огноо
# }

# ─────────────────────────────────────────────
#  users коллекц
# ─────────────────────────────────────────────
# {
#   "_id":              ObjectId,
#   "username":         str,
#   "email":            str,
#   "password_hash":    str,
#   "role":             str,          # "admin" | "user"
#   "purchased_movies": list[str],    # Худалдаж авсан киноны tmdb_id жагсаалт
#   "created_at":       datetime,
# }

# ─────────────────────────────────────────────
#  payments коллекц
# ─────────────────────────────────────────────
# {
#   "_id":               ObjectId,
#   "user_id":           str,          # Хэрэглэгчийн _id
#   "movie_tmdb_id":     int,          # Киноны TMDB ID
#   "amount":            int,          # Төлбөрийн дүн (MNT)
#   "sender_invoice_no": str,          # Давтагдашгүй нэхэмжлэлийн дугаар
#   "qpay_invoice_id":   str,          # QPay-ээс ирсэн invoice_id
#   "qr_text":           str,          # QR текст
#   "qr_image":          str,          # QR зураг (base64)
#   "qpay_short_url":    str,          # QPay богино URL
#   "qpay_deeplinks":    list[dict],   # Банкны апп-ын линкүүд
#   "status":            str,          # "PENDING" | "PAID" | "FAILED" | "CANCELLED"
#   "payment_id":        str,          # QPay payment_id (төлөгдсөний дараа)
#   "created_at":        datetime,
#   "paid_at":           datetime,     # Төлөгдсөн огноо
# }


# ═══════════════════════════════════════════════
#  Pydantic Models (Request / Response)
# ═══════════════════════════════════════════════

class MovieAddRequest(BaseModel):
    """Админ кино нэмэх хүсэлт"""
    tmdb_id: int = Field(..., description="TMDB дахь киноны ID", example=550)
    price: int = Field(..., ge=0, description="Үнэ (MNT)", example=5000)
    download_url: str = Field(..., description="Татах линк", example="https://example.com/movie.mp4")


class MovieUpdateRequest(BaseModel):
    """Киноны мэдээлэл шинэчлэх"""
    price: Optional[int] = Field(None, ge=0)
    download_url: Optional[str] = None
    is_active: Optional[bool] = None


class UserRegisterRequest(BaseModel):
    """Хэрэглэгч бүртгүүлэх"""
    username: str = Field(..., min_length=3, max_length=30)
    email: str = Field(..., pattern=r'^[^@]+@[^@]+\.[^@]+$')
    password: str = Field(..., min_length=6)


class UserLoginRequest(BaseModel):
    """Хэрэглэгч нэвтрэх"""
    username: str
    password: str


class PurchaseRequest(BaseModel):
    """Худалдаж авах хүсэлт"""
    movie_tmdb_id: int


class PaymentCheckRequest(BaseModel):
    """Төлбөр шалгах хүсэлт"""
    sender_invoice_no: str


class MovieResponse(BaseModel):
    """Киноны мэдээлэл буцаах"""
    tmdb_id: int
    title: str
    original_title: Optional[str] = ""
    overview: str
    poster_path: Optional[str] = ""
    backdrop_path: Optional[str] = ""
    vote_average: float
    release_date: Optional[str] = ""
    genres: list = []
    runtime: Optional[int] = 0
    price: int
    download_url: Optional[str] = None
    is_active: bool = True
    is_purchased: bool = False  # Хэрэглэгч худалдаж авсан эсэх


class InvoiceResponse(BaseModel):
    """QPay invoice үүсгэсний хариу"""
    sender_invoice_no: str
    qpay_invoice_id: str
    qr_image: str
    qpay_short_url: str
    deeplinks: list = []


def generate_invoice_no() -> str:
    """Давтагдашгүй sender_invoice_no үүсгэх"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    short_uuid = uuid.uuid4().hex[:8].upper()
    return f"MV{timestamp}{short_uuid}"
