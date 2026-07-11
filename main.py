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

s3_client = boto3.client(
    's3',
    endpoint_url=os.environ.get("BUCKET_ENDPOINT"),
    aws_access_key_id=os.environ.get("BUCKET_ACCESS_KEY"),
    aws_secret_access_key=os.environ.get("BUCKET_SECRET_KEY"),
    region_name='auto'
)

BUCKET_NAME = os.environ.get("BUCKET_NAME")
DEFAULT_PDF_KEY = os.environ.get("DEFAULT_PDF_KEY", "Ict_mastery_for_jhs_1-3_bece_success.pdf")

# ✅ Check if email was already sent for this reference
def is_email_already_sent(reference):
    try:
        flag_key = f"sent_flags/{reference}.txt"
        s3_client.head_object(Bucket=BUCKET_NAME, Key=flag_key)
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
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
    return {"status": "ok", "message": "Email API running"}

# ✅ UPDATED: Now checks for duplicate sends
@app.post("/send-email")
async def send_email(
    name: str = Form(...),
    email: str = Form(...),
    message: str = Form(...),
    reference: str = Form(None)  # ✅ Added reference tracking
):
    print(f"📧 Received email request for: {email}, reference: {reference}")
    
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
            # Continue anyway - don't block the email
    
    try:
        pdf_content, content_type = get_pdf_from_bucket(DEFAULT_PDF_KEY)
        
        attachments = [{
            "filename": DEFAULT_PDF_KEY.split('/')[-1],
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
        
        # ✅ MARK: Record that this reference was emailed
        if reference:
            mark_email_as_sent(reference, email)
        
        return {
            "status": "success",
            "id": email_response["id"],
            "reference": reference
        }
        
    except Exception as e:
        print(f"❌ Email sending error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ✅ Optional: Endpoint to check if email was sent
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
    uvicorn.run(app, host="0.0.0.0", port=port)
