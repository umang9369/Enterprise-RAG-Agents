import logfire
from bs4 import BeautifulSoup

def parse_html(file_path:str):
    """
    Parses HTML content using BeautifulSoup.
    Cleans scripts, styles, and extracts readable text for RAG.
    """
