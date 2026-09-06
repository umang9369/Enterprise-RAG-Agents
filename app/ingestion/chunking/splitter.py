import logfire


def chunk_text(text: str, chunk_size: int = 1500) -> list[str]:
    """
    Simple semantic-ish chunker that splits by paragraphs.
    Ensures chunks do not exceed the specified size.
    """

    with logfire.span("text chunking"):
        if not text.strip():
            return []

        # Split by double newline first; if paragraphs exceed chunk_size, sub-split by single newline
        paragraphs = text.split("\n\n")
        sub_paragraphs: list[str] = []
        for p in paragraphs:
            if len(p) > chunk_size:
                lines = p.split("\n")
                buf = ""
                for line in lines:
                    if len(buf) + len(line) < chunk_size:
                        buf += line + "\n"
                    else:
                        if buf.strip():
                            sub_paragraphs.append(buf.strip())
                        while len(line) > chunk_size:
                            sub_paragraphs.append(line[:chunk_size])
                            line = line[chunk_size:]
                        buf = line + "\n"
                if buf.strip():
                    sub_paragraphs.append(buf.strip())
            else:
                sub_paragraphs.append(p)

        chunks: list[str] = []
        current_chunk = ""
        for p in sub_paragraphs:
            if len(current_chunk) + len(p) < chunk_size:
                current_chunk += p + "\n\n"
            else:
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                current_chunk = p + "\n\n"

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        valid_chunks = [c for c in chunks if c.strip()]
        logfire.info(f"[OK] Generated {len(valid_chunks)} chunks")

        return valid_chunks
