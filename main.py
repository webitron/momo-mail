import os
import base64
from datetime import datetime
from fastapi import FastAPI, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
import resend
import boto3
from botocore.exceptions import ClientError

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_key = os.environ.get("RESEND_API_KEY")
if api_key:
    resend.api_key = api_key
    print("✅ RESEND_API_KEY loaded")

s3_client = boto3.client(
    's3',
    endpoint_url=os.environ.get("BUCKET_ENDPOINT"),
    aws_access_key_id=os.environ.get("BUCKET_ACCESS_KEY"),
    aws_secret_access_key=os.environ.get("BUCKET_SECRET_KEY"),
    region_name='auto'
)

BUCKET_NAME = os.environ.get("BUCKET_NAME")
DEFAULT_PDF_KEY = os.environ.get("DEFAULT_PDF_KEY", "Ict_mastery_for_jhs_1-3_bece_success.pdf")

# ✅ NEW: Configurable email sender (set these in Railway Variables)
# After verifying your domain, change these to:
# EMAIL_FROM_NAME = "BookHaven"
# EMAIL_FROM_ADDRESS = "noreply@webitronsystems.com"
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "BookHaven")
EMAIL_FROM_ADDRESS = os.environ.get("EMAIL_FROM_ADDRESS", "onboarding@resend.dev")
EMAIL_REPLY_TO = os.environ.get("EMAIL_REPLY_TO", "webitronsystems@gmail.com")

print(f"📧 Email sender: {EMAIL_FROM_NAME} <{EMAIL_FROM_ADDRESS}>")

# ✅ Check if email was already sent for this reference
def is_email_already_sent(reference):
    try:
        flag_key = f"sent_flags/{reference}.txt"
        s3_client.head_object(Bucket=BUCKET_NAME, Key=flag_key)
        return True
    except ClientError as e:
        if e.response['Error']['Code'] in ['404', 'NoSuchKey', 'NotFound']:
            return False
        raise

# ✅ Mark email as sent
def mark_email_as_sent(reference, email):
    try:
        flag_key = f"sent_flags/{reference}.txt"
        flag_content = f"""Reference: {reference}
Email: {email}
Sent At: {datetime.utcnow().isoformat()}
Status: SUCCESS"""
        
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=flag_key,
            Body=flag_content.encode('utf-8'),
            ContentType='text/plain'
        )
        print(f"✅ Marked reference '{reference}' as sent")
    except Exception as e:
        print(f"⚠️ Failed to mark as sent: {str(e)}")

# ✅ Fetch PDF from bucket
def get_pdf_from_bucket(file_key):
    try:
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=file_key)
        return response['Body'].read(), response.get('ContentType', 'application/pdf')
    except ClientError as e:
        raise HTTPException(status_code=404, detail=f"File not found: {file_key}")

@app.get("/")
async def health_check():
    return {
        "status": "ok",
        "message": "Email API running",
        "bucket": BUCKET_NAME,
        "default_pdf": DEFAULT_PDF_KEY,
        "sender": f"{EMAIL_FROM_NAME} <{EMAIL_FROM_ADDRESS}>"
    }

# ✅ UPDATED: Uses configured sender address
@app.post("/send-email")
async def send_email(
    name: str = Form(...),
    email: str = Form(...),
    message: str = Form(...),
    reference: str = Form(None)
):
    print(f"\n{'='*50}")
    print(f"📧 Received email request")
    print(f"   To: {email}")
    print(f"   Reference: {reference or 'NOT PROVIDED'}")
    print(f"   From: {EMAIL_FROM_NAME} <{EMAIL_FROM_ADDRESS}>")
    print(f"{'='*50}\n")
    
    if not api_key:
        raise HTTPException(status_code=500, detail="RESEND_API_KEY not configured")
    
    # ✅ CHECK: Has this reference already been emailed?
    if reference:
        try:
            if is_email_already_sent(reference):
                print(f"⚠️ Email already sent for reference: {reference}")
                return {
                    "status": "already_sent",
                    "message": "Email was already sent for this reference",
                    "reference": reference
                }
        except Exception as e:
            print(f"⚠️ Error checking sent status: {str(e)}")
    
    try:
        pdf_content, content_type = get_pdf_from_bucket(DEFAULT_PDF_KEY)
        print(f"✅ PDF fetched: {len(pdf_content)} bytes")
        
        attachments = [{
            "filename": DEFAULT_PDF_KEY.split('/')[-1],
            "content": base64.b64encode(pdf_content).decode("utf-8"),
            "content_type": content_type,
        }]
        
        # ✅ FIXED: Use configured sender with friendly name
        params = {
            "from": f"{EMAIL_FROM_NAME} <{EMAIL_FROM_ADDRESS}>",
            "reply_to": EMAIL_REPLY_TO,
            "to": [email],
            "subject": f"🎉 Payment Receipt - BookHaven",
            "html": message,
            "attachments": attachments
        }
        
        print(f"📧 Sending via Resend to: {email}")
        email_response = resend.Emails.send(params)
        print(f"✅ Email sent: {email_response}")
        
        # ✅ MARK: Record that this reference was emailed
        if reference:
            mark_email_as_sent(reference, email)
        
        return {
            "status": "success",
            "id": email_response["id"],
            "reference": reference
        }
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Email sending error: {error_msg}")
        
        # ✅ Helpful error message for domain verification issue
        if "verify a domain" in error_msg.lower():
            raise HTTPException(
                status_code=500,
                detail="Domain not verified. Please verify your domain at resend.com/domains and set EMAIL_FROM_ADDRESS environment variable."
            )
        
        raise HTTPException(status_code=500, detail=error_msg)

@app.get("/check-sent/{reference}")
async def check_sent(reference: str):
    try:
        already_sent = is_email_already_sent(reference)
        return {
            "reference": reference,
            "already_sent": already_sent
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
