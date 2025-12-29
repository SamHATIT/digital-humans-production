"""
Lead capture endpoints for Digital Humans website
With double opt-in verification
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, timedelta
import asyncpg
import secrets
from app.config import settings

router = APIRouter(prefix="/leads", tags=["leads"])

# Token expires after 24 hours
TOKEN_EXPIRY_HOURS = 24

class LeadCreate(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    company: Optional[str] = None
    source: Optional[str] = "website"
    newsletter: Optional[bool] = True

class LeadResponse(BaseModel):
    id: int
    email: str
    verification_token: str
    message: str

class VerifyResponse(BaseModel):
    success: bool
    email: str
    message: str

@router.post("", response_model=LeadResponse)
async def create_lead(lead: LeadCreate):
    """Create a new lead - requires email verification"""
    try:
        conn = await asyncpg.connect(settings.DATABASE_URL)
        try:
            # Generate verification token
            token = secrets.token_urlsafe(32)
            expires_at = datetime.now() + timedelta(hours=TOKEN_EXPIRY_HOURS)
            
            # Insert or update lead
            result = await conn.fetchrow("""
                INSERT INTO leads (email, name, company, source, subscribed_newsletter, 
                                   verification_token, token_expires_at, verified)
                VALUES ($1, $2, $3, $4, $5, $6, $7, false)
                ON CONFLICT (email) DO UPDATE SET
                    name = COALESCE(EXCLUDED.name, leads.name),
                    company = COALESCE(EXCLUDED.company, leads.company),
                    subscribed_newsletter = EXCLUDED.subscribed_newsletter,
                    verification_token = EXCLUDED.verification_token,
                    token_expires_at = EXCLUDED.token_expires_at,
                    verified = CASE WHEN leads.verified THEN true ELSE false END
                RETURNING id, email, verification_token
            """, lead.email, lead.name, lead.company, lead.source, lead.newsletter, 
                token, expires_at)
            
            return LeadResponse(
                id=result['id'],
                email=result['email'],
                verification_token=result['verification_token'],
                message="Verification email will be sent"
            )
        finally:
            await conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/verify", response_class=HTMLResponse)
async def verify_email(token: str = Query(..., description="Verification token")):
    """Verify email address via token"""
    try:
        conn = await asyncpg.connect(settings.DATABASE_URL)
        try:
            # Find lead by token
            lead = await conn.fetchrow("""
                SELECT id, email, verified, token_expires_at 
                FROM leads 
                WHERE verification_token = $1
            """, token)
            
            if not lead:
                return HTMLResponse(content=get_error_page("Invalid verification link"), status_code=400)
            
            if lead['verified']:
                return HTMLResponse(content=get_success_page(lead['email'], already_verified=True))
            
            if lead['token_expires_at'] and lead['token_expires_at'] < datetime.now():
                return HTMLResponse(content=get_error_page("Verification link has expired. Please request a new one."), status_code=400)
            
            # Mark as verified
            await conn.execute("""
                UPDATE leads 
                SET verified = true, verified_at = NOW(), verification_token = NULL
                WHERE id = $1
            """, lead['id'])
            
            return HTMLResponse(content=get_success_page(lead['email']))
            
        finally:
            await conn.close()
    except Exception as e:
        return HTMLResponse(content=get_error_page(f"Error: {str(e)}"), status_code=500)

@router.get("/count")
async def get_leads_count(verified_only: bool = False):
    """Get total number of leads"""
    try:
        conn = await asyncpg.connect(settings.DATABASE_URL)
        try:
            if verified_only:
                count = await conn.fetchval("SELECT COUNT(*) FROM leads WHERE verified = true")
            else:
                count = await conn.fetchval("SELECT COUNT(*) FROM leads")
            return {"count": count, "verified_only": verified_only}
        finally:
            await conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


def get_success_page(email: str, already_verified: bool = False) -> str:
    """Generate success HTML page"""
    title = "Already Verified!" if already_verified else "Email Verified!"
    message = f"Your email <strong>{email}</strong> was already verified." if already_verified else f"Your email <strong>{email}</strong> has been verified successfully!"
    submessage = "" if already_verified else "We'll be in touch with you shortly."
    
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title} - Digital Humans</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
            }}
            .container {{
                text-align: center;
                padding: 3rem;
                background: rgba(255,255,255,0.05);
                border-radius: 1.5rem;
                border: 1px solid rgba(255,255,255,0.1);
                max-width: 500px;
                margin: 1rem;
            }}
            .icon {{ font-size: 4rem; margin-bottom: 1.5rem; }}
            h1 {{ font-size: 2rem; margin-bottom: 1rem; color: #22d3ee; }}
            p {{ color: #94a3b8; line-height: 1.6; margin-bottom: 1rem; }}
            p strong {{ color: white; }}
            .btn {{
                display: inline-block;
                margin-top: 1.5rem;
                padding: 1rem 2rem;
                background: linear-gradient(135deg, #06b6d4, #0891b2);
                color: white;
                text-decoration: none;
                border-radius: 0.75rem;
                font-weight: 600;
                transition: transform 0.2s;
            }}
            .btn:hover {{ transform: scale(1.05); }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="icon">✅</div>
            <h1>{title}</h1>
            <p>{message}</p>
            <p>{submessage}</p>
            <a href="https://digital-humans.fr" class="btn">Back to Digital Humans</a>
        </div>
    </body>
    </html>
    """

def get_error_page(error_message: str) -> str:
    """Generate error HTML page"""
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Verification Error - Digital Humans</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
            }}
            .container {{
                text-align: center;
                padding: 3rem;
                background: rgba(255,255,255,0.05);
                border-radius: 1.5rem;
                border: 1px solid rgba(239,68,68,0.3);
                max-width: 500px;
                margin: 1rem;
            }}
            .icon {{ font-size: 4rem; margin-bottom: 1.5rem; }}
            h1 {{ font-size: 2rem; margin-bottom: 1rem; color: #f87171; }}
            p {{ color: #94a3b8; line-height: 1.6; }}
            .btn {{
                display: inline-block;
                margin-top: 1.5rem;
                padding: 1rem 2rem;
                background: linear-gradient(135deg, #06b6d4, #0891b2);
                color: white;
                text-decoration: none;
                border-radius: 0.75rem;
                font-weight: 600;
                transition: transform 0.2s;
            }}
            .btn:hover {{ transform: scale(1.05); }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="icon">❌</div>
            <h1>Verification Failed</h1>
            <p>{error_message}</p>
            <a href="https://digital-humans.fr" class="btn">Back to Digital Humans</a>
        </div>
    </body>
    </html>
    """
