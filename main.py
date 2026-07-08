import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import resend
from dotenv import load_dotenv

# Load environment variables from .env file locally
load_dotenv()

app = FastAPI()

# ✅ SECURITY: Allow your Vue app to talk to this Railway backend
# Replace 'https://your-vue-app.com' with your actual frontend URL or '*' for testing
origins = [
    "http://localhost:5173",  # Vite default port
    "https://momo-mail-production.up.railway.app", 
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure Resend API Key from Environment Variables
resend.api_key = os.environ.get("RESEND_API_KEY")

class EmailRequest(BaseModel):
    name: str
    email: str
    message: str

@app.post("/send-email")
async def send_email(request: EmailRequest):
    try:
        params = {
            "from": "onboarding@resend.dev", # Or your verified domain
            "to": ["webitronsystems@gmail.com"], # Where you want to receive emails
            "subject": f"New Message from {request.name}",
            "html": f"<strong>Name:</strong> {request.name}<br><strong>Email:</strong> {request.email}<br><strong>Message:</strong> {request.message}"
        }

        email = resend.Emails.send(params)
        return {"status": "success", "id": email.id}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def health_check():
    return {"status": "ok", "message": "Email API is running!"}
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
