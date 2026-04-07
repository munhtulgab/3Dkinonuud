"""
=============================================
  MongoDB Холболт & CRUD Үйлдлүүд
  Motor (async) драйвер ашиглана
=============================================
"""

import motor.motor_asyncio
from datetime import datetime
from typing import Optional
import hashlib
import os


class Database:
    """MongoDB async холболт, бүх CRUD үйлдлүүд"""

    def __init__(self, mongo_uri: str, db_name: str):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(mongo_uri)
        self.db = self.client[db_name]

        # Коллекцууд
        self.movies = self.db["movies"]
        self.users = self.db["users"]
        self.payments = self.db["payments"]

    async def init_indexes(self):
        """Индекс үүсгэх (нэг удаа)"""
        await self.movies.create_index("tmdb_id", unique=True)
        await self.users.create_index("username", unique=True)
        await self.users.create_index("email", unique=True)
        await self.payments.create_index("sender_invoice_no", unique=True)
        await self.payments.create_index("qpay_invoice_id")
        await self.payments.create_index("user_id")

    # ─────────────────────────────────────────
    #  Нууц үг хэшлэх
    # ─────────────────────────────────────────
    @staticmethod
    def hash_password(password: str) -> str:
        salt = os.urandom(16).hex()
        hashed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        return f"{salt}:{hashed}"

    @staticmethod
    def verify_password(password: str, stored_hash: str) -> bool:
        salt, hashed = stored_hash.split(":")
        return hashlib.sha256(f"{salt}{password}".encode()).hexdigest() == hashed

    # ═════════════════════════════════════════
    #  MOVIES CRUD
    # ═════════════════════════════════════════

    async def add_movie(self, movie_data: dict) -> dict:
        """Кино нэмэх (TMDB-аас татсан + админ тохиргоо)"""
        movie_data["created_at"] = datetime.utcnow()
        movie_data["updated_at"] = datetime.utcnow()
        movie_data["is_active"] = True
        result = await self.movies.insert_one(movie_data)
        movie_data["_id"] = str(result.inserted_id)
        return movie_data

    async def get_movie_by_tmdb_id(self, tmdb_id: int) -> Optional[dict]:
        """TMDB ID-аар кино хайх"""
        return await self.movies.find_one({"tmdb_id": tmdb_id})

    async def get_all_movies(self, active_only: bool = True) -> list:
        """Бүх кино жагсаалт"""
        query = {"is_active": True} if active_only else {}
        cursor = self.movies.find(query).sort("created_at", -1)
        movies = []
        async for movie in cursor:
            movie["_id"] = str(movie["_id"])
            movies.append(movie)
        return movies

    async def update_movie(self, tmdb_id: int, update_data: dict) -> bool:
        """Киноны мэдээлэл шинэчлэх"""
        update_data["updated_at"] = datetime.utcnow()
        result = await self.movies.update_one(
            {"tmdb_id": tmdb_id},
            {"$set": update_data}
        )
        return result.modified_count > 0

    async def delete_movie(self, tmdb_id: int) -> bool:
        """Кино устгах (is_active = False)"""
        result = await self.movies.update_one(
            {"tmdb_id": tmdb_id},
            {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0

    # ═════════════════════════════════════════
    #  USERS CRUD
    # ═════════════════════════════════════════

    async def create_user(self, username: str, email: str, password: str, role: str = "user") -> dict:
        """Хэрэглэгч бүртгэх"""
        user = {
            "username": username,
            "email": email,
            "password_hash": self.hash_password(password),
            "role": role,
            "purchased_movies": [],
            "created_at": datetime.utcnow(),
        }
        result = await self.users.insert_one(user)
        user["_id"] = str(result.inserted_id)
        return user

    async def get_user_by_username(self, username: str) -> Optional[dict]:
        """Нэрээр хэрэглэгч хайх"""
        return await self.users.find_one({"username": username})

    async def get_user_by_id(self, user_id: str) -> Optional[dict]:
        """ID-аар хэрэглэгч хайх"""
        from bson import ObjectId
        return await self.users.find_one({"_id": ObjectId(user_id)})

    async def add_purchased_movie(self, user_id: str, tmdb_id: int) -> bool:
        """Худалдаж авсан кино нэмэх"""
        from bson import ObjectId
        result = await self.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$addToSet": {"purchased_movies": tmdb_id}}
        )
        return result.modified_count > 0

    async def has_purchased_movie(self, user_id: str, tmdb_id: int) -> bool:
        """Хэрэглэгч тухайн киног авсан эсэх"""
        from bson import ObjectId
        user = await self.users.find_one(
            {"_id": ObjectId(user_id), "purchased_movies": tmdb_id}
        )
        return user is not None

    # ═════════════════════════════════════════
    #  PAYMENTS CRUD
    # ═════════════════════════════════════════

    async def create_payment(self, payment_data: dict) -> dict:
        """Төлбөрийн бичлэг үүсгэх"""
        payment_data["status"] = "PENDING"
        payment_data["created_at"] = datetime.utcnow()
        payment_data["paid_at"] = None
        result = await self.payments.insert_one(payment_data)
        payment_data["_id"] = str(result.inserted_id)
        return payment_data

    async def get_payment_by_invoice_no(self, sender_invoice_no: str) -> Optional[dict]:
        """sender_invoice_no-аар төлбөр хайх"""
        return await self.payments.find_one({"sender_invoice_no": sender_invoice_no})

    async def get_payment_by_qpay_invoice_id(self, qpay_invoice_id: str) -> Optional[dict]:
        """QPay invoice_id-аар хайх"""
        return await self.payments.find_one({"qpay_invoice_id": qpay_invoice_id})

    async def update_payment_status(self, sender_invoice_no: str, status: str,
                                     payment_id: str = None) -> bool:
        """Төлбөрийн статус шинэчлэх"""
        update = {"$set": {"status": status}}
        if status == "PAID":
            update["$set"]["paid_at"] = datetime.utcnow()
        if payment_id:
            update["$set"]["payment_id"] = payment_id
        result = await self.payments.update_one(
            {"sender_invoice_no": sender_invoice_no},
            update
        )
        return result.modified_count > 0

    async def get_user_payments(self, user_id: str) -> list:
        """Хэрэглэгчийн төлбөрийн түүх"""
        cursor = self.payments.find({"user_id": user_id}).sort("created_at", -1)
        payments = []
        async for payment in cursor:
            payment["_id"] = str(payment["_id"])
            payments.append(payment)
        return payments

    async def ensure_admin_exists(self):
        """Анхны admin хэрэглэгч үүсгэх"""
        admin = await self.get_user_by_username("admin")
        if not admin:
            await self.create_user(
                username="admin",
                email="admin@movieplatform.mn",
                password="admin123",
                role="admin"
            )
            print("✅ Анхны admin хэрэглэгч үүсгэлээ (admin / admin123)")
