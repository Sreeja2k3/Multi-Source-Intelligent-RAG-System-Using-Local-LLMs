# src/ingestion/loader.py
import csv
import json
import io
import re
import urllib.request
from pathlib import Path
from typing import List

from loguru import logger
from langchain_core.documents import Document
from langchain_community.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
    TextLoader,
)

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    YouTubeTranscriptApi = None


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

    def load_csv(self, file_path: str) -> List[Document]:
        """Load a CSV file — each row becomes a document."""
        logger.info(f"Loading CSV: {file_path}")
        docs = []
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                # Combine all columns into readable text
                text = "\n".join(f"{key}: {value}" for key, value in row.items() if value)
                if text.strip():
                    docs.append(Document(
                        page_content=text,
                        metadata={
                            "source_type": "csv",
                            "file_name": Path(file_path).name,
                            "row_index": i,
                        },
                    ))
        logger.success(f"Loaded {len(docs)} rows from CSV")
        return docs

    def load_json(self, file_path: str) -> List[Document]:
        """Load a JSON file — handles both array of objects and single object."""
        logger.info(f"Loading JSON: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        docs = []
        # If it's a list, each item becomes a document
        if isinstance(data, list):
            for i, item in enumerate(data):
                if isinstance(item, dict):
                    text = "\n".join(f"{k}: {v}" for k, v in item.items() if v)
                else:
                    text = str(item)
                if text.strip():
                    docs.append(Document(
                        page_content=text,
                        metadata={
                            "source_type": "json",
                            "file_name": Path(file_path).name,
                            "item_index": i,
                        },
                    ))
        elif isinstance(data, dict):
            # Single object — flatten into one document
            text = json.dumps(data, indent=2, ensure_ascii=False)
            docs.append(Document(
                page_content=text,
                metadata={
                    "source_type": "json",
                    "file_name": Path(file_path).name,
                },
            ))

        logger.success(f"Loaded {len(docs)} items from JSON")
        return docs

    def load_url(self, url: str) -> List[Document]:
        """Scrapes URL using trafilatura for better text extraction, with fallback to BeautifulSoup."""
        url = url.strip().rstrip("\\")
        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"https://{url}"
        logger.info(f"Loading URL: {url}")

        try:
            import trafilatura
            downloaded = trafilatura.fetch_url(url)
            if downloaded:
                text = trafilatura.extract(downloaded, include_comments=False, include_tables=True)
                if text and len(text.strip()) > 100:
                    doc = Document(
                        page_content=text,
                        metadata={"source_type": "web", "url": url},
                    )
                    logger.success(f"Loaded {len(text)} chars from URL (trafilatura)")
                    return [doc]
        except ImportError:
            logger.warning("trafilatura not installed, falling back to BeautifulSoup")
        except Exception as e:
            logger.warning(f"trafilatura failed: {e}, falling back to BeautifulSoup")

        # Fallback to BeautifulSoup
        import requests
        from bs4 import BeautifulSoup

        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        lines = [line for line in text.splitlines() if line.strip()]
        clean_text = "\n".join(lines)

        doc = Document(
            page_content=clean_text,
            metadata={"source_type": "web", "url": url},
        )
        logger.success(f"Loaded {len(clean_text)} chars from URL (BeautifulSoup)")
        return [doc]

    def load_youtube(self, video_url: str) -> List[Document]:
        logger.info(f"Loading YouTube: {video_url}")

        video_id = None
        if "v=" in video_url:
            video_id = video_url.split("v=")[1].split("&")[0]
        elif "youtu.be/" in video_url:
            video_id = video_url.split("youtu.be/")[1].split("?")[0]
        elif "embed/" in video_url:
            video_id = video_url.split("embed/")[1].split("?")[0]
        elif "shorts/" in video_url:
            video_id = video_url.split("shorts/")[1].split("?")[0]
        elif "live/" in video_url:
            video_id = video_url.split("live/")[1].split("?")[0]
        else:
            cleaned = video_url.strip()
            if len(cleaned) == 11 and "/" not in cleaned:
                video_id = cleaned
                video_url = f"https://www.youtube.com/watch?v={video_id}"

        if not video_id:
            raise ValueError(f"Cannot extract video ID from: {video_url}")

        # Step 1: Fetch title & creator via YouTube oEmbed API (reliable and unblocked)
        title = f"YouTube Video ({video_id})"
        author = "YouTube"
        try:
            oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
            req = urllib.request.Request(oembed_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as r:
                oembed_data = json.loads(r.read().decode("utf-8"))
                title = oembed_data.get("title", title)
                author = oembed_data.get("author_name", author)
        except Exception as e:
            logger.warning(f"Could not fetch oEmbed metadata for {video_id}: {e}")

        # Step 2: Attempt to fetch subtitles / transcripts
        full_text = ""
        if YouTubeTranscriptApi:
            try:
                try:
                    entries = YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "en-US", "en-GB"])
                    full_text = " ".join([e["text"] for e in entries if e.get("text")])
                except Exception:
                    transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                    for t in transcript_list:
                        full_text = " ".join([e["text"] for e in t.fetch() if e.get("text")])
                        if full_text:
                            break
            except Exception as e:
                logger.warning(f"YouTube transcript API unavailable for {video_id} (likely datacenter IP restriction): {e}")

        # Step 3: Fallback / supplementary extraction from video webpage (description & syllabus)
        desc_text = ""
        try:
            watch_url = f"https://www.youtube.com/watch?v={video_id}"
            req = urllib.request.Request(watch_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=10) as r:
                html = r.read().decode("utf-8", errors="ignore")
                match = re.search(r'"shortDescription":"(.*?)"', html)
                if match:
                    raw_desc = match.group(1)
                    desc_text = re.sub(r'\\n', '\n', raw_desc)
                    desc_text = re.sub(r'\\"', '"', desc_text)
        except Exception as e:
            logger.warning(f"Could not scrape YouTube page description: {e}")

        # Compose rich document content
        content_parts = [f"Title: {title}", f"Channel / Creator: {author}", f"URL: {video_url}"]
        if full_text:
            content_parts.append(f"\nTranscript:\n{full_text}")
        elif desc_text:
            content_parts.append(f"\nVideo Overview & Description:\n{desc_text}")
        else:
            content_parts.append(f"\nIndexed YouTube Video: {title} by {author}.")

        content = "\n".join(content_parts)
        doc = Document(
            page_content=content,
            metadata={
                "source_type": "youtube",
                "file_name": video_url,
                "video_id": video_id,
                "title": title,
                "url": video_url,
            },
        )
        logger.success(f"Loaded YouTube video: '{title}' ({len(content)} chars)")
        return [doc]

    def load_from_directory(self, directory: str) -> List[Document]:
        directory = Path(directory)
        all_docs = []
        dispatch = {
            ".pdf": self.load_pdf,
            ".docx": self.load_docx,
            ".txt": self.load_txt,
            ".csv": self.load_csv,
            ".json": self.load_json,
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
