import logfire
from bs4 import BeautifulSoup


def parse_html(file_path: str):
    """
    Parses HTML content using BeautifulSoup.
    Cleans scripts, styles, and extracts readable text for RAG.
    """

    with logfire.span("html parsing", filename=file_path):
        try:
            with open(
                file_path,
                "r",
                encoding="utf-8",
                errors="ignore",
            ) as f:
                content = f.read()

            soup = BeautifulSoup(
                content,
                "html.parser",
            )

            # 1. Remove junk
            for script in soup(
                ["script", "style", "meta", "noscript"]
            ):
                script.decompose()

            # 2. Extract text
            text = soup.get_text(
                separator="\n"
            )

            # 3. Clean whitespace
            lines = (
                line.strip()
                for line in text.splitlines()
            )

            chunks = (
                phrase.strip()
                for line in lines
                for phrase in line.split("   ")
            )

            text_clean = "\n".join(
                chunk
                for chunk in chunks
                if chunk
            )

            return text_clean

        except Exception as e:
            logfire.error(
                f"html parser is failed: {e}"
            )
            raise