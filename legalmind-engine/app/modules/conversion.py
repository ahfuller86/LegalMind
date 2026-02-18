import uuid
import pdfplumber
import docx
from typing import List, Optional
from app.core.stores import CaseContext
from app.models import EvidenceSegment, Modality

class Conversion:
    def __init__(self, case_context: CaseContext):
        self.case_context = case_context

    def ingest_pdf_layout(self, file_path: str, source_asset_id: str) -> List[EvidenceSegment]:
        segments = []
        try:
            with pdfplumber.open(file_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    if text:
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

    # Stubs for other modalities
    def ingest_ocr_printed(self, file_path: str): pass
    def ingest_handwriting(self, file_path: str): pass
    def ingest_audio(self, file_path: str): pass
    def ingest_video(self, file_path: str): pass
    def ingest_image(self, file_path: str): pass
