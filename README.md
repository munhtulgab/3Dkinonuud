# 🎬 Movie Platform — TMDB + QPay v2

Киноны мэдээллийн сан болон QPay v2 төлбөрийн систем бүхий иж бүрэн вэб платформ.

## 📁 Төслийн бүтэц

```
movie-platform/
├── main.py              # FastAPI үндсэн програм (бүх endpoint)
├── database.py          # MongoDB холболт, CRUD үйлдлүүд
├── qpay_service.py      # QPay v2 API сервис (token, invoice, check)
├── tmdb_service.py      # TMDB API сервис
├── models.py            # Pydantic models, MongoDB schema тодорхойлолт
├── requirements.txt     # Python хамаарлууд
├── .env                 # Тохиргоо (API key, MongoDB URI)
├── templates/
│   ├── index.html       # Нүүр хуудас (кино жагсаалт)
│   └── admin.html       # Админ панел
└── static/
    ├── css/style.css    # Бүх стайл (Dark Cinema UI)
    ├── js/app.js        # Хэрэглэгч талын JS
    ├── js/admin.js      # Админ талын JS
    └── img/no-poster.svg
```

## 🚀 Суулгах

### 1. Хамаарлууд суулгах
```bash
pip install -r requirements.txt
```

### 2. MongoDB ажиллуулах
```bash
# MongoDB суулгасан байх шаардлагатай
mongod --dbpath /data/db
```

### 3. .env файл тохируулах
```env
MONGO_URI=mongodb://localhost:27017
MONGO_DB_NAME=movie_platform
TMDB_API_KEY=<TMDB_API_KEY_ОО_ЭНЭД_ОРУУЛНА>
QPAY_USERNAME=TEST_MERCHANT
QPAY_PASSWORD=123456
QPAY_INVOICE_CODE=TEST_INVOICE
```

### 4. Ажиллуулах
```bash
python main.py
# эсвэл
uvicorn main:app --reload --port 8000
```

Хөтөч дээр: **http://localhost:8000**

## 👤 Анхны хэрэглэгч

Апп анх ажиллахад автоматаар admin хэрэглэгч үүсгэнэ:
- **Нэвтрэх нэр:** `admin`
- **Нууц үг:** `admin123`

## 📋 MongoDB Коллекцууд

### `movies` — Кино
| Талбар          | Төрөл    | Тайлбар                      |
|-----------------|----------|------------------------------|
| tmdb_id         | int      | TMDB дахь ID (unique)        |
| title           | string   | Англи нэр                    |
| overview        | string   | Тайлбар                      |
| poster_path     | string   | Постер зургийн URL           |
| vote_average    | float    | Үнэлгээ (0-10)              |
| price           | int      | Үнэ (MNT)                   |
| download_url    | string   | Татах линк                   |
| is_active       | bool     | Идэвхтэй эсэх               |

### `users` — Хэрэглэгч
| Талбар           | Төрөл    | Тайлбар                      |
|------------------|----------|------------------------------|
| username         | string   | Нэвтрэх нэр (unique)        |
| email            | string   | И-мэйл (unique)             |
| password_hash    | string   | Нууц үг (SHA-256 + salt)    |
| role             | string   | "admin" \| "user"            |
| purchased_movies | [int]    | Авсан кинонуудын tmdb_id     |

### `payments` — Төлбөр
| Талбар             | Төрөл    | Тайлбар                      |
|--------------------|----------|------------------------------|
| user_id            | string   | Хэрэглэгчийн _id            |
| movie_tmdb_id      | int      | Киноны TMDB ID               |
| amount             | int      | Дүн (MNT)                   |
| sender_invoice_no  | string   | Давтагдашгүй дугаар (unique)|
| qpay_invoice_id    | string   | QPay invoice_id              |
| qr_image           | string   | QR зураг (base64)           |
| status             | string   | PENDING \| PAID \| FAILED    |

## 🔗 API Endpoints

### Auth
- `POST /api/auth/register` — Бүртгүүлэх
- `POST /api/auth/login` — Нэвтрэх
- `POST /api/auth/logout` — Гарах
- `GET /api/auth/me` — Одоогийн хэрэглэгч

### Movies (Хэрэглэгч)
- `GET /api/movies` — Бүх кино жагсаалт
- `GET /api/movies/{tmdb_id}` — Дэлгэрэнгүй

### Admin
- `POST /api/admin/movies` — TMDB-ээс кино нэмэх
- `PUT /api/admin/movies/{tmdb_id}` — Шинэчлэх
- `DELETE /api/admin/movies/{tmdb_id}` — Устгах
- `GET /api/admin/tmdb/search?q=` — TMDB хайлт

### Payments (QPay v2)
- `POST /api/payments/create-invoice` — Нэхэмжлэх үүсгэх
- `POST /api/payments/check` — Төлбөр шалгах (polling)
- `GET /api/payments/callback` — QPay callback
- `GET /api/payments/history` — Төлбөрийн түүх

## 🔄 Төлбөрийн урсгал

```
1. Хэрэглэгч "Худалдаж авах" дарна
2. Backend → QPay /v2/invoice (Simple) → invoice_id, qr_image, deeplinks
3. Frontend: QR код + банкны апп-ууд харуулна
4. Frontend: 5 секунд тутам /api/payments/check polling
5. QPay /v2/payment/check → count > 0, rows[].payment_status == "PAID"
6. Backend: payments.status = "PAID", users.purchased_movies += tmdb_id
7. Frontend: "Амжилттай!" → "Татаж авах" линк идэвхжинэ
```
