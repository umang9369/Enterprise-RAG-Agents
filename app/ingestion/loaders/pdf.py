import logfire
from pypdf import PdfReader

def parse_pdf(file_path :str)->str:
    """
    Extract text from a PDF locally using pypdf.
    Falls back to pdfplumber for pages that yield no text (e.g. image-heavy pages).
    """
    with logfire.span("parse_pdf",filename=file_path):
            try:
                reader =PdfReader(file_path)
                total_pages=len(reader.pages)
                logfire.info(f"Total pages in PDF: {total_pages}")
    
                text_parts:list[str]=[]
                blank_parts:list[int]=[]
    
                
    
            
                

