import os
import base64
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import resend

app = FastAPI()

# ✅ CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load Resend API key
api_key = os.environ.get("RESEND_API_KEY")
if api_key:
    resend.api_key = api_key
    print("✅ RESEND_API_KEY loaded successfully")
else:
    print("⚠️ WARNING: RESEND_API_KEY not set!")

@app.get("/")
async def health_check():
    return {"status": "ok", "message": "Email API running"}

# ✅ FIXED: Use Form() parameters correctly
@app.post("/send-email")
async def send_email(
    name: str = Form(...),
    email: str = Form(...),
    message: str = Form(...),
    attachment: UploadFile = File(None)
):
    print(f"📧 Received email request for: {email}")
    
    if not api_key:
        raise HTTPException(status_code=500, detail="RESEND_API_KEY not configured")
    
    try:
        attachments = []
        if attachment and attachment.filename:
            content = await attachment.read()
            attachments.append({
                "filename": attachment.filename,
                "content": base64.b64encode(content).decode("utf-8"),
                "content_type": attachment.content_type or "application/octet-stream",
            })
        
        params = {
            "from": "onboarding@resend.dev",
            "to": [email],
            "subject": "Payment Receipt - BookHaven",
            "html": message,
        }
        
        if attachments:
            params["attachments"] = attachments
        
        print(f"📧 Sending email via Resend to: {email}")
        email_response = resend.Emails.send(params)
        print(f"✅ Email sent successfully: {email_response}")
        
        return {
            "status": "success",
            "id": email_response["id"],
        }
        
    except Exception as e:
        print(f"❌ Email sending error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
