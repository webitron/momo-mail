import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import resend

app = FastAPI()

# ✅ ROBUST CORS CONFIGURATION
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Alternative dev port
        "https://webitronsystems.com",  # Add your deployed Vue URL
        "https://your-vue-app.netlify.app",  # Or Netlify
        "*",  # Allow all origins (for testing only - remove in production)
    ],
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
    expose_headers=["*"],
)

# ✅ Add CORS headers to ALL responses, including errors
@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response

# ✅ Handle OPTIONS preflight requests explicitly
@app.options("/{rest_of_path:path}")
async def preflight_handler(rest_of_path: str):
    return JSONResponse(
        content={"message": "OK"},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )

# Load Resend API key
api_key = os.environ.get("RESEND_API_KEY")
if api_key:
    resend.api_key = api_key
else:
    print("⚠️ WARNING: RESEND_API_KEY not set!")

class EmailRequest(BaseModel):
    name: str
    email: str
    message: str

@app.get("/")
async def health_check():
    return {"status": "ok", "message": "Email API running"}

@app.post("/send-email")
async def send_email(request: EmailRequest):
    if not api_key:
        raise HTTPException(status_code=500, detail="RESEND_API_KEY not configured")
    
    try:
        email = resend.Emails.send({
            "from": "onboarding@resend.dev",
            "to": ["webitronsystems@gmail.com"],  # ← Change to your email
            "subject": f"New Message from {request.name}",
            "html": f"<strong>Name:</strong> {request.name}<br><strong>Email:</strong> {request.email}<br><strong>Message:</strong> {request.message}"
        })
        return {"status": "success", "id": email["id"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
