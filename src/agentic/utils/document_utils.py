import sys
from pathlib import Path

from src.agentic.exception import CustomException
from src.agentic.logger import logging


def extract_text(file_path: str) -> str:
    """Extract plain text from a .pdf or .docx itinerary knowledge-base file."""
    path = Path(file_path)
    if not path.exists():
        raise CustomException(
            FileNotFoundError(
                f"Itinerary knowledge base file not found at '{file_path}'. "
                "Set ITINERARY_PDF_PATH to a real file before starting the app."
            ),
            sys,
        )

    try:
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            import fitz  # PyMuPDF

            doc = fitz.open(str(path))
            text = "\n".join(page.get_text() for page in doc)
            doc.close()
            return text

        if suffix == ".docx":
            import docx

            document = docx.Document(str(path))
            return "\n".join(p.text for p in document.paragraphs)

        raise ValueError(f"Unsupported itinerary file type: {suffix}")

    except CustomException:
        raise
    except Exception as e:
        logging.exception("Failed to extract text from %s", file_path)
        raise CustomException(e, sys) from e
