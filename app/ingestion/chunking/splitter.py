from typinf import List
import logfire

def chunk_text(text:str,chunk_size:int =1500)->list[str]:
    """
    Simple semantic-ish chunker that splits by paragraphs.
    Ensures chunks do not exceed the specified size.
    """
    