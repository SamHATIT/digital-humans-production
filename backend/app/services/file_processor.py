"""
File processor service for extracting text from various file formats.
Supports: PDF, DOCX, DOC, TXT
"""
import io
import logging
from typing import Optional
from PyPDF2 import PdfReader
from docx import Document
from fastapi import UploadFile

logger = logging.getLogger(__name__)


class FileProcessor:
    """Service for processing uploaded files and extracting text content."""
    
    @staticmethod
    async def extract_text_from_file(file: UploadFile) -> Optional[str]:
        """
        Extract text content from uploaded file.
        
        Args:
            file: FastAPI UploadFile object
            
        Returns:
            Extracted text content or None if extraction failed
        """
        try:
            content = await file.read()
            file_ext = file.filename.split('.')[-1].lower()
            
            if file_ext == 'txt':
                return FileProcessor._extract_from_txt(content)
            elif file_ext == 'pdf':
                return FileProcessor._extract_from_pdf(content)
            elif file_ext in ['doc', 'docx']:
                return FileProcessor._extract_from_docx(content)
            else:
                logger.error(f"Unsupported file extension: {file_ext}")
                return None
                
        except Exception as e:
            logger.error(f"Error extracting text from file: {str(e)}")
            return None
    
    @staticmethod
    def _extract_from_txt(content: bytes) -> str:
        """Extract text from TXT file."""
        try:
            return content.decode('utf-8')
        except UnicodeDecodeError:
            # Try with latin-1 as fallback
            return content.decode('latin-1')
    
    @staticmethod
    def _extract_from_pdf(content: bytes) -> str:
        """Extract text from PDF file."""
        try:
            pdf_file = io.BytesIO(content)
            pdf_reader = PdfReader(pdf_file)
            
            text_parts = []
            for page in pdf_reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            
            return '\n\n'.join(text_parts)
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {str(e)}")
            raise
    
    @staticmethod
    def _extract_from_docx(content: bytes) -> str:
        """Extract text from DOCX file."""
        try:
            docx_file = io.BytesIO(content)
            doc = Document(docx_file)
            
            text_parts = []
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_parts.append(paragraph.text)
            
            return '\n\n'.join(text_parts)
        except Exception as e:
            logger.error(f"Error extracting text from DOCX: {str(e)}")
            raise
