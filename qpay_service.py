"""
=============================================
  QPay v2 Төлбөрийн Сервис
  Token авах, Invoice үүсгэх, Төлбөр шалгах
=============================================
"""

import httpx
import base64
from datetime import datetime, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class QPayService:
    """QPay v2 API-тай харилцах сервис"""

    def __init__(self, username: str, password: str, invoice_code: str,
                 auth_url: str, invoice_url: str, payment_check_url: str,
                 callback_url: str):
        self.username = username
        self.password = password
        self.invoice_code = invoice_code
        self.auth_url = auth_url
        self.invoice_url = invoice_url
        self.payment_check_url = payment_check_url
        self.callback_url = callback_url

        # Token кэш
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    # ─────────────────────────────────────────
    #  Token авах (Basic Auth)
    # ─────────────────────────────────────────
    async def _get_auth_header(self) -> str:
        """Basic Auth header үүсгэх"""
        credentials = f"{self.username}:{self.password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    async def get_token(self) -> str:
        """
        Access token авах.
        Хугацаа дуусаагүй бол кэшээс буцаана.
        """
        # Кэш шалгах
        if (self._access_token and self._token_expires_at
                and datetime.utcnow() < self._token_expires_at):
            return self._access_token

        try:
            auth_header = await self._get_auth_header()
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.auth_url,
                    headers={
                        "Authorization": auth_header,
                        "Content-Type": "application/json"
                    }
                )
                response.raise_for_status()
                data = response.json()

                self._access_token = data["access_token"]
                self._refresh_token = data.get("refresh_token")

                # Token хугацаа (expires_in нь timestamp)
                expires_in = data.get("expires_in", 0)
                if expires_in > 1700000000:
                    # Timestamp хэлбэртэй
                    self._token_expires_at = datetime.utcfromtimestamp(expires_in) - timedelta(minutes=5)
                else:
                    # Секунд хэлбэрт
                    self._token_expires_at = datetime.utcnow() + timedelta(seconds=max(expires_in - 300, 60))

                logger.info("✅ QPay token амжилттай авлаа")
                return self._access_token

        except httpx.HTTPStatusError as e:
            logger.error(f"❌ QPay token авахад алдаа: {e.response.status_code} - {e.response.text}")
            raise Exception(f"QPay authentication алдаа: {e.response.status_code}")
        except Exception as e:
            logger.error(f"❌ QPay token авахад алдаа: {str(e)}")
            raise

    # ─────────────────────────────────────────
    #  Token сэргээх (Refresh)
    # ─────────────────────────────────────────
    async def refresh_token(self) -> str:
        """Refresh token ашиглан access token шинэчлэх"""
        if not self._refresh_token:
            return await self.get_token()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.auth_url.replace("/token", "/refresh"),
                    headers={
                        "Authorization": f"Bearer {self._refresh_token}",
                        "Content-Type": "application/json"
                    }
                )
                response.raise_for_status()
                data = response.json()
                self._access_token = data["access_token"]
                self._refresh_token = data.get("refresh_token", self._refresh_token)
                logger.info("✅ QPay token refresh амжилттай")
                return self._access_token

        except Exception:
            # Refresh амжилтгүй бол шинээр авна
            logger.warning("⚠️  Token refresh амжилтгүй, шинээр авч байна...")
            self._access_token = None
            self._token_expires_at = None
            return await self.get_token()

    # ─────────────────────────────────────────
    #  Нэхэмжлэх үүсгэх (Invoice Create Simple)
    # ─────────────────────────────────────────
    async def create_invoice(self, sender_invoice_no: str, amount: int,
                              description: str, receiver_code: str = "terminal") -> dict:
        """
        QPay нэхэмжлэх үүсгэх.
        
        Args:
            sender_invoice_no: Давтагдашгүй нэхэмжлэлийн дугаар
            amount: Төлбөрийн дүн (MNT)
            description: Нэхэмжлэлийн тайлбар
            receiver_code: Хүлээн авагчийн код
            
        Returns:
            dict: {invoice_id, qr_text, qr_image, qPay_shortUrl, qPay_deeplink}
        """
        token = await self.get_token()

        payload = {
            "invoice_code": self.invoice_code,
            "sender_invoice_no": sender_invoice_no,
            "invoice_receiver_code": receiver_code,
            "invoice_description": description,
            "sender_branch_code": "ONLINE",
            "amount": amount,
            "callback_url": f"{self.callback_url}?sender_invoice_no={sender_invoice_no}"
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.invoice_url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    }
                )

                # 401 бол token шинэчлээд дахин оролдох
                if response.status_code == 401:
                    token = await self.refresh_token()
                    response = await client.post(
                        self.invoice_url,
                        json=payload,
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Content-Type": "application/json"
                        }
                    )

                response.raise_for_status()
                data = response.json()

                logger.info(f"✅ QPay нэхэмжлэх үүсгэлээ: {sender_invoice_no}")
                return {
                    "invoice_id": data.get("invoice_id", ""),
                    "qr_text": data.get("qr_text", ""),
                    "qr_image": data.get("qr_image", ""),
                    "qpay_short_url": data.get("qPay_shortUrl", ""),
                    "deeplinks": data.get("urls", data.get("qPay_deeplink", []))
                }

        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Invoice үүсгэхэд алдаа: {e.response.status_code} - {e.response.text}")
            raise Exception(f"QPay invoice алдаа: {e.response.text}")
        except Exception as e:
            logger.error(f"❌ Invoice үүсгэхэд алдаа: {str(e)}")
            raise

    # ─────────────────────────────────────────
    #  Төлбөр шалгах (Payment Check)
    # ─────────────────────────────────────────
    async def check_payment(self, qpay_invoice_id: str) -> dict:
        """
        Төлбөр төлөгдсөн эсэхийг шалгах.
        
        Args:
            qpay_invoice_id: QPay-ээс ирсэн invoice_id
            
        Returns:
            dict: {paid: bool, payment_id: str, rows: list}
        """
        token = await self.get_token()

        payload = {
            "object_type": "INVOICE",
            "object_id": qpay_invoice_id,
            "offset": {
                "page_number": 1,
                "page_limit": 100
            }
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.payment_check_url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    }
                )

                if response.status_code == 401:
                    token = await self.refresh_token()
                    response = await client.post(
                        self.payment_check_url,
                        json=payload,
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Content-Type": "application/json"
                        }
                    )

                response.raise_for_status()
                data = response.json()

                count = data.get("count", 0)
                paid_amount = data.get("paid_amount", 0)
                rows = data.get("rows", [])

                # Төлөгдсөн гүйлгээ шүүх
                paid_rows = [r for r in rows if r.get("payment_status") == "PAID"]

                if paid_rows:
                    payment_id = paid_rows[0].get("payment_id", "")
                    logger.info(f"✅ Төлбөр амжилттай: payment_id={payment_id}")
                    return {
                        "paid": True,
                        "payment_id": str(payment_id),
                        "paid_amount": paid_amount,
                        "count": count,
                        "rows": paid_rows
                    }
                else:
                    return {
                        "paid": False,
                        "payment_id": None,
                        "paid_amount": 0,
                        "count": count,
                        "rows": rows
                    }

        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Төлбөр шалгахад алдаа: {e.response.status_code} - {e.response.text}")
            raise Exception(f"QPay payment check алдаа: {e.response.text}")
        except Exception as e:
            logger.error(f"❌ Төлбөр шалгахад алдаа: {str(e)}")
            raise
