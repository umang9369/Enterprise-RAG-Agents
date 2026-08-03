import logfire
from bs4 import BeautifulSoup

def parse_html(file_path:str):
    """
    Parses HTML content using BeautifulSoup.
    Cleans scripts, styles, and extracts readable text for RAG.
    """
    with logfire.span("html parsing",filename=file_path):
        try:
            with open(file_path,"r",encoding="utf-8",errors="ignore") as f:
                content=f.read()

            soup = BeautifulSoup(content,"html.parser")

            


        except Exception as e:
