import logfire
from pypdf import PdfReader

def parse_pdf(file_path :str)->str:
    """
    Extract text from a PDF locally using pypdf.
    Falls back to pdfplumber for pages that yield no text (e.g. image-heavy pages).
    """
    
            
                

