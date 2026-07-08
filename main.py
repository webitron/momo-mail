import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import resend

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

resend.api_key = os.environ.get("RESEND_API_KEY")

class EmailRequest(BaseModel):
    name: str
    email: str
    message: str

@app.get("/")
async def health_check():
    port = os.environ.get("PORT", "8000")
    return {
        "status": "ok",
        "message": f"Email API running on port {port}",
        "debug_port": port
    }

@app.post("/send-email")
async def send_email(request: EmailRequest):
    try:
        email = resend.Emails.send({
            "from": "onboarding@resend.dev",
            "to": ["your-email@gmail.com"],
            "subject": f"New Message from {request.name}",
            "html": f"<strong>Name:</strong> {request.name}<br><strong>Email:</strong> {request.email}<br><strong>Message:</strong> {request.message}"
        })
        return {"status": "success", "id": email.id}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

if __name__ == "__main__":
    # ✅ CRITICAL: Read Railway's PORT, default to 8000
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
