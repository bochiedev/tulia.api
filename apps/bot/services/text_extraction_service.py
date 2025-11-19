"""
Text extraction service for document processing.
"""
import logging
from typing import Dict, Any
import chardet
from PyPDF2 import PdfReader
import pdfplumber

logger = logging.getLogger(__name__)


class TextExtractionService:
    """
    Service for extracting text from various document formats.
    """
    
    @staticmethod
    def extract_from_pdf(file_path: str) -> Dict[str, Any]:
        """
        Extract text from PDF file.
        
        Args:
            file_path: Path to PDF file
        
        Returns:
            Dict with 'text', 'pages', and 'metadata'
        """
        try:
            # Try PyPDF2 first (faster)
            with open(file_path, 'rb') as file:
                reader = PdfReader(file)
                
                pages = []
                full_text = []
                
                for page_num, page in enumerate(reader.pages, start=1):
                    try:
                        text = page.extract_text()
                        if text and text.strip():
                            pages.append({
                                'page_number': page_num,
                                'text': text
                            })
                            full_text.append(text)
                    except Exception as e:
                        logger.warning(
                            f"Error extracting page {page_num} with PyPDF2: {e}"
                        )
                
                # If we got good text, return it
                if full_text and len(''.join(full_text).strip()) > 100:
                    return {
                        'text': '\n\n'.join(full_text),
                        'pages': pages,
                        'metadata': {
                            'num_pages': len(reader.pages),
                            'extraction_method': 'pypdf2'
                        }
                    }
                
                logger.info("PyPDF2 extraction insufficient, trying pdfplumber")
        
        except Exception as e:
            logger.warning(f"PyPDF2 extraction failed: {e}")
        
        # Fallback to pdfplumber (better for scanned PDFs)
        try:
            with pdfplumber.open(file_path) as pdf:
                pages = []
                full_text = []
                
                for page_num, page in enumerate(pdf.pages, start=1):
                    try:
                        text = page.extract_text()
                        if text and text.strip():
                            pages.append({
                                'page_number': page_num,
                                'text': text
                            })
                            full_text.append(text)
                    except Exception as e:
                        logger.warning(
                            f"Error extracting page {page_num} with pdfplumber: {e}"
                        )
                
                if not full_text:
                    raise ValueError("No text could be extracted from PDF")
                
                return {
                    'text': '\n\n'.join(full_text),
                    'pages': pages,
                    'metadata': {
                        'num_pages': len(pdf.pages),
                        'extraction_method': 'pdfplumber'
                    }
                }
        
        except Exception as e:
            logger.error(f"pdfplumber extraction failed: {e}")
            raise ValueError(f"Failed to extract text from PDF: {e}")
    
    @staticmethod
    def extract_from_text(file_path: str) -> Dict[str, Any]:
        """
        Extract text from text file with encoding detection.
        
        Args:
            file_path: Path to text file
        
        Returns:
            Dict with 'text' and 'metadata'
        """
        try:
            # Detect encoding
            with open(file_path, 'rb') as file:
                raw_data = file.read()
                result = chardet.detect(raw_data)
                encoding = result['encoding'] or 'utf-8'
                confidence = result['confidence']
            
            logger.info(
                f"Detected encoding: {encoding} "
                f"(confidence: {confidence:.2f})"
            )
            
            # Read with detected encoding
            try:
                with open(file_path, 'r', encoding=encoding) as file:
                    text = file.read()
            except UnicodeDecodeError:
                # Fallback to utf-8 with error handling
                logger.warning(f"Failed to decode with {encoding}, trying utf-8")
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
                    text = file.read()
                encoding = 'utf-8 (with errors ignored)'
            
            if not text or not text.strip():
                raise ValueError("Text file is empty")
            
            return {
                'text': text,
                'pages': [{
                    'page_number': 1,
                    'text': text
                }],
                'metadata': {
                    'encoding': encoding,
                    'encoding_confidence': confidence,
                    'extraction_method': 'text'
                }
            }
        
        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            raise ValueError(f"Failed to extract text from file: {e}")
    
    @classmethod
    def extract(cls, file_path: str, file_type: str) -> Dict[str, Any]:
        """
        Extract text from file based on type.
        
        Args:
            file_path: Path to file
            file_type: File type (pdf, txt)
        
        Returns:
            Dict with extracted text and metadata
        """
        if file_type == 'pdf':
            return cls.extract_from_pdf(file_path)
        elif file_type == 'txt':
            return cls.extract_from_text(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
