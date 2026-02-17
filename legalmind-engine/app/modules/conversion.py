from app.core.stores import CaseContext
from app.models import EvidenceSegment

class Conversion:
    def __init__(self, case_context: CaseContext):
        self.case_context = case_context

    def ingest_pdf_layout(self, file_path: str):
        pass

    def ingest_ocr_printed(self, file_path: str):
        pass

    def ingest_handwriting(self, file_path: str):
        pass

    def ingest_audio(self, file_path: str):
        pass

    def ingest_video(self, file_path: str):
        pass

    def ingest_image(self, file_path: str):
        pass
