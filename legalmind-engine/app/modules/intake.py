from app.core.stores import CaseContext
from typing import Dict, Any

class Intake:
    def __init__(self, case_context: CaseContext):
        self.case_context = case_context

    def file_classifier(self, file_path: str):
        pass

    def checksum_engine(self, file_path: str):
        pass

    def integrity_checker(self, file_path: str):
        pass

    def manifest_builder(self):
        pass

    def vault_writer(self, file_path: str):
        pass
