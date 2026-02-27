import sys
import unittest
from unittest.mock import MagicMock, Mock, patch

class TestSentinel(unittest.TestCase):
    def setUp(self):
        # Create a mock for pydantic
        self.mock_pydantic = MagicMock()

        # Define a MockBaseModel that behaves enough like Pydantic's BaseModel
        class MockBaseModel:
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)

            def model_dump_json(self):
                import json
                return json.dumps(self.__dict__, default=str)

            def dict(self):
                return self.__dict__

        self.mock_pydantic.BaseModel = MockBaseModel
        self.mock_pydantic.Field = lambda *args, **kwargs: None

        # Start patching sys.modules
        self.modules_patcher = patch.dict(sys.modules, {"pydantic": self.mock_pydantic})
        self.modules_patcher.start()

        # Remove modules from cache to force re-import with mocked pydantic
        # We need to remove any module that imports pydantic or app.models
        modules_to_remove = ["app.models", "app.modules.sentinel", "app.core.stores"]
        for mod in modules_to_remove:
            if mod in sys.modules:
                del sys.modules[mod]

        # Now import the modules
        import app.modules.sentinel
        import app.models

        self.sentinel_module = app.modules.sentinel
        self.models_module = app.models

        self.mock_context = Mock()
        self.sentinel = self.sentinel_module.Sentinel(self.mock_context)

    def tearDown(self):
        self.modules_patcher.stop()
        # Clean up modules to avoid polluting other tests
        # (Though patch.dict might handle restoring sys.modules, it doesn't un-import modules that were imported during the patch if they weren't there before.
        # But for safety, we can leave it or clear them.)
        pass

    def create_citation_finding(self, status):
        return self.models_module.CitationFinding(
            citation_text="Test v. Test",
            normalized_form="test v. test",
            status=status,
            confidence=1.0,
            case_details={"name": "Test v. Test", "date": "2023", "court": "Test Court", "url": "http://test.com"},
            reconciliation_notes="None",
            source_pass="local"
        )

    def create_verification_finding(self, status):
        return self.models_module.VerificationFinding(
            claim_id="claim_1",
            status=status,
            justification=self.models_module.Justification(
                elements_supported=[],
                elements_missing=[],
                contradictions=[]
            ),
            quotes_with_provenance=[],
            evidence_refs=[],
            confidence=self.models_module.ConfidenceLevel.HIGH
        )

    def test_gate_evaluator_clear(self):
        citation_findings = [self.create_citation_finding(self.models_module.CitationStatus.VERIFIED)]
        claim_findings = [self.create_verification_finding(self.models_module.VerificationStatus.SUPPORTED)]

        result = self.sentinel.gate_evaluator(claim_findings, citation_findings)

        self.assertEqual(result.filing_recommendation, self.models_module.FilingRecommendation.CLEAR)
        self.assertEqual(result.risk_score, 0.0)

    def test_gate_evaluator_citation_not_found(self):
        citation_findings = [
            self.create_citation_finding(self.models_module.CitationStatus.VERIFIED),
            self.create_citation_finding(self.models_module.CitationStatus.NOT_FOUND)
        ]
        claim_findings = [self.create_verification_finding(self.models_module.VerificationStatus.SUPPORTED)]

        result = self.sentinel.gate_evaluator(claim_findings, citation_findings)

        self.assertEqual(result.filing_recommendation, self.models_module.FilingRecommendation.DO_NOT_FILE)
        self.assertEqual(result.risk_score, 20.0)

    def test_gate_evaluator_claim_contradicted(self):
        citation_findings = [self.create_citation_finding(self.models_module.CitationStatus.VERIFIED)]
        claim_findings = [
            self.create_verification_finding(self.models_module.VerificationStatus.SUPPORTED),
            self.create_verification_finding(self.models_module.VerificationStatus.CONTRADICTED)
        ]

        result = self.sentinel.gate_evaluator(claim_findings, citation_findings)

        self.assertEqual(result.filing_recommendation, self.models_module.FilingRecommendation.REVIEW_REQUIRED)
        self.assertEqual(result.risk_score, 10.0)

    def test_gate_evaluator_high_risk(self):
        citation_findings = [self.create_citation_finding(self.models_module.CitationStatus.UNVERIFIED) for _ in range(4)]
        claim_findings = [self.create_verification_finding(self.models_module.VerificationStatus.SUPPORTED)]

        result = self.sentinel.gate_evaluator(claim_findings, citation_findings)

        self.assertEqual(result.risk_score, 20.0)
        self.assertEqual(result.filing_recommendation, self.models_module.FilingRecommendation.REVIEW_REQUIRED)

    def test_gate_evaluator_priority_citation_not_found_vs_contradicted(self):
        citation_findings = [self.create_citation_finding(self.models_module.CitationStatus.NOT_FOUND)]
        claim_findings = [self.create_verification_finding(self.models_module.VerificationStatus.CONTRADICTED)]

        result = self.sentinel.gate_evaluator(claim_findings, citation_findings)

        self.assertEqual(result.filing_recommendation, self.models_module.FilingRecommendation.DO_NOT_FILE)
        self.assertEqual(result.risk_score, 30.0)

    def test_gate_evaluator_priority_contradicted_vs_high_risk(self):
        citation_findings = [self.create_citation_finding(self.models_module.CitationStatus.VERIFIED)]
        claim_findings = [
            self.create_verification_finding(self.models_module.VerificationStatus.CONTRADICTED),
            self.create_verification_finding(self.models_module.VerificationStatus.NOT_SUPPORTED),
            self.create_verification_finding(self.models_module.VerificationStatus.NOT_SUPPORTED)
        ]

        result = self.sentinel.gate_evaluator(claim_findings, citation_findings)

        self.assertEqual(result.filing_recommendation, self.models_module.FilingRecommendation.REVIEW_REQUIRED)
        self.assertEqual(result.risk_score, 20.0)

    def test_risk_score_capping(self):
        citation_findings = [self.create_citation_finding(self.models_module.CitationStatus.NOT_FOUND) for _ in range(6)]
        claim_findings = []

        result = self.sentinel.gate_evaluator(claim_findings, citation_findings)

        self.assertEqual(result.risk_score, 100.0)

if __name__ == '__main__':
    unittest.main()
