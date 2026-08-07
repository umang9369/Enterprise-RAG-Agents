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
    
                for i,page in enumerate(reader.pages):
                                    text=page.extract_ptext() or ""
                                    if text.strip():
                                        text_parts.append(text)
                                    else:
                                        blank_pages.append(i+1)   

                # Fallback: use pdfplumber for any pages pypdf returned blank
                if blank_pages:
                        logfire.info(f"pypdf returned blank on pages {blank_pages} — retrying with pdfplumber.")
                        try:
                            import pdfplumber

                            with pdfplumber.open(file_path)as pdf:
                                   for page_num in blank_pages:
                                        page=pdf.pages[page_num-1]
                                        fallback_text=page.extract_text() or ""
                                        if fallback_text.strip():
                                               text_parts.append(fallback_text)
                        except Exception as plumber_err:
                            logfire.warning(f"Error occurred while using pdfplumber: {plumber_err}")
                ful_text="\n".join(text_parts)

                if not ful_text.strip():
                    logfire.warning("No text could be extracted from the PDF.")
                else :
                    logfire.info(f"Extracted text length: {len(ful_text)} characters")
                return ful_text
            except Exception as e:
                logfire.error(f"Error occurred while parsing PDF: {e}")
                raise
                

