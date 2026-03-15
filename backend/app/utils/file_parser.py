"""
File parsing utilities
Supports text extraction from PDF, Markdown, TXT, images, and video files
"""

import base64
import os
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

from ..config import Config


def _read_text_with_fallback(file_path: str) -> str:
    """
    Read text file with automatic encoding detection when UTF-8 fails.
    
    Uses multi-level fallback strategy:
    1. First try UTF-8 decoding
    2. Use charset_normalizer to detect encoding
    3. Fall back to chardet encoding detection
    4. Final fallback: UTF-8 + errors='replace'
    
    Args:
        file_path: File path

    Returns:
        Decoded text content
    """
    data = Path(file_path).read_bytes()
    
    # First try UTF-8
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        pass
    
    # Try charset_normalizer for encoding detection
    encoding = None
    try:
        from charset_normalizer import from_bytes
        best = from_bytes(data).best()
        if best and best.encoding:
            encoding = best.encoding
    except Exception:
        pass
    
    # Fall back to chardet
    if not encoding:
        try:
            import chardet
            result = chardet.detect(data)
            encoding = result.get('encoding') if result else None
        except Exception:
            pass
    
    # Final fallback: UTF-8 + replace
    if not encoding:
        encoding = 'utf-8'
    
    return data.decode(encoding, errors='replace')


class FileParser:
    """File parser"""
    
    TEXT_EXTENSIONS = {'.pdf', '.md', '.markdown', '.txt'}
    IMAGE_EXTENSIONS = {f'.{e}' for e in Config.IMAGE_EXTENSIONS}
    VIDEO_EXTENSIONS = {f'.{e}' for e in Config.VIDEO_EXTENSIONS}
    SUPPORTED_EXTENSIONS = TEXT_EXTENSIONS | IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
    
    @classmethod
    def extract_text(cls, file_path: str) -> str:
        """
        Extract text from any supported file type.
        - PDF/MD/TXT: direct text extraction
        - Images: LLM vision analysis → text description
        - Video: audio extraction → Whisper transcription + keyframe vision analysis
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        suffix = path.suffix.lower()
        
        if suffix not in cls.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file format: {suffix}")
        
        if suffix == '.pdf':
            return cls._extract_from_pdf(file_path)
        elif suffix in {'.md', '.markdown'}:
            return cls._extract_from_md(file_path)
        elif suffix == '.txt':
            return cls._extract_from_txt(file_path)
        elif suffix in cls.IMAGE_EXTENSIONS:
            return cls._extract_from_image(file_path)
        elif suffix in cls.VIDEO_EXTENSIONS:
            return cls._extract_from_video(file_path)
        
        raise ValueError(f"Unable to process file format: {suffix}")
    
    @staticmethod
    def _extract_from_pdf(file_path: str) -> str:
        """Extract text from PDF"""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise ImportError("PyMuPDF required: pip install PyMuPDF")
        
        text_parts = []
        with fitz.open(file_path) as doc:
            for page in doc:
                text = page.get_text()
                if text.strip():
                    text_parts.append(text)
        
        return "\n\n".join(text_parts)
    
    @staticmethod
    def _extract_from_md(file_path: str) -> str:
        """Extract text from Markdown with auto encoding detection"""
        return _read_text_with_fallback(file_path)
    
    @staticmethod
    def _extract_from_txt(file_path: str) -> str:
        """Extract text from TXT with auto encoding detection"""
        return _read_text_with_fallback(file_path)
    
    @staticmethod
    def _extract_from_image(file_path: str) -> str:
        """
        Analyze image using LLM vision API.
        Encodes the image as base64 and sends it to the vision-capable model
        for a detailed textual description and analysis.
        """
        from openai import OpenAI

        path = Path(file_path)
        mime_map = {
            '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
            '.png': 'image/png', '.webp': 'image/webp',
            '.gif': 'image/gif', '.bmp': 'image/bmp',
        }
        mime = mime_map.get(path.suffix.lower(), 'image/png')
        b64 = base64.b64encode(path.read_bytes()).decode('utf-8')
        data_url = f"data:{mime};base64,{b64}"

        client = OpenAI(api_key=Config.LLM_API_KEY, base_url=Config.LLM_BASE_URL)
        response = client.chat.completions.create(
            model=Config.LLM_MODEL_NAME,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": (
                        "Analyze this image in detail for use in a predictive simulation. "
                        "Extract ALL visible text (OCR). Describe every chart, graph, table, diagram, "
                        "logo, person, scene, and data point. Be exhaustive — this output will be the "
                        "only representation of the image in the knowledge graph."
                    )},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }],
            max_tokens=4096,
            temperature=0.2,
        )
        description = response.choices[0].message.content or ""
        return f"[Image Analysis: {path.name}]\n{description}"

    @staticmethod
    def _extract_from_video(file_path: str) -> str:
        """
        Extract content from video:
        1. Extract audio track → transcribe via OpenAI Whisper API
        2. Extract keyframes → analyze via LLM vision
        Combines both into a single text document.
        """
        from openai import OpenAI

        path = Path(file_path)
        parts = [f"[Video Analysis: {path.name}]"]
        vision_client = OpenAI(api_key=Config.LLM_API_KEY, base_url=Config.LLM_BASE_URL)

        # --- Audio transcription via OpenAI Whisper ---
        audio_path = None
        try:
            audio_path = tempfile.mktemp(suffix='.mp3')
            result = subprocess.run(
                ['ffmpeg', '-i', str(path), '-vn', '-acodec', 'libmp3lame',
                 '-ar', '16000', '-ac', '1', '-q:a', '6', '-y', audio_path],
                capture_output=True, timeout=300,
            )
            if result.returncode == 0 and os.path.getsize(audio_path) > 1000:
                whisper_key = Config.OPENAI_API_KEY or Config.LLM_API_KEY
                whisper_client = OpenAI(api_key=whisper_key, base_url='https://api.openai.com/v1')
                with open(audio_path, 'rb') as af:
                    transcript = whisper_client.audio.transcriptions.create(
                        model='whisper-1',
                        file=af,
                        response_format='text',
                    )
                if transcript and transcript.strip():
                    parts.append(f"\n--- Transcript ---\n{transcript.strip()}")
            else:
                parts.append("\n[Audio extraction failed or no audio track]")
        except FileNotFoundError:
            parts.append("\n[ffmpeg not installed — audio transcription skipped]")
        except Exception as e:
            parts.append(f"\n[Audio transcription error: {e}]")
        finally:
            if audio_path and os.path.exists(audio_path):
                os.unlink(audio_path)

        # --- Keyframe analysis ---
        frames_dir = None
        try:
            frames_dir = tempfile.mkdtemp()
            frame_path = os.path.join(frames_dir, 'frame_%03d.jpg')
            subprocess.run(
                ['ffmpeg', '-i', str(path), '-vf', 'fps=1/15,scale=512:-1',
                 '-frames:v', '4', '-q:v', '3', '-y', frame_path],
                capture_output=True, timeout=120,
            )
            frame_files = sorted(Path(frames_dir).glob('*.jpg'))
            if frame_files:
                parts.append("\n--- Visual Analysis (keyframes) ---")
                for i, fp in enumerate(frame_files[:4]):
                    b64 = base64.b64encode(fp.read_bytes()).decode('utf-8')
                    resp = vision_client.chat.completions.create(
                        model=Config.LLM_MODEL_NAME,
                        messages=[{
                            "role": "user",
                            "content": [
                                {"type": "text", "text": f"Describe keyframe {i+1} of a video. Extract all visible text, data, charts, people, and context."},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                            ],
                        }],
                        max_tokens=1024,
                        temperature=0.2,
                    )
                    desc = resp.choices[0].message.content or ""
                    parts.append(f"\nKeyframe {i+1}:\n{desc}")
        except FileNotFoundError:
            parts.append("\n[ffmpeg not installed — keyframe analysis skipped]")
        except Exception as e:
            parts.append(f"\n[Keyframe analysis error: {e}]")
        finally:
            if frames_dir and os.path.exists(frames_dir):
                import shutil
                shutil.rmtree(frames_dir, ignore_errors=True)

        return "\n".join(parts)

    @staticmethod
    def extract_from_url(url: str) -> str:
        """
        Extract text content from a URL.
        Detects YouTube links and routes to the YouTube-specific extractor.
        For regular web pages, uses requests + BeautifulSoup.
        """
        if FileParser._is_youtube_url(url):
            return FileParser.extract_from_youtube(url)

        import requests
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            raise ImportError("beautifulsoup4 required: pip install beautifulsoup4")

        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AgenikPredict/1.0'
        }
        try:
            resp = requests.get(url, headers=headers, timeout=30)
        except requests.exceptions.SSLError:
            resp = requests.get(url, headers=headers, timeout=30, verify=False)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, 'html.parser')

        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'noscript', 'iframe']):
            tag.decompose()

        title = soup.title.string.strip() if soup.title and soup.title.string else url

        # Prioritize article/main content
        main = soup.find('article') or soup.find('main') or soup.find('body')
        text = main.get_text(separator='\n', strip=True) if main else ''

        # Trim excessively long pages
        if len(text) > 50000:
            text = text[:50000] + '\n\n[Content truncated at 50,000 characters]'

        if not text.strip():
            text = '[No extractable text content found on this page]'

        return f"[Web Page: {title}]\nURL: {url}\n\n{text}"

    @staticmethod
    def _is_youtube_url(url: str) -> bool:
        return any(host in url for host in [
            'youtube.com/watch', 'youtu.be/', 'youtube.com/shorts',
            'youtube.com/live', 'youtube.com/embed'
        ])

    @staticmethod
    def extract_from_youtube(url: str) -> str:
        """
        Extract content from a YouTube video:
        1. Fetch video metadata (title, description, duration, channel)
        2. Download auto-generated or manual subtitles/captions
        3. If no subtitles — download audio and transcribe via Whisper
        """
        import json as _json

        parts = []

        # --- Metadata ---
        try:
            meta_result = subprocess.run(
                ['yt-dlp', '--dump-json', '--no-download', url],
                capture_output=True, text=True, timeout=30,
            )
            if meta_result.returncode == 0:
                meta = _json.loads(meta_result.stdout)
                title = meta.get('title', 'Unknown')
                channel = meta.get('channel', meta.get('uploader', 'Unknown'))
                duration = meta.get('duration_string', str(meta.get('duration', '?')))
                description = meta.get('description', '')
                parts.append(f"[YouTube Video: {title}]")
                parts.append(f"Channel: {channel}")
                parts.append(f"Duration: {duration}")
                parts.append(f"URL: {url}")
                if description:
                    desc_trimmed = description[:3000]
                    if len(description) > 3000:
                        desc_trimmed += '...'
                    parts.append(f"\n--- Description ---\n{desc_trimmed}")
        except Exception as e:
            parts.append(f"[YouTube Video]\nURL: {url}\n[Metadata fetch error: {e}]")

        # --- Subtitles (preferred — no API cost) ---
        subtitle_text = None
        sub_dir = None
        try:
            sub_dir = tempfile.mkdtemp()
            sub_path = os.path.join(sub_dir, 'subs')
            sub_result = subprocess.run(
                ['yt-dlp', '--skip-download',
                 '--write-auto-sub', '--write-sub',
                 '--sub-lang', 'en,ru,he,es,de',
                 '--sub-format', 'vtt',
                 '--convert-subs', 'srt',
                 '-o', sub_path, url],
                capture_output=True, text=True, timeout=60,
            )
            srt_files = list(Path(sub_dir).glob('*.srt'))
            if srt_files:
                raw = srt_files[0].read_text(errors='replace')
                import re as _re
                lines = []
                for line in raw.splitlines():
                    line = line.strip()
                    if not line or _re.match(r'^\d+$', line) or '-->' in line:
                        continue
                    clean = _re.sub(r'<[^>]+>', '', line)
                    if clean and clean not in lines[-1:]:
                        lines.append(clean)
                subtitle_text = ' '.join(lines)
        except Exception:
            pass
        finally:
            if sub_dir and os.path.exists(sub_dir):
                import shutil
                shutil.rmtree(sub_dir, ignore_errors=True)

        if subtitle_text and len(subtitle_text) > 50:
            if len(subtitle_text) > 50000:
                subtitle_text = subtitle_text[:50000] + '\n[Transcript truncated at 50,000 characters]'
            parts.append(f"\n--- Transcript (subtitles) ---\n{subtitle_text}")
            return "\n".join(parts)

        # --- Fallback: download audio → Whisper ---
        audio_path = None
        try:
            audio_path = tempfile.mktemp(suffix='.mp3')
            dl_result = subprocess.run(
                ['yt-dlp', '-x', '--audio-format', 'mp3',
                 '--audio-quality', '6',
                 '-o', audio_path, url],
                capture_output=True, text=True, timeout=300,
            )
            actual_path = audio_path
            if not os.path.exists(actual_path):
                candidates = list(Path(os.path.dirname(audio_path)).glob(
                    os.path.basename(audio_path).replace('.mp3', '*')))
                if candidates:
                    actual_path = str(candidates[0])

            if os.path.exists(actual_path) and os.path.getsize(actual_path) > 1000:
                from openai import OpenAI
                whisper_key = Config.OPENAI_API_KEY or Config.LLM_API_KEY
                whisper_client = OpenAI(api_key=whisper_key, base_url='https://api.openai.com/v1')
                with open(actual_path, 'rb') as af:
                    transcript = whisper_client.audio.transcriptions.create(
                        model='whisper-1', file=af, response_format='text')
                if transcript and transcript.strip():
                    parts.append(f"\n--- Transcript (Whisper) ---\n{transcript.strip()}")
            else:
                parts.append("\n[Audio download failed]")
        except FileNotFoundError:
            parts.append("\n[yt-dlp not installed — audio transcription skipped]")
        except Exception as e:
            parts.append(f"\n[Audio transcription error: {e}]")
        finally:
            if audio_path:
                for p in [audio_path, audio_path.replace('.mp3', '.webm'),
                          audio_path.replace('.mp3', '.m4a')]:
                    if os.path.exists(p):
                        os.unlink(p)

        if len(parts) <= 2:
            parts.append("\n[No transcript could be extracted from this video]")

        return "\n".join(parts)

    @staticmethod
    def extract_from_screenshot(file_path: str) -> str:
        """
        Alias for _extract_from_image — treats a screenshot exactly like
        any other image: full OCR + visual analysis via LLM vision.
        """
        return FileParser._extract_from_image(file_path)

    @classmethod
    def extract_from_multiple(cls, file_paths: List[str]) -> str:
        """
        Extract and merge text from multiple files
        
        Args:
            file_paths: List of file paths

        Returns:
            Merged text
        """
        all_texts = []
        
        for i, file_path in enumerate(file_paths, 1):
            try:
                text = cls.extract_text(file_path)
                filename = Path(file_path).name
                all_texts.append(f"=== Document {i}: {filename} ===\n{text}")
            except Exception as e:
                all_texts.append(f"=== Document {i}: {file_path} (extraction failed: {str(e)}) ===")
        
        return "\n\n".join(all_texts)


def split_text_into_chunks(
    text: str, 
    chunk_size: int = 500, 
    overlap: int = 50
) -> List[str]:
    """
    Split text into small chunks
    
    Args:
        text: Original text
        chunk_size: Characters per chunk
        overlap: Overlap characters

    Returns:
        List of text chunks
    """
    if len(text) <= chunk_size:
        return [text] if text.strip() else []
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        
        # Try to split at sentence boundaries
        if end < len(text):
            # Find nearest sentence ending
            for sep in ['\u3002', '\uff01', '\uff1f', '.\n', '!\n', '?\n', '\n\n', '. ', '! ', '? ']:
                last_sep = text[start:end].rfind(sep)
                if last_sep != -1 and last_sep > chunk_size * 0.3:
                    end = start + last_sep + len(sep)
                    break
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        # Next chunk starts from overlap position
        start = end - overlap if end < len(text) else len(text)
    
    return chunks

