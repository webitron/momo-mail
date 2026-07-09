import os
import base64
from fastapi import FastAPI, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
import resend
import boto3
from botocore.exceptions import ClientError

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

# ✅ Initialize Railway Bucket (S3-compatible)
s3_client = boto3.client(
    's3',
    endpoint_url=os.environ.get("BUCKET_ENDPOINT"),
    aws_access_key_id=os.environ.get("BUCKET_ACCESS_KEY"),
    aws_secret_access_key=os.environ.get("BUCKET_SECRET_KEY"),
    region_name='auto'
)

BUCKET_NAME = os.environ.get("BUCKET_NAME")
DEFAULT_PDF_KEY = os.environ.get("DEFAULT_PDF_KEY", "Ict_mastery_for_jhs_1-3_bece_success.pdf")  # Path to PDF in bucket

@app.get("/")
async def health_check():
    return {
        "status": "ok", 
        "message": "Email API running",
        "bucket_configured": bool(BUCKET_NAME and s3_client),
        "default_pdf": DEFAULT_PDF_KEY
    }

# ✅ Fetch PDF from Railway Bucket
def get_pdf_from_bucket(file_key):
    try:
        print(f"📦 Fetching '{file_key}' from bucket '{BUCKET_NAME}'...")
        
        response = s3_client.get_object(
            Bucket=BUCKET_NAME,
            Key=file_key
        )
        
        file_content = response['Body'].read()
        content_type = response.get('ContentType', 'application/pdf')
        
        print(f"✅ PDF fetched successfully: {len(file_content)} bytes")
        return file_content, content_type
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchKey':
            print(f"❌ File not found in bucket: {file_key}")
            raise HTTPException(status_code=404, detail=f"File '{file_key}' not found in bucket")
        else:
            print(f"❌ Bucket error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Bucket error: {str(e)}")
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ✅ Send email with default PDF attachment from bucket
@app.post("/send-email")
async def send_email(
    name: str = Form(...),
    email: str = Form(...),
    message: str = Form(...)
):
    print(f"📧 Received email request for: {email}")
    
    if not api_key:
        raise HTTPException(status_code=500, detail="RESEND_API_KEY not configured")
    
    if not BUCKET_NAME:
        raise HTTPException(status_code=500, detail="BUCKET_NAME not configured")
    
    try:
        # ✅ Fetch PDF from Railway Bucket
        pdf_content, content_type = get_pdf_from_bucket(DEFAULT_PDF_KEY)
        
        # ✅ Prepare attachment
        attachments = [{
            "filename": DEFAULT_PDF_KEY.split('/')[-1],  # Extract filename from path
            "content": base64.b64encode(pdf_content).decode("utf-8"),
            "content_type": content_type,
        }]
        
        # ✅ Build email params
        params = {
            "from": "onboarding@resend.dev",
            "to": [email],
            "subject": "Payment Receipt - BookHaven",
            "html": message,
            "attachments": attachments  # Always attach the PDF
        }
        
        print(f"📧 Sending email via Resend to: {email}")
        email_response = resend.Emails.send(params)
        print(f"✅ Email sent successfully: {email_response}")
        
        return {
            "status": "success",
            "id": email_response["id"],
            "attachment": DEFAULT_PDF_KEY
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Email sending error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ✅ Optional: Send email with custom PDF from bucket
@app.post("/send-email-with-pdf")
async def send_email_with_pdf(
    name: str = Form(...),
    email: str = Form(...),
    message: str = Form(...),
    pdf_key: str = Form(...)  # Path to PDF in bucket
):
    print(f"📧 Received email request for: {email} with custom PDF: {pdf_key}")
    
    if not api_key:
        raise HTTPException(status_code=500, detail="RESEND_API_KEY not configured")
    
    try:
        pdf_content, content_type = get_pdf_from_bucket(pdf_key)
        
        attachments = [{
            "filename": pdf_key.split('/')[-1],
            "content": base64.b64encode(pdf_content).decode("utf-8"),
            "content_type": content_type,
        }]
        
        params = {
            "from": "onboarding@resend.dev",
            "to": [email],
            "subject": "Payment Receipt - BookHaven",
            "html": message,
            "attachments": attachments
        }
        
        email_response = resend.Emails.send(params)
        
        return {
            "status": "success",
            "id": email_response["id"],
            "attachment": pdf_key
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
