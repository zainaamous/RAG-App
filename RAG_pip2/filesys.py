import os, glob, hashlib, pathlib
from urllib.parse import urlparse
from typing import List
from langchain_core.documents import Document
from langchain_community.document_loaders import (
    PyPDFLoader, UnstructuredFileLoader, Docx2txtLoader, TextLoader,
    CSVLoader, BSHTMLLoader, WebBaseLoader
)

SUPPORTED_EXTS = {".pdf", ".docx", ".txt", ".md", ".log", ".csv", ".html", ".htm"}

def is_url(path: str) -> bool:
    p = urlparse(path)
    return p.scheme in ("http", "https")

def iter_files(paths: List[str]) -> List[str]:
    """Collect local files (and keep URLs as-is) with supported extensions."""
    found = []
    for p in paths:
        if is_url(p):
            found.append(p)
            continue
        p_abs = os.path.abspath(p)
        if os.path.isdir(p_abs):
            for root, _, files in os.walk(p_abs):
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in SUPPORTED_EXTS:
                        found.append(os.path.join(root, f))
        elif os.path.isfile(p_abs):
            ext = os.path.splitext(p_abs)[1].lower()
            if ext in SUPPORTED_EXTS:
                found.append(p_abs)
        else:
            # simple globs
            for g in glob.glob(p):
                if os.path.isfile(g) and os.path.splitext(g)[1].lower() in SUPPORTED_EXTS:
                    found.append(os.path.abspath(g))
    return sorted(set(found))

def load_one_local(path: str, user_agent: str) -> List[Document]:
    """Load a single local file into one or more Documents."""
    ext = pathlib.Path(path).suffix.lower()
    if ext == ".pdf":
        loader = PyPDFLoader(path)
    elif ext == ".docx":
        loader = Docx2txtLoader(path)
    elif ext in {".txt", ".md", ".log"}:
        loader = TextLoader(path, encoding="utf-8", autodetect_encoding=True)
    elif ext == ".csv":
        loader = CSVLoader(path)
    elif ext in {".html", ".htm"}:
        loader = BSHTMLLoader(path)
    else:
        loader = UnstructuredFileLoader(path)
    docs = loader.load()
    for d in docs:
        d.metadata = d.metadata or {}
        d.metadata["source"] = path
    return docs

def doc_uid_for_path(path: str) -> str:
    # stable, cross-run: hash normalized absolute path
    ap = os.path.abspath(path)
    return hashlib.sha1(ap.encode("utf-8")).hexdigest()[:12]

def doc_uid_for_content(path: str) -> str:
    # slower, but changes if file bytes change
    data = pathlib.Path(path).read_bytes()
    return hashlib.sha1(data).hexdigest()[:12]
