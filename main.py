"""
╔══════════════════════════════════════════════════════════════════╗
║          STUDY IQ — COMPLETE REST API                           ║
║          FastAPI | Render + Vercel Compatible                   ║
║          Author : Built from VIP Study Bot v51 analysis        ║
╚══════════════════════════════════════════════════════════════════╝

ENDPOINTS:
  GET  /                           → Welcome / API Info
  GET  /health                     → Health check
  GET  /api/batches                → All public batches (no login)
  GET  /api/batches/search         → Search batches by name/id
  POST /api/login                  → Login with phone → sends OTP
  POST /api/verify-otp             → Verify OTP → returns token
  GET  /api/my-courses             → Purchased courses (token required)
  GET  /api/course/{id}            → Full course content (videos+PDFs)
  GET  /api/course/{id}/subjects   → Subjects list of a course
  GET  /api/course/{id}/subject/{subject} → Videos+PDFs of one subject
  GET  /api/course/{id}/topics     → Topics list (login-based courses)
  GET  /api/course/{id}/topic/{tid}      → Topic content
  GET  /api/lesson/{lid}/{cid}     → Lesson data (PDFs via options)
  GET  /api/extract/{id}           → Full extract as line list (TXT style)
"""

import os, time, json, re, logging
from typing import Optional, List, Dict, Any

import requests
import httpx
from fastapi import FastAPI, Query, Header, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ─────────────────────────────────────────────────────────────────
#  LOGGING
# ─────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("studyiq-api")

# ─────────────────────────────────────────────────────────────────
#  STUDY IQ CONSTANTS  (extracted from VIP Study Bot v51)
# ─────────────────────────────────────────────────────────────────

# ── Authentication Endpoints ──
IQ_LOGIN_URL   = "https://www.studyiq.net/api/web/userlogin"
IQ_OTP_URL     = "https://www.studyiq.net/api/web/web_user_login"

# ── Course / Content Endpoints ──
IQ_COURSES_URL   = "https://backend.studyiq.net/app-content-ws/api/v1/getAllPurchasedCourses?source=WEB"
IQ_DETAILS_URL   = "https://backend.studyiq.net/app-content-ws/v1/course/getDetails?courseId={cid}&languageId={lid}"
IQ_DETAILS_P     = "https://backend.studyiq.net/app-content-ws/v1/course/getDetails?courseId={cid}&languageId=&parentId={pid}"
IQ_LESSON_URL    = "https://backend.studyiq.net/app-content-ws/api/lesson/data?lesson_id={lid}&courseId={cid}"

# ── Public Batch List (no login) ──
IQ_PUBLIC_BATCHES_URL = "https://raj-iq-api.onrender.com/api/batches"

# ── Static Token (for content without user login) ──
IQ_STATIC_TOKEN = (
    "eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiIyMjcyNzQwIiwicm9sZSI6IlVTRVIiLCJJcC1BZGRyZXNzIjoiMTI3LjAuMC4xIiwiVXNlci1BZ2VudCI"
    "6IkFtYXpvbiBDbG91ZEZyb250IiwiaWF0IjoxNzc0OTQ0NzI0LCJ1c2VySWQiOiJzdHVkeS52MS5mYmNkMzIzNjBjZTM2MjEwYzJhZTYzYjljNWIz"
    "MjJmZCIsInBsYXRmb3JtIjoiV0VCIiwiaXNzdWVyIjoiYWRkYTI0Ny5jb20iLCJleHAiOjE4MDY0ODA3MjR9"
    ".g-GUM5uspfDywwP7S3zy2zlU6SvH20akdbyPZNtdE5mOStWcmpYNdV5ZJhHVufiFQP1Wn1FgIyHcr72iERDTog"
)

# ── Multiple Content Endpoints (fallback chain) ──
IQ_CONTENT_ENDPOINTS = [
    "https://backend.studyiq.net/app-content-ws/v2/course/getDetails?courseId={cid}",
    "https://backend.studyiq.net/app-content-ws/v1/course/getDetails?courseId={cid}&languageId=",
    "https://backend.studyiq.net/app-content-ws/v1/course/content?courseId={cid}",
    "https://backend.studyiq.net/app-content-ws/course/lectures?courseId={cid}",
]

# ─────────────────────────────────────────────────────────────────
#  HTTP SESSION  (reuse connections for speed)
# ─────────────────────────────────────────────────────────────────
_session = requests.Session()
_session.headers.update({
    "User-Agent":  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept":      "application/json, text/plain, */*",
    "Platform":    "WEB",
    "Referer":     "https://www.studyiq.com/",
    "Origin":      "https://www.studyiq.com",
    "Connection":  "keep-alive",
})
_adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=2)
_session.mount("https://", _adapter)
_session.mount("http://",  _adapter)

# ─────────────────────────────────────────────────────────────────
#  FASTAPI APP
# ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title        = "Study IQ API",
    description  = "Complete Study IQ REST API — All courses, subjects, videos, PDFs, login",
    version      = "2.0.0",
    docs_url     = "/docs",
    redoc_url    = "/redoc",
)

# Allow all origins (for web frontends, Postman, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# ─────────────────────────────────────────────────────────────────
#  PYDANTIC MODELS  (request bodies)
# ─────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    mobile: str                    # phone number (10 digits)

class OTPRequest(BaseModel):
    user_id: str                   # user_id from login response
    otp:     str                   # 6-digit OTP

# ─────────────────────────────────────────────────────────────────
#  INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────

def _get_headers(token: Optional[str] = None) -> dict:
    """Build Study IQ API headers. Uses static token if none provided."""
    tok = token or IQ_STATIC_TOKEN
    return {
        "Accept":        "application/json, text/plain, */*",
        "Platform":      "WEB",
        "Authorization": tok,
        "User-Agent":    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer":       "https://www.studyiq.com/",
        "Origin":        "https://www.studyiq.com",
    }


def _fetch(url: str, token: Optional[str] = None, retries: int = 3) -> Optional[dict]:
    """GET request with retry logic. Returns parsed JSON or None."""
    hdrs = _get_headers(token)
    for attempt in range(retries):
        try:
            r = _session.get(url, headers=hdrs, timeout=30)
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 429:
                time.sleep(2 ** attempt)
            elif r.status_code in (401, 403):
                logger.warning(f"Auth error {r.status_code} for {url}")
                return None
            else:
                logger.warning(f"HTTP {r.status_code} for {url}")
        except requests.Timeout:
            logger.warning(f"Timeout attempt {attempt+1} for {url}")
        except Exception as e:
            logger.error(f"Fetch error: {e}")
        if attempt < retries - 1:
            time.sleep(0.5 * (attempt + 1))
    return None


def _post(url: str, data: dict, retries: int = 3) -> Optional[dict]:
    """POST JSON request with retry. Returns parsed JSON or None."""
    for attempt in range(retries):
        try:
            r = _session.post(url, json=data, timeout=25)
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 400:
                # 400 = wrong data — no point retrying
                try:
                    return r.json()
                except:
                    return {"error": "Bad request", "status": 400}
        except Exception as e:
            logger.error(f"Post error: {e}")
        if attempt < retries - 1:
            time.sleep(0.5)
    return None


def _fetch_course_content(course_id: str, token: Optional[str] = None):
    """
    Try multiple endpoints to get course content.
    Returns (items_list, course_title) or (None, None).
    Mirrors iq_fetch_course_content() in the bot.
    """
    for tpl in IQ_CONTENT_ENDPOINTS:
        url = tpl.format(cid=course_id)
        data = _fetch(url, token)
        if not data:
            continue
        # Try different JSON structures
        items = (
            data.get("data")
            or data.get("courseContent")
            or data.get("lectures")
        )
        if items and isinstance(items, list) and len(items) > 0:
            title = data.get("courseTitle") or data.get("title") or ""
            return items, title
    return None, None


def _parse_content(items: list, subject_filter: Optional[str] = None):
    """
    Parse raw content items into subjects / videos / pdfs.
    Mirrors iq_parse_content() in the bot.
    Returns: (subjects, videos, pdfs)
    """
    if not items:
        return [], [], []
    if subject_filter:
        items = [i for i in items if (i.get("parentTitle") or "General") == subject_filter]

    subjects = list(dict.fromkeys(
        i.get("parentTitle") or "General" for i in items
    ))
    videos = [i for i in items if i.get("videoUrl") or i.get("video_url")]
    pdfs   = [i for i in items if i.get("textUploadUrl") or i.get("pdfUrl")]
    return subjects, videos, pdfs


def _format_video(item: dict) -> dict:
    """Format a video item into clean dict."""
    return {
        "id":       item.get("id") or item.get("contentId") or item.get("lessonId"),
        "title":    item.get("name") or item.get("title") or "Untitled",
        "subject":  item.get("parentTitle") or "General",
        "type":     "video",
        "url":      item.get("videoUrl") or item.get("video_url") or "",
        "duration": item.get("duration") or item.get("videoDuration") or None,
        "free":     item.get("isFree", False),
        "raw":      item,        # full raw item for advanced use
    }


def _format_pdf(item: dict) -> dict:
    """Format a PDF item into clean dict."""
    return {
        "id":      item.get("id") or item.get("contentId"),
        "title":   item.get("name") or item.get("title") or "Untitled",
        "subject": item.get("parentTitle") or "General",
        "type":    "pdf",
        "url":     item.get("textUploadUrl") or item.get("pdfUrl") or "",
        "raw":     item,
    }


def _ok(data: Any, message: str = "success", extra: dict = None) -> dict:
    """Standard success response envelope."""
    resp = {"success": True, "message": message, "data": data}
    if extra:
        resp.update(extra)
    return resp


def _err(message: str, status: int = 400, detail: Any = None) -> JSONResponse:
    """Standard error response."""
    body = {"success": False, "message": message}
    if detail is not None:
        body["detail"] = detail
    return JSONResponse(content=body, status_code=status)


# ─────────────────────────────────────────────────────────────────
#  ROUTES
# ─────────────────────────────────────────────────────────────────

# ══ Root / Info ══════════════════════════════════════════════════

@app.get("/", tags=["Info"])
def root():
    """API welcome page with all endpoint descriptions."""
    return {
        "api":     "Study IQ REST API",
        "version": "2.0.0",
        "status":  "running",
        "docs":    "/docs",
        "endpoints": {
            "GET  /health":                         "Health check",
            "GET  /api/batches":                    "All public batches (no login needed)",
            "GET  /api/batches/search?q=QUERY":     "Search batches by name or ID",
            "POST /api/login":                      "Login with mobile number → sends OTP",
            "POST /api/verify-otp":                 "Verify OTP → returns API token",
            "GET  /api/my-courses":                 "Your purchased courses (Bearer token required)",
            "GET  /api/course/{id}":                "Full course content (videos + PDFs)",
            "GET  /api/course/{id}/subjects":       "List of subjects in a course",
            "GET  /api/course/{id}/subject/{name}": "Videos + PDFs of one subject",
            "GET  /api/course/{id}/topics":         "Topics of a course (for login-based courses)",
            "GET  /api/course/{id}/topic/{tid}":    "Content of one topic",
            "GET  /api/lesson/{lid}/{cid}":         "Raw lesson data (PDFs from options)",
            "GET  /api/extract/{id}":               "Full extract: all content as line list",
        },
        "auth_note": (
            "Most endpoints work WITHOUT login using a static token. "
            "For premium/purchased courses, pass token as: "
            "Authorization: Bearer YOUR_TOKEN"
        ),
    }


@app.get("/health", tags=["Info"])
def health():
    """Health check endpoint."""
    return {"status": "ok", "timestamp": int(time.time())}


# ══ Public Batches ═══════════════════════════════════════════════

@app.get("/api/batches", tags=["Batches"])
def get_all_batches(
    page:  int = Query(1,  ge=1,  description="Page number (1-based)"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    sort:  str = Query("newest", description="Sort: newest | oldest | id"),
):
    """
    Get ALL Study IQ public batches.
    No login required.
    Returns paginated list with id, title, price, mrp, validity.

    JSON Response:
    {
      "success": true,
      "data": {
        "total": 250,
        "page": 1,
        "per_page": 20,
        "total_pages": 13,
        "batches": [
          {
            "id": 12345,
            "title": "SSC CGL 2024 Complete Batch",
            "price": 999,
            "mrp": 2999,
            "validity": "12 months"
          }, ...
        ]
      }
    }
    """
    raw = _fetch(IQ_PUBLIC_BATCHES_URL)
    if not raw or not raw.get("success"):
        return _err("Study IQ public batch API unavailable. Try again later.", 503)

    batches: List[dict] = raw.get("data", [])
    if not batches:
        return _err("No batches found.", 404)

    # Sort
    if sort == "oldest":
        batches = sorted(batches, key=lambda x: x.get("id", 0))
    elif sort in ("newest", "id"):
        batches = sorted(batches, key=lambda x: x.get("id", 0), reverse=True)

    total = len(batches)
    total_pages = max(1, (total + limit - 1) // limit)
    page = min(page, total_pages)
    start = (page - 1) * limit
    page_items = batches[start: start + limit]

    return _ok({
        "total":       total,
        "page":        page,
        "per_page":    limit,
        "total_pages": total_pages,
        "batches":     page_items,
    })


@app.get("/api/batches/search", tags=["Batches"])
def search_batches(
    q:     str = Query(..., min_length=1, description="Search query (name or ID)"),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Search Study IQ batches by name or batch ID.

    JSON Response:
    {
      "success": true,
      "data": {
        "query": "SSC",
        "total": 5,
        "batches": [...]
      }
    }
    """
    raw = _fetch(IQ_PUBLIC_BATCHES_URL)
    if not raw or not raw.get("success"):
        return _err("Batch API unavailable.", 503)

    batches: List[dict] = raw.get("data", [])
    q_lower = q.lower().strip()
    results = [
        b for b in batches
        if q_lower in b.get("title", "").lower() or q_lower in str(b.get("id", ""))
    ]
    return _ok({
        "query":   q,
        "total":   len(results),
        "batches": results[:limit],
    })


# ══ Authentication ════════════════════════════════════════════════

@app.post("/api/login", tags=["Auth"])
def login(body: LoginRequest):
    """
    Step 1: Login with mobile number.
    Study IQ sends OTP to your registered mobile.

    Request Body:
    { "mobile": "9876543210" }

    Response:
    {
      "success": true,
      "message": "OTP sent",
      "data": {
        "user_id": "123456",
        "msg": "OTP sent to your number"
      }
    }

    ➡ Use user_id in /api/verify-otp
    """
    mobile = body.mobile.strip()
    if not mobile.isdigit() or len(mobile) < 10:
        return _err("Invalid mobile number. Must be 10+ digits.")

    resp = _post(IQ_LOGIN_URL, {"mobile": mobile})
    if not resp:
        return _err("Study IQ login API unavailable. Try again.", 503)

    # Check for errors in response
    if resp.get("status") == 0 or resp.get("error"):
        return _err(
            resp.get("msg") or resp.get("message") or "Login failed",
            400,
            detail=resp,
        )

    data = resp.get("data", {})
    user_id = data.get("user_id") if isinstance(data, dict) else None
    if not user_id:
        return _err("Could not get user_id from response.", 500, detail=resp)

    return _ok(
        {"user_id": str(user_id), "msg": resp.get("msg", "OTP sent")},
        message="OTP sent successfully"
    )


@app.post("/api/verify-otp", tags=["Auth"])
def verify_otp(body: OTPRequest):
    """
    Step 2: Verify OTP and get API token.

    Request Body:
    { "user_id": "123456", "otp": "123456" }

    Response:
    {
      "success": true,
      "message": "Login successful",
      "data": {
        "token": "eyJhbGciOiJIUzUxMiJ9...",
        "user_name": "John Doe",
        "email": "john@example.com",
        "mobile": "9876543210"
      }
    }

    ➡ Use token as: Authorization: Bearer TOKEN
    """
    resp = _post(IQ_OTP_URL, {"user_id": body.user_id, "otp": body.otp})
    if not resp:
        return _err("OTP verification API unavailable.", 503)

    if resp.get("status") == 0 or resp.get("error"):
        return _err(
            resp.get("msg") or resp.get("message") or "OTP verification failed",
            400,
            detail=resp,
        )

    data = resp.get("data", {})
    token = data.get("api_token") if isinstance(data, dict) else None
    if not token:
        return _err("Could not extract token from response.", 500, detail=resp)

    return _ok({
        "token":     token,
        "user_name": data.get("user_name") or data.get("name") or "",
        "email":     data.get("email") or "",
        "mobile":    data.get("mobile") or "",
        "user_id":   data.get("user_id") or body.user_id,
        "raw":       data,
    }, message="Login successful")


# ══ User Courses (Login Required) ════════════════════════════════

@app.get("/api/my-courses", tags=["Courses"])
def get_my_courses(
    authorization: Optional[str] = Header(None, description="Bearer YOUR_TOKEN")
):
    """
    Get purchased courses for logged-in user.
    Requires: Authorization: Bearer YOUR_TOKEN

    Response:
    {
      "success": true,
      "data": {
        "total": 3,
        "courses": [
          {
            "courseId": 12345,
            "courseTitle": "SSC CGL 2024",
            "languageId": 1,
            "thumbnail": "https://..."
          }, ...
        ]
      }
    }
    """
    token = _extract_token(authorization)
    if not token:
        return _err("Authorization token required. Pass as: Authorization: Bearer YOUR_TOKEN", 401)

    resp = _fetch(IQ_COURSES_URL, token)
    if not resp:
        return _err("Could not fetch courses. Check token validity.", 503)

    if not resp.get("data"):
        return _err("No purchased courses found or invalid token.", 404, detail=resp)

    courses = resp["data"]
    return _ok({
        "total":   len(courses),
        "courses": courses,
    })


# ══ Course Content ════════════════════════════════════════════════

@app.get("/api/course/{course_id}", tags=["Course Content"])
def get_course_content(
    course_id:     str,
    authorization: Optional[str] = Header(None),
    subject:       Optional[str] = Query(None, description="Filter by subject name"),
):
    """
    Get FULL course content — all videos and PDFs.
    Works WITHOUT login using static token.
    Optionally pass your token for better access.

    Response:
    {
      "success": true,
      "data": {
        "course_id": "12345",
        "course_title": "SSC CGL 2024",
        "total_subjects": 5,
        "total_videos": 120,
        "total_pdfs": 45,
        "subjects": ["Maths", "English", "GK", ...],
        "videos": [
          {
            "id": 1001,
            "title": "Number System - Part 1",
            "subject": "Maths",
            "type": "video",
            "url": "https://vod.studyiq.com/...",
            "duration": 3600,
            "free": false
          }, ...
        ],
        "pdfs": [
          {
            "id": 2001,
            "title": "Maths Notes PDF",
            "subject": "Maths",
            "type": "pdf",
            "url": "https://cdn.studyiq.net/..."
          }, ...
        ]
      }
    }
    """
    token = _extract_token(authorization)
    items, course_title = _fetch_course_content(course_id, token)

    if not items:
        return _err(
            f"No content found for course {course_id}. "
            "Token may be expired or course not available.",
            404,
        )

    subjects, videos, pdfs = _parse_content(items, subject_filter=subject)

    return _ok({
        "course_id":       course_id,
        "course_title":    course_title or course_id,
        "total_subjects":  len(subjects),
        "total_videos":    len(videos),
        "total_pdfs":      len(pdfs),
        "subjects":        subjects,
        "videos":          [_format_video(v) for v in videos],
        "pdfs":            [_format_pdf(p)   for p in pdfs],
    })


@app.get("/api/course/{course_id}/subjects", tags=["Course Content"])
def get_subjects(
    course_id:     str,
    authorization: Optional[str] = Header(None),
):
    """
    Get list of subjects/chapters in a course.

    Response:
    {
      "success": true,
      "data": {
        "course_id": "12345",
        "course_title": "SSC CGL 2024",
        "total": 8,
        "subjects": ["Maths", "English", "Reasoning", ...]
      }
    }
    """
    token = _extract_token(authorization)
    items, course_title = _fetch_course_content(course_id, token)

    if not items:
        return _err(f"No content found for course {course_id}.", 404)

    subjects, _, _ = _parse_content(items)
    return _ok({
        "course_id":    course_id,
        "course_title": course_title or course_id,
        "total":        len(subjects),
        "subjects":     subjects,
    })


@app.get("/api/course/{course_id}/subject/{subject_name}", tags=["Course Content"])
def get_subject_content(
    course_id:    str,
    subject_name: str,
    authorization: Optional[str] = Header(None),
):
    """
    Get all videos and PDFs for a specific subject.

    Response:
    {
      "success": true,
      "data": {
        "course_id": "12345",
        "subject": "Maths",
        "total_videos": 30,
        "total_pdfs": 10,
        "videos": [...],
        "pdfs": [...]
      }
    }
    """
    token = _extract_token(authorization)
    items, course_title = _fetch_course_content(course_id, token)

    if not items:
        return _err(f"No content found for course {course_id}.", 404)

    _, videos, pdfs = _parse_content(items, subject_filter=subject_name)
    if not videos and not pdfs:
        return _err(f"No content found for subject '{subject_name}' in course {course_id}.", 404)

    return _ok({
        "course_id":    course_id,
        "course_title": course_title or course_id,
        "subject":      subject_name,
        "total_videos": len(videos),
        "total_pdfs":   len(pdfs),
        "videos":       [_format_video(v) for v in videos],
        "pdfs":         [_format_pdf(p)   for p in pdfs],
    })


# ══ Topic-Based (Login Courses) ═══════════════════════════════════

@app.get("/api/course/{course_id}/topics", tags=["Topics (Login Courses)"])
def get_topics(
    course_id:     str,
    language_id:   str = Query("", description="Language ID (optional, leave blank for all)"),
    authorization: Optional[str] = Header(None),
):
    """
    Get topics list for a course.
    Best for PURCHASED/LOGIN courses.
    Returns list of topic names + contentIds for drilling down.

    Response:
    {
      "success": true,
      "data": {
        "course_id": "12345",
        "course_title": "SSC CGL 2024",
        "total_topics": 15,
        "topics": [
          {
            "contentId": 9001,
            "name": "Maths - Algebra",
            "order": 1
          }, ...
        ]
      }
    }
    """
    token = _extract_token(authorization)
    url   = IQ_DETAILS_URL.format(cid=course_id, lid=language_id)
    resp  = _fetch(url, token)

    if not resp or not resp.get("data"):
        return _err(f"Topics not found for course {course_id}.", 404, detail=resp)

    course_title = resp.get("courseTitle", "")
    topics: List[dict] = resp["data"]

    return _ok({
        "course_id":    course_id,
        "course_title": course_title,
        "total_topics": len(topics),
        "topics": [
            {
                "contentId": t.get("contentId"),
                "name":      t.get("name", "Unknown"),
                "order":     t.get("orderNo") or t.get("order") or i + 1,
                "type":      t.get("type") or t.get("contentType") or "",
            }
            for i, t in enumerate(topics)
        ],
    })


@app.get("/api/course/{course_id}/topic/{topic_id}", tags=["Topics (Login Courses)"])
def get_topic_content(
    course_id:     str,
    topic_id:      str,
    authorization: Optional[str] = Header(None),
):
    """
    Get detailed content (videos + PDFs) for a specific topic.

    Response:
    {
      "success": true,
      "data": {
        "course_id": "12345",
        "topic_id": "9001",
        "total_items": 25,
        "has_sub_folders": false,
        "videos": [...],
        "pdfs": [...],
        "sub_folders": []
      }
    }
    """
    token = _extract_token(authorization)
    url   = IQ_DETAILS_P.format(cid=course_id, pid=topic_id)
    resp  = _fetch(url, token)

    if not resp or not resp.get("data"):
        return _err(f"Topic {topic_id} not found in course {course_id}.", 404, detail=resp)

    raw_items: List[dict] = resp["data"]
    has_sub = any(x.get("subFolderOrderId") is not None for x in raw_items)

    videos = []
    pdfs   = []
    sub_folders = []

    if not has_sub:
        for item in raw_items:
            url_v = item.get("videoUrl")
            if url_v:
                videos.append({
                    "contentId": item.get("contentId"),
                    "name":      item.get("name", "Untitled"),
                    "url":       url_v,
                    "duration":  item.get("duration"),
                    "free":      item.get("isFree", False),
                })
            # Try fetching lesson PDFs
            cid_ = item.get("contentId")
            if cid_:
                lesson_data = _fetch(IQ_LESSON_URL.format(lid=cid_, cid=course_id), token)
                if lesson_data and lesson_data.get("options"):
                    for opt in lesson_data["options"]:
                        for ud in (opt.get("urls") or []):
                            if ud.get("name") and ud.get("url"):
                                pdfs.append({
                                    "contentId": cid_,
                                    "name":      ud["name"],
                                    "url":       ud["url"],
                                })
    else:
        for sub in raw_items:
            sub_folders.append({
                "contentId": sub.get("contentId"),
                "name":      sub.get("name", "Sub-folder"),
                "order":     sub.get("orderNo") or sub.get("subFolderOrderId"),
            })

    return _ok({
        "course_id":      course_id,
        "topic_id":       topic_id,
        "total_items":    len(videos) + len(pdfs),
        "has_sub_folders": has_sub,
        "videos":         videos,
        "pdfs":           pdfs,
        "sub_folders":    sub_folders,
    })


# ══ Lesson Data ═══════════════════════════════════════════════════

@app.get("/api/lesson/{lesson_id}/{course_id}", tags=["Lesson"])
def get_lesson(
    lesson_id:     str,
    course_id:     str,
    authorization: Optional[str] = Header(None),
):
    """
    Get raw lesson data — including embedded PDF links from 'options'.

    Response:
    {
      "success": true,
      "data": {
        "lesson_id": "555",
        "course_id": "12345",
        "pdfs": [
          {"name": "Chapter Notes", "url": "https://..."}
        ],
        "raw": {...}   // full API response
      }
    }
    """
    token = _extract_token(authorization)
    url   = IQ_LESSON_URL.format(lid=lesson_id, cid=course_id)
    resp  = _fetch(url, token)

    if not resp:
        return _err(f"Lesson {lesson_id} not found.", 404)

    pdfs = []
    if resp.get("options"):
        for opt in resp["options"]:
            for ud in (opt.get("urls") or []):
                if ud.get("name") and ud.get("url"):
                    pdfs.append({"name": ud["name"], "url": ud["url"]})

    return _ok({
        "lesson_id": lesson_id,
        "course_id": course_id,
        "total_pdfs": len(pdfs),
        "pdfs":      pdfs,
        "raw":       resp,
    })


# ══ Full Extract ═══════════════════════════════════════════════════

@app.get("/api/extract/{course_id}", tags=["Extract"])
def full_extract(
    course_id:     str,
    authorization: Optional[str] = Header(None),
    format:        str = Query("json", description="Output format: json | txt"),
):
    """
    FULL EXTRACTION — All videos + PDFs of a course as flat list.

    format=json → Structured JSON with stats
    format=txt  → Plain text (one line per item, like:
                  [Subject] Video | Title : URL
                  [Subject] PDF   | Title : URL)

    JSON Response:
    {
      "success": true,
      "data": {
        "course_id": "12345",
        "course_title": "SSC CGL 2024",
        "stats": {
          "total_videos": 120,
          "total_pdfs": 45,
          "total_items": 165
        },
        "items": [
          {
            "subject": "Maths",
            "type": "video",
            "title": "Number System Part 1",
            "url": "https://vod.studyiq.com/..."
          },
          {
            "subject": "Maths",
            "type": "pdf",
            "title": "Maths Notes",
            "url": "https://cdn.studyiq.net/..."
          }, ...
        ]
      }
    }
    """
    token = _extract_token(authorization)
    items, course_title = _fetch_course_content(course_id, token)

    if not items:
        return _err(f"No content found for course {course_id}.", 404)

    subjects, videos, pdfs = _parse_content(items)

    all_items = []
    lines     = []
    tv = tp   = 0

    for v in videos:
        title   = v.get("name") or v.get("title", "Untitled")
        subject = v.get("parentTitle") or "General"
        url     = v.get("videoUrl") or v.get("video_url", "")
        if url:
            all_items.append({"subject": subject, "type": "video", "title": title, "url": url})
            lines.append(f"[{subject}] Video | {title} : {url}")
            tv += 1

    for p in pdfs:
        title   = p.get("name") or p.get("title", "Untitled")
        subject = p.get("parentTitle") or "General"
        url     = p.get("textUploadUrl") or p.get("pdfUrl", "")
        if url:
            all_items.append({"subject": subject, "type": "pdf", "title": title, "url": url})
            lines.append(f"[{subject}] PDF | {title} : {url}")
            tp += 1

    if format.lower() == "txt":
        header = f"# Study IQ — {course_title or course_id}\n"
        header += f"# Course ID: {course_id}\n"
        header += f"# Videos: {tv} | PDFs: {tp} | Total: {tv+tp}\n"
        header += f"# Extracted: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        return PlainTextResponse(header + "\n".join(lines))

    return _ok({
        "course_id":    course_id,
        "course_title": course_title or course_id,
        "stats": {
            "total_videos": tv,
            "total_pdfs":   tp,
            "total_items":  tv + tp,
        },
        "subjects": subjects,
        "items":    all_items,
    })


# ══ Batch + Course Combined ════════════════════════════════════════

@app.get("/api/batch/{batch_id}/info", tags=["Batches"])
def batch_info(
    batch_id:      str,
    authorization: Optional[str] = Header(None),
):
    """
    Get batch/course info: title + content overview + subject list.
    One-stop endpoint for batch details without full extraction.
    """
    token = _extract_token(authorization)

    # First try to get basic info from public batch list
    batch_meta = {}
    raw = _fetch(IQ_PUBLIC_BATCHES_URL)
    if raw and raw.get("data"):
        batch_meta = next(
            (b for b in raw["data"] if str(b.get("id","")) == str(batch_id)),
            {}
        )

    # Then get content info
    items, course_title = _fetch_course_content(batch_id, token)
    subjects, videos, pdfs = _parse_content(items) if items else ([], [], [])

    return _ok({
        "batch_id":       batch_id,
        "title":          course_title or batch_meta.get("title", "Unknown"),
        "price":          batch_meta.get("price"),
        "mrp":            batch_meta.get("mrp"),
        "validity":       batch_meta.get("validity"),
        "total_subjects": len(subjects),
        "total_videos":   len(videos),
        "total_pdfs":     len(pdfs),
        "subjects":       subjects,
        "meta":           batch_meta,
    })


# ─────────────────────────────────────────────────────────────────
#  UTILITY
# ─────────────────────────────────────────────────────────────────

def _extract_token(authorization: Optional[str]) -> Optional[str]:
    """Extract Bearer token from Authorization header."""
    if not authorization:
        return None
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return authorization.strip()


# ─────────────────────────────────────────────────────────────────
#  GLOBAL EXCEPTION HANDLER
# ─────────────────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"success": False, "message": f"Internal server error: {str(exc)}"},
    )


# ─────────────────────────────────────────────────────────────────
#  ENTRYPOINT  (for local dev / Render)
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False, log_level="info")
