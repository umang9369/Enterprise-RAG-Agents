import logfire

def parse_text(file_path:str):
    """
    Parses plain text files.
    """

    with logfire.span("parse_text",filename=file_path):
        try:
            with open(file_path,"r",encoding="utf-8",errors="ignore")as f:
                return f.read()
        except Exception as e:
            logfire.error(f"Error occurred while parsing text file: {e}")
            raise e