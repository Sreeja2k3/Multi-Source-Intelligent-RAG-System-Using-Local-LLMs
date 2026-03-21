# src/ingestion/loader.py
from pathlib import Path
from typing import List

from loguru import logger
from langchain_core.documents import Document

# These are all from langchain-community — one package, safe to import together
from langchain_community.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
    TextLoader,
)

# WebBaseLoader needs lxml or html.parser — we use bs4 directly to be safe
import requests
from bs4 import BeautifulSoup

from youtube_transcript_api import YouTubeTranscriptApi


class MultiSourceLoader:

    def load_pdf(self, file_path: str) -> List[Document]:
        logger.info(f"Loading PDF: {file_path}")
        loader = PyPDFLoader(file_path)
        docs = loader.load()
        for doc in docs:
            doc.metadata["source_type"] = "pdf"
            doc.metadata["file_name"] = Path(file_path).name
        logger.success(f"Loaded {len(docs)} pages from PDF")
        return docs

    def load_docx(self, file_path: str) -> List[Document]:
        logger.info(f"Loading DOCX: {file_path}")
        loader = Docx2txtLoader(file_path)
        docs = loader.load()
        for doc in docs:
            doc.metadata["source_type"] = "docx"
            doc.metadata["file_name"] = Path(file_path).name
        logger.success(f"Loaded DOCX: {Path(file_path).name}")
        return docs

    def load_txt(self, file_path: str) -> List[Document]:
        logger.info(f"Loading TXT: {file_path}")
        loader = TextLoader(file_path, encoding="utf-8")
        docs = loader.load()
        for doc in docs:
            doc.metadata["source_type"] = "txt"
            doc.metadata["file_name"] = Path(file_path).name
        return docs

    def load_url(self, url: str) -> List[Document]:
        """
        Scrapes URL using requests + BeautifulSoup directly.
        More reliable than WebBaseLoader which can fail on some sites.
        """
        logger.info(f"Loading URL: {url}")
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()  # raises HTTPError if status != 200

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove script and style tags — we only want readable text
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)

        # Remove blank lines
        lines = [line for line in text.splitlines() if line.strip()]
        clean_text = "\n".join(lines)

        doc = Document(
            page_content=clean_text,
            metadata={"source_type": "web", "url": url},
        )
        logger.success(f"Loaded {len(clean_text)} chars from URL")
        return [doc]

    def load_youtube(self, video_url: str) -> List[Document]:
        logger.info(f"Loading YouTube: {video_url}")

        # Extract video ID — handle both youtube.com and youtu.be formats
        if "v=" in video_url:
            video_id = video_url.split("v=")[1].split("&")[0]
        elif "youtu.be/" in video_url:
            video_id = video_url.split("youtu.be/")[1].split("?")[0]
        else:
            raise ValueError(f"Cannot extract video ID from: {video_url}")

        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        full_text = " ".join([entry["text"] for entry in transcript_list])

        doc = Document(
            page_content=full_text,
            metadata={"source_type": "youtube", "video_id": video_id, "url": video_url},
        )
        logger.success(f"Loaded YouTube transcript ({len(full_text)} chars)")
        return [doc]

    def load_from_directory(self, directory: str) -> List[Document]:
        directory = Path(directory)
        all_docs = []
        dispatch = {
            ".pdf": self.load_pdf,
            ".docx": self.load_docx,
            ".txt": self.load_txt,
        }
        for file_path in directory.iterdir():
            if file_path.suffix.lower() in dispatch:
                try:
                    docs = dispatch[file_path.suffix.lower()](str(file_path))
                    all_docs.extend(docs)
                except Exception as e:
                    logger.error(f"Failed to load {file_path.name}: {e}")
        logger.success(f"Loaded {len(all_docs)} documents from {directory}")
        return all_docs
