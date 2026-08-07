import logfire

def parse_text(file_path:str):
    """
    Parses plain text files.
    """

    with logfire.span("parse_text",filename=file_path):
        