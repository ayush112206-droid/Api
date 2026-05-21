# 📚 Study IQ Complete REST API

Fully reverse-engineered Study IQ API — built from VIP Study Bot v51 analysis.  
Works on **Render** and **Vercel** out of the box.

---

## 🚀 Quick Deploy

### Deploy on Render (Recommended — Free Tier)
1. Push this folder to GitHub
2. Go to [render.com](https://render.com) → New → Web Service
3. Connect your GitHub repo
4. Set:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Click Deploy ✅

### Deploy on Vercel
```bash
npm i -g vercel
cd studyiq-api
vercel --prod
```

### Run Locally
```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
# Open: http://localhost:8000/docs
```

---

## 📡 All API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/` | ❌ | API info |
| GET | `/health` | ❌ | Health check |
| GET | `/api/batches` | ❌ | All public batches |
| GET | `/api/batches/search?q=SSC` | ❌ | Search batches |
| POST | `/api/login` | ❌ | Login with phone → OTP |
| POST | `/api/verify-otp` | ❌ | OTP verify → Token |
| GET | `/api/my-courses` | ✅ | Your purchased courses |
| GET | `/api/course/{id}` | Optional | Full course content |
| GET | `/api/course/{id}/subjects` | Optional | Subjects list |
| GET | `/api/course/{id}/subject/{name}` | Optional | Subject content |
| GET | `/api/course/{id}/topics` | Optional | Topics list |
| GET | `/api/course/{id}/topic/{tid}` | Optional | Topic content |
| GET | `/api/lesson/{lid}/{cid}` | Optional | Lesson PDFs |
| GET | `/api/extract/{id}` | Optional | Full extract |
| GET | `/api/batch/{id}/info` | Optional | Batch overview |

> ✅ = Required &nbsp; Optional = Works without token (uses static token), better with your token

---

## 🔐 Authentication Flow

```
1. POST /api/login
   Body: {"mobile": "9876543210"}
   → Returns: user_id

2. POST /api/verify-otp
   Body: {"user_id": "123456", "otp": "456789"}
   → Returns: token

3. Use token in all requests:
   Authorization: Bearer YOUR_TOKEN
```

---

## 📦 JSON Response Format

Every endpoint returns this envelope:
```json
{
  "success": true,
  "message": "success",
  "data": { ... }
}
```

On error:
```json
{
  "success": false,
  "message": "Error description",
  "detail": { ... }
}
```

---

## 🎯 Example Usage

### 1. Get All Batches
```bash
GET /api/batches?page=1&limit=20&sort=newest
```
```json
{
  "success": true,
  "data": {
    "total": 250,
    "page": 1,
    "per_page": 20,
    "total_pages": 13,
    "batches": [
      {"id": 99999, "title": "SSC CGL 2025", "price": 999, "mrp": 4999}
    ]
  }
}
```

### 2. Search Batch
```bash
GET /api/batches/search?q=UPSC
```

### 3. Get Course Videos + PDFs (No Login)
```bash
GET /api/course/12345
```
```json
{
  "success": true,
  "data": {
    "course_id": "12345",
    "course_title": "SSC CGL Complete 2024",
    "total_subjects": 6,
    "total_videos": 120,
    "total_pdfs": 40,
    "subjects": ["Maths", "English", "GK", "Reasoning"],
    "videos": [
      {
        "id": 1001,
        "title": "Number System Part 1",
        "subject": "Maths",
        "type": "video",
        "url": "https://vod.studyiq.com/maths-ns-p1.m3u8",
        "duration": 3600,
        "free": false
      }
    ],
    "pdfs": [
      {
        "title": "Maths Notes",
        "subject": "Maths",
        "type": "pdf",
        "url": "https://cdn.studyiq.net/maths-notes.pdf"
      }
    ]
  }
}
```

### 4. Full Extract as TXT
```bash
GET /api/extract/12345?format=txt
```
Output:
```
# Study IQ — SSC CGL 2024
# Course ID: 12345
# Videos: 120 | PDFs: 40 | Total: 160

[Maths] Video | Number System Part 1 : https://vod.studyiq.com/...
[Maths] Video | Number System Part 2 : https://vod.studyiq.com/...
[Maths] PDF | Maths Notes : https://cdn.studyiq.net/...
[English] Video | Reading Comprehension : https://...
```

### 5. Login + Get My Courses
```bash
# Step 1
POST /api/login
{"mobile": "9876543210"}

# Step 2
POST /api/verify-otp
{"user_id": "123456", "otp": "654321"}
→ {"token": "eyJhbGci..."}

# Step 3
GET /api/my-courses
Authorization: Bearer eyJhbGci...
```

---

## 🔍 How Data Extraction Works

```
Public API (no login)
  └── GET /api/batches
        └── batch id → /api/course/{id}
              ├── Tries 4 content endpoints (fallback chain)
              ├── Parses: data / courseContent / lectures
              └── Returns: subjects + videos + PDFs

Login-based extraction
  └── /api/login → OTP → token
        └── /api/my-courses (purchased list)
              └── /api/course/{id}/topics
                    └── /api/course/{id}/topic/{tid}
                          └── /api/lesson/{lid}/{cid} → PDF URLs
```

---

## ⚙️ Content API Fallback Chain

The API automatically tries these endpoints in order:
1. `v2/course/getDetails?courseId=X`
2. `v1/course/getDetails?courseId=X&languageId=`
3. `v1/course/content?courseId=X`
4. `course/lectures?courseId=X`

First one that returns valid data is used.

---

## 📝 Notes
- Static token is built-in for no-login access
- All endpoints have CORS enabled (any frontend can call)
- Retry logic: 3 attempts with backoff
- Swagger UI available at `/docs`
- ReDoc available at `/redoc`
