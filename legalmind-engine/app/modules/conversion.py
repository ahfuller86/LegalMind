import uuid
import pdfplumber
import docx
import shutil
import os
import mimetypes
from typing import List, Optional
from PIL import Image
from app.core.stores import CaseContext
from app.core.config import load_config
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

class WhisperModelManager:
    _instance = None
    _model = None
    _model_name = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = WhisperModelManager()
        return cls._instance

    def get_model(self, model_name: str = None):
        if not whisper:
            return None

        config = load_config()
        target_model = model_name or config.WHISPER_MODEL_FAST

        # Load if not loaded or if requested model differs from loaded one
        if self._model is None or self._model_name != target_model:
            print(f"Loading Whisper model: {target_model}...")
            # Unload previous model if needed
            if self._model:
                del self._model
                import gc
                gc.collect()

            try:
                self._model = whisper.load_model(target_model)
                self._model_name = target_model
            except Exception as e:
                print(f"Failed to load Whisper model {target_model}: {e}")
                return None

        return self._model

class Conversion:
    def __init__(self, case_context: CaseContext):
        self.case_context = case_context

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
        config = load_config()
        manager = WhisperModelManager.get_instance()
        model = manager.get_model(config.WHISPER_MODEL_FAST)

        # Check if we can run whisper (model loaded + ffmpeg present)
        has_ffmpeg = shutil.which('ffmpeg') is not None

        if model and has_ffmpeg:
            try:
                result = model.transcribe(file_path)

                # Ideally map result['segments'] to EvidenceSegments
                for s in result.get('segments', []):
                    segment = EvidenceSegment(
                        segment_id=str(uuid.uuid4()),
                        source_asset_id=source_asset_id,
                        modality=modality,
                        location=f"{s['start']}-{s['end']}",
                        text=s['text'].strip(),
                        confidence=1.0, # Whisper doesn't give segment-level confidence easily in this API
                        extraction_method=f"openai-whisper-{config.WHISPER_MODEL_FAST}",
                        derived=False,
                        warnings=[],
                        metadata={
                            "transcription_quality": "draft",
                            "model": config.WHISPER_MODEL_FAST,
                            "timestamp_start": s['start'],
                            "timestamp_end": s['end']
                        }
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

    def refine_transcription(self, segment: EvidenceSegment) -> EvidenceSegment:
        """
        Refines the transcription of a segment using the accurate model.
        """
        config = load_config()

        # Identify source file from vault
        file_path = os.path.join(self.case_context.vault.vault_path, segment.source_asset_id)
        if not os.path.exists(file_path):
            segment.warnings.append("Refinement failed: Source file not found")
            return segment

        manager = WhisperModelManager.get_instance()
        model = manager.get_model(config.WHISPER_MODEL_ACCURATE)

        if not model:
            segment.warnings.append("Refinement failed: Model not loaded")
            return segment

        try:
            # We need to transcribe only the segment or the whole file and find the segment?
            # Whisper transcribes the whole file.
            # Ideally we extract the clip using ffmpeg-python.
            # For simplicity in this engine, we re-transcribe the whole file and find the matching segment based on timestamps?
            # That is inefficient for a single segment, but acceptable if we batch or if file is small.
            # OPTIMIZATION: Extract audio clip for the specific duration.

            # Since segment has start/end in metadata (if ingested by new logic) or location
            start = segment.metadata.get("timestamp_start")
            duration = None
            if start is not None:
                end = segment.metadata.get("timestamp_end")
                if end:
                    duration = end - start

            # If we don't have timestamps (legacy), fallback to full re-transcription logic or skip
            # Assuming we only refine "draft" segments which have this metadata.

            # However, Whisper takes file path. We can't easily tell it to start at X.
            # We must use ffmpeg to trim.
            if not ffmpeg:
                segment.warnings.append("Refinement failed: ffmpeg-python not installed")
                return segment

            temp_clip = f"/tmp/{segment.segment_id}.wav"

            if start is not None and duration:
                try:
                    (
                        ffmpeg
                        .input(file_path, ss=start, t=duration)
                        .output(temp_clip)
                        .run(quiet=True, overwrite_output=True)
                    )
                    transcribe_path = temp_clip
                except ffmpeg.Error as e:
                    print(f"ffmpeg error: {e.stderr.decode() if e.stderr else str(e)}")
                    # Fallback to full file? No, that's too heavy for one segment.
                    segment.warnings.append("Refinement failed: ffmpeg processing error")
                    return segment
            else:
                transcribe_path = file_path

            result = model.transcribe(transcribe_path)
            new_text = result["text"].strip()

            segment.text = new_text
            segment.metadata["transcription_quality"] = "final"
            segment.metadata["model"] = config.WHISPER_MODEL_ACCURATE
            segment.extraction_method = f"openai-whisper-{config.WHISPER_MODEL_ACCURATE}"

            if os.path.exists(temp_clip):
                os.remove(temp_clip)

        except Exception as e:
            print(f"Refinement failed: {e}")
            segment.warnings.append(f"Refinement error: {str(e)}")

        return segment

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
