import sys
import unittest
from unittest.mock import MagicMock, patch

class TestConversion(unittest.TestCase):
    def setUp(self):
        # Create a dictionary of mocked modules needed for import
        self.mock_modules = {
            'pdfplumber': MagicMock(),
            'docx': MagicMock(),
            'PIL': MagicMock(),
            'app.core.stores': MagicMock(),
            'app.core.config': MagicMock(),
            'app.models': MagicMock(),
            # Also mock submodules if needed, e.g. app.models.EvidenceSegment
            # But MagicMock usually handles attributes access
        }

        # Patch sys.modules for the duration of the test setup
        self.patcher = patch.dict(sys.modules, self.mock_modules)
        self.patcher.start()

        # Ensure we import a fresh version of the module using the mocks
        if 'app.modules.conversion' in sys.modules:
             del sys.modules['app.modules.conversion']

        from app.modules.conversion import Conversion
        self.ConversionClass = Conversion

        # Instantiate with None as context since we test a static-like utility method
        self.converter = self.ConversionClass(None)

    def tearDown(self):
        self.patcher.stop()

    def test_empty_table(self):
        """Test with an empty table list."""
        self.assertEqual(self.converter._table_to_markdown([]), "")

    def test_none_table(self):
        """Test with None as table."""
        self.assertEqual(self.converter._table_to_markdown(None), "")

    def test_simple_table(self):
        """Test with a simple valid table."""
        table = [
            ["Header1", "Header2"],
            ["Row1Col1", "Row1Col2"],
            ["Row2Col1", "Row2Col2"]
        ]
        expected_md = (
            "| Header1 | Header2 |\n"
            "| --- | --- |\n"
            "| Row1Col1 | Row1Col2 |\n"
            "| Row2Col1 | Row2Col2 |\n"
        )
        self.assertEqual(self.converter._table_to_markdown(table), expected_md)

    def test_table_with_none_cells(self):
        """Test table with None values in cells, should be replaced by empty string."""
        table = [
            ["Header1", "Header2"],
            ["Row1Col1", None],
            [None, "Row2Col2"]
        ]
        expected_md = (
            "| Header1 | Header2 |\n"
            "| --- | --- |\n"
            "| Row1Col1 |  |\n"
            "|  | Row2Col2 |\n"
        )
        self.assertEqual(self.converter._table_to_markdown(table), expected_md)

    def test_header_only_table(self):
        """Test table with only a header."""
        table = [["Header1", "Header2"]]
        expected_md = (
            "| Header1 | Header2 |\n"
            "| --- | --- |\n"
        )
        self.assertEqual(self.converter._table_to_markdown(table), expected_md)

    def test_varying_row_lengths(self):
        """Test table where rows have different lengths."""
        table = [
            ["Header1", "Header2"],
            ["Row1Col1"],  # shorter
            ["Row2Col1", "Row2Col2", "Row2Col3"]  # longer
        ]
        # Implementation checks for simple joining.
        expected_md = (
            "| Header1 | Header2 |\n"
            "| --- | --- |\n"
            "| Row1Col1 |\n"
            "| Row2Col1 | Row2Col2 | Row2Col3 |\n"
        )
        self.assertEqual(self.converter._table_to_markdown(table), expected_md)

    def test_special_characters(self):
        """Test table with special characters like pipes."""
        table = [
            ["Header|1", "Header2"],
            ["Row1|Col1", "Row1Col2"]
        ]
        # Implementation SHOULD escape pipes to produce valid markdown.
        expected_md = (
            "| Header\\|1 | Header2 |\n"
            "| --- | --- |\n"
            "| Row1\\|Col1 | Row1Col2 |\n"
        )
        self.assertEqual(self.converter._table_to_markdown(table), expected_md)

    def test_newlines_in_cells(self):
        """Test table with newlines in cells."""
        table = [
            ["Header1", "Header2"],
            ["Line1\nLine2", "Normal"]
        ]
        # Newlines break markdown table rows. replaced by <br>
        expected_md = (
            "| Header1 | Header2 |\n"
            "| --- | --- |\n"
            "| Line1<br>Line2 | Normal |\n"
        )
        self.assertEqual(self.converter._table_to_markdown(table), expected_md)

if __name__ == '__main__':
    unittest.main()
