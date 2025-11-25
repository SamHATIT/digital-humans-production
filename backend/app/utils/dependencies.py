"""
FastAPI dependencies for authentication and authorization.
"""
from typing import Optional
from fastapi import Depends, HTTPException, status, Query, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.utils.auth import decode_access_token

# HTTP Bearer security scheme - auto_error=False allows query param fallback
security = HTTPBearer(auto_error=False)


def _authenticate_user(token: str, db: Session) -> User:
    """
    Authenticate user from JWT token.
    
    Args:
        token: JWT token string
        db: Database session
        
    Returns:
        Authenticated user
        
    Raises:
        HTTPException: If authentication fails
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = decode_access_token(token)
    
    if payload is None:
        raise credentials_exception
    
    user_id_str = payload.get("sub")
    
    if user_id_str is None:
        raise credentials_exception
    
    try:
        user_id: int = int(user_id_str)
    except (ValueError, TypeError):
        raise credentials_exception
    
    user = db.query(User).filter(User.id == user_id).first()
    
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    
    return user


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Get the current authenticated user from JWT token in Authorization header.

    Args:
        credentials: HTTP Bearer credentials (JWT token)
        db: Database session

    Returns:
        Current authenticated user

    Raises:
        HTTPException: If token is invalid or user not found
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return _authenticate_user(credentials.credentials, db)


async def get_current_user_from_token_or_header(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    token: Optional[str] = Query(None, description="JWT token (alternative to Authorization header for SSE)"),
    db: Session = Depends(get_db)
) -> User:
    """
    Get the current authenticated user from JWT token.
    
    Supports two authentication methods:
    1. Authorization header (Bearer token) - preferred for regular API calls
    2. Query parameter 'token' - for SSE/EventSource which cannot send headers
    
    Args:
        credentials: HTTP Bearer credentials from header
        token: JWT token from query parameter
        db: Database session

    Returns:
        Current authenticated user

    Raises:
        HTTPException: If no valid authentication provided
    """
    # Try header first, then query parameter
    jwt_token = None
    
    if credentials and credentials.credentials:
        jwt_token = credentials.credentials
    elif token:
        jwt_token = token
    
    if not jwt_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials. Provide Authorization header or token query parameter.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return _authenticate_user(jwt_token, db)


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get the current active user.

    Args:
        current_user: Current authenticated user

    Returns:
        Current active user

    Raises:
        HTTPException: If user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user
