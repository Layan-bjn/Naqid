import os
import traceback
from urllib.parse import urlparse
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

# Load environment variables
load_dotenv()

from backend.schemas import AuditRequest, AuditReport
from backend.agent import AuditAgent

app = FastAPI(
    title="Naqid API (ناقد)",
    description="وكيل تدقيق ذكي يفحص صفحات الويب ويكتشف أخطاء الواجهة والتصميم",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
DEMO_DIR = os.path.join(BASE_DIR, "demo")
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

agent = AuditAgent()

@app.get("/api/health")
async def health_check():
    has_api_key = bool(os.getenv("GEMINI_API_KEY"))
    return {
        "status": "ok",
        "service": "Naqid (ناقد)",
        "has_gemini_key": has_api_key,
        "model": os.getenv("GEMINI_MODEL_NAME", "gemini-3.5-flash-lite")
    }

@app.post("/api/audit", response_model=AuditReport)
async def perform_audit(request: AuditRequest):
    url = request.url.strip()
    if not url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="يرجى إدخال رابط صالح للفحص (URL فارغ)"
        )

    # Basic URL validation
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="صيغة الرابط غير صحيحة. يجب أن يبدأ بـ http:// أو https://"
        )

    # Explicit console logging of audit mode
    has_api_key = bool(os.getenv("GEMINI_API_KEY"))
    is_demo = request.demo or not has_api_key
    mode_str = "DEMO" if is_demo else "LIVE"
    print(f"\n==========================================", flush=True)
    print(f" >>> RUNNING AUDIT IN [{mode_str}] MODE <<<", flush=True)
    print(f" Target URL: {url}", flush=True)
    print(f" Demo requested: {request.demo} | API Key present: {has_api_key}", flush=True)
    print(f"==========================================\n", flush=True)

    try:
        report = await agent.run_audit(url=url, force_demo=request.demo)
        return report
    except TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail="انتهت مهلة الاتصال أثناء محاولة فتح الصفحة المطلوبة. يرجى التحقق من سرعة واستجابة الموقع."
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"حدث خطأ أثناء إجراء الفحص: {str(e)}"
        )

# Mount screenshots directory
app.mount("/screenshots", StaticFiles(directory=SCREENSHOTS_DIR), name="screenshots")

# Mount demo directory (broken_page.html)
app.mount("/demo", StaticFiles(directory=DEMO_DIR, html=True), name="demo")

# Serve frontend static assets (style.css, app.js, index.html)
@app.get("/")
async def serve_index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
