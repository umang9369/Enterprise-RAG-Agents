import logfire
from unstructured.partition.auto import partition

def parse_office(file_path: str):
    """
    Parses Office documents (.docx, .pptx) using the Unstructured library.
    Unlike PDFs, these formats are structured and lightweight, so they are processed locally.
    """
    with logfire.span("parse_office",filename=file_path):
        try:
            elements=partition(filename=file_path)
            full_text="\n".join([str(el) for el in elements])

            if not full_text.strip():
                logfire.warning(f"office parsing failed for : {file_path}")
            else:
                logfire.info(f"succesfully parsed office file {len(full_text)} characters")

            return full_text
        except Exception as e:
            logfire.error(f"office parsing failed for : {e}")
            raise e