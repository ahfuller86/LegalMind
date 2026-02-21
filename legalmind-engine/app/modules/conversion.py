import uuid
import pdfplumber
import docx
import shutil
import os
import mimetypes
from typing import List, Optional
from PIL import Image
from app.core.stores import CaseContext
from app.models import EvidenceSegment, Modality

# Optional imports for multi-modal support
try:
    import whisper
except ImportError:
    whisper = None

try:
    import pytesseract
except ImportError:
    pytesseract = None

try:
    import ffmpeg
except ImportError:
    ffmpeg = None

try:
    from pdf2image import convert_from_path
except ImportError:
    convert_from_path = None

class Conversion:
    def __init__(self, case_context: CaseContext):
        self.case_context = case_context
        self._whisper_model = None

    def _get_whisper_model(self):
        if not self._whisper_model and whisper:
            # Using 'tiny' for this environment/stub purposes.
            # In prod, config should dictate model size.
            try:
                self._whisper_model = whisper.load_model("tiny")
            except Exception as e:
                print(f"Failed to load Whisper model: {e}")
        return self._whisper_model

    def ingest_pdf_layout(self, file_path: str, source_asset_id: str) -> List[EvidenceSegment]:
        segments = []
        try:
            with pdfplumber.open(file_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    if text and len(text.strip()) > 50:
                        segment = EvidenceSegment(
                            segment_id=str(uuid.uuid4()),
                            source_asset_id=source_asset_id,
                            modality=Modality.PDF_TEXT,
                            location=f"page_{i+1}",
                            text=text,
                            confidence=1.0,
                            extraction_method="pdfplumber",
                            derived=False,
                            warnings=[]
                        )
                        segments.append(segment)
                        self.case_context.ledger.append_segment(segment)
                    else:
                        # Fallback to OCR for this page if possible
                        # Extract single page as image?
                        # pdf2image converts whole PDF or ranges.
                        # For simplicity/efficiency, we might just mark for OCR or do it here.
                        # Calling internal helper
                        ocr_segments = self._ocr_page_fallback(file_path, i+1, source_asset_id)
                        segments.extend(ocr_segments)

                    # Basic table extraction (can be improved)
                    tables = page.extract_tables()
                    for table in tables:
                        table_text = self._table_to_markdown(table)
                        if table_text:
                            segment = EvidenceSegment(
                                segment_id=str(uuid.uuid4()),
                                source_asset_id=source_asset_id,
                                modality=Modality.PDF_TABLE,
                                location=f"page_{i+1}_table",
                                text=table_text,
                                confidence=1.0,
                                extraction_method="pdfplumber_table",
                                derived=False,
                                warnings=[]
                            )
                            segments.append(segment)
                            self.case_context.ledger.append_segment(segment)

        except Exception as e:
            print(f"Error processing PDF {file_path}: {e}")
            # Should log to audit log
        return segments

    def ingest_docx(self, file_path: str, source_asset_id: str) -> List[EvidenceSegment]:
        segments = []
        try:
            doc = docx.Document(file_path)
            full_text = []
            for para in doc.paragraphs:
                if para.text.strip():
                    full_text.append(para.text)

            text = "\n".join(full_text)
            if text:
                segment = EvidenceSegment(
                    segment_id=str(uuid.uuid4()),
                    source_asset_id=source_asset_id,
                    modality=Modality.PDF_TEXT, # Using PDF_TEXT as generic text for now or add DOCX_TEXT
                    location="full_doc", # DOCX doesn't have reliable pagination
                    text=text,
                    confidence=1.0,
                    extraction_method="python-docx",
                    derived=False,
                    warnings=[]
                )
                segments.append(segment)
                self.case_context.ledger.append_segment(segment)

        except Exception as e:
            print(f"Error processing DOCX {file_path}: {e}")
        return segments

    def ingest_audio(self, file_path: str, source_asset_id: str, modality: Modality = Modality.AUDIO_TRANSCRIPT) -> List[EvidenceSegment]:
        segments = []
        model = self._get_whisper_model()

        # Check if we can run whisper (model loaded + ffmpeg present)
        has_ffmpeg = shutil.which('ffmpeg') is not None

        if model and has_ffmpeg:
            try:
                result = model.transcribe(file_path)
                text = result["text"]

                # We could split by segments, but for simplicity here we take the whole text
                # Ideally map result['segments'] to EvidenceSegments
                for s in result.get('segments', []):
                    segment = EvidenceSegment(
                        segment_id=str(uuid.uuid4()),
                        source_asset_id=source_asset_id,
                        modality=modality,
                        location=f"{s['start']}-{s['end']}",
                        text=s['text'].strip(),
                        confidence=1.0, # Whisper doesn't give segment-level confidence easily in this API
                        extraction_method="openai-whisper-tiny",
                        derived=False,
                        warnings=[]
                    )
                    segments.append(segment)
                    self.case_context.ledger.append_segment(segment)
            except Exception as e:
                print(f"Error transcribing audio {file_path}: {e}")
                # Fallback or error segment
        else:
            # Stub/Mock behavior if tools missing
            print(f"Skipping audio transcription: ffmpeg={has_ffmpeg}, whisper={model is not None}")
            pass

        return segments

    def ingest_video(self, file_path: str, source_asset_id: str) -> List[EvidenceSegment]:
        # Reuse audio ingestion for the audio track, but override modality
        segments = self.ingest_audio(file_path, source_asset_id, modality=Modality.VIDEO_TRANSCRIPT)

        # Frame extraction would go here using ffmpeg-python
        # if ffmpeg:
        #    ... extract keyframes ...
        #    ... OCR keyframes ...

        return segments

    def ingest_image(self, file_path: str, source_asset_id: str) -> List[EvidenceSegment]:
        segments = []
        has_tesseract = shutil.which('tesseract') is not None

        if pytesseract and has_tesseract:
            try:
                image = Image.open(file_path)
                text = pytesseract.image_to_string(image)
                if text.strip():
                    segment = EvidenceSegment(
                        segment_id=str(uuid.uuid4()),
                        source_asset_id=source_asset_id,
                        modality=Modality.OCR_PRINTED, # Assuming printed text in image
                        location="image_full",
                        text=text.strip(),
                        confidence=0.8, # OCR is imperfect
                        extraction_method="tesseract",
                        derived=False,
                        warnings=["OCR used"]
                    )
                    segments.append(segment)
                    self.case_context.ledger.append_segment(segment)
            except Exception as e:
                print(f"Error processing image {file_path}: {e}")
        else:
            print("Skipping image OCR: tesseract not found")

        return segments

    def ingest_ocr_printed(self, file_path: str, source_asset_id: str) -> List[EvidenceSegment]:
        # Explicit OCR ingestion for a file (PDF or Image)
        # Convert PDF to images -> OCR
        segments = []
        if not convert_from_path or not pytesseract or shutil.which("tesseract") is None:
            print("OCR tools missing")
            return segments

        try:
            images = convert_from_path(file_path)
            for i, image in enumerate(images):
                text = pytesseract.image_to_string(image)
                if text.strip():
                    segment = EvidenceSegment(
                        segment_id=str(uuid.uuid4()),
                        source_asset_id=source_asset_id,
                        modality=Modality.OCR_PRINTED,
                        location=f"page_{i+1}",
                        text=text.strip(),
                        confidence=0.85,
                        extraction_method="tesseract",
                        derived=False,
                        warnings=["Scanned Document OCR"]
                    )
                    segments.append(segment)
                    self.case_context.ledger.append_segment(segment)
        except Exception as e:
            print(f"OCR failed for {file_path}: {e}")

        return segments

    def _ocr_page_fallback(self, file_path: str, page_num: int, source_asset_id: str) -> List[EvidenceSegment]:
        # Helper to OCR a specific page.
        # pdf2image is efficient enough to get one page
        segments = []
        if not convert_from_path or not pytesseract or shutil.which("tesseract") is None:
            return segments

        try:
            # pdf2image uses 1-based indexing for first_page/last_page
            images = convert_from_path(file_path, first_page=page_num, last_page=page_num)
            if images:
                text = pytesseract.image_to_string(images[0])
                if text.strip():
                    segment = EvidenceSegment(
                        segment_id=str(uuid.uuid4()),
                        source_asset_id=source_asset_id,
                        modality=Modality.OCR_PRINTED,
                        location=f"page_{page_num}",
                        text=text.strip(),
                        confidence=0.8,
                        extraction_method="pdf_fallback_ocr",
                        derived=False,
                        warnings=["Fallback OCR used"]
                    )
                    segments.append(segment)
                    self.case_context.ledger.append_segment(segment)
        except Exception as e:
            print(f"Fallback OCR failed for page {page_num}: {e}")
        return segments

    def ingest_handwriting(self, file_path: str, source_asset_id: str):
        # Requires Vision LLM. Stub for now.
        # Create a placeholder segment to simulate flow
        segment = EvidenceSegment(
            segment_id=str(uuid.uuid4()),
            source_asset_id=source_asset_id,
            modality=Modality.HANDWRITING_OCR,
            location="page_1",
            text="[Handwriting extraction stub]",
            confidence=0.5,
            extraction_method="vision-llm-stub",
            derived=False,
            warnings=["Low confidence stub"]
        )
        self.case_context.ledger.append_segment(segment)
        return [segment]

    def _table_to_markdown(self, table: List[List[str]]) -> str:
        if not table:
            return ""
        # Handle None values in cells
        cleaned_table = [[cell if cell is not None else "" for cell in row] for row in table]

        # Simple markdown table generator
        if not cleaned_table:
            return ""
        header = cleaned_table[0]
        rows = cleaned_table[1:]

        md = "| " + " | ".join(header) + " |\n"
        md += "| " + " | ".join(["---"] * len(header)) + " |\n"
        for row in rows:
            md += "| " + " | ".join(row) + " |\n"
        return md
