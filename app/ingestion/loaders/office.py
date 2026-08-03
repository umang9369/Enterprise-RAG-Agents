import logfire
from unstructured.partition.auto import partition

def parse_office(file_path: str):
    """
    Parses Office documents (.docx, .pptx) using the Unstructured library.
    Unlike PDFs, these formats are structured and lightweight, so they are processed locally.
    """
    with logfire.span("parse_office",filename=file_path):
        try:
            # Unstructured automatically detects if it's docx or pptx
            elements=partition(filename=file_path)
            full_text="\n".join([str(el) for el in elements])

            
        except Exception as e:
            logfire.error(f"office parsing failed for : {e}")
            raise e