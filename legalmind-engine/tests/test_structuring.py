import sys
from unittest.mock import MagicMock
import os

# Mock dependencies to allow importing Structuring without missing packages
sys.modules['app.core.stores'] = MagicMock()
sys.modules['app.models'] = MagicMock()

import unittest

# Ensure the app directory is in the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.modules.structuring import Structuring

class TestSentenceChunker(unittest.TestCase):
    def setUp(self):
        # Mocking CaseContext which is passed to Structuring.__init__
        self.mock_context = MagicMock()
        self.structuring = Structuring(case_context=self.mock_context)

    def test_basic_splitting(self):
        """Test simple sentence splitting on dots."""
        text = "This is the first sentence. This is the second sentence."
        expected = ["This is the first sentence.", "This is the second sentence."]
        self.assertEqual(self.structuring.sentence_chunker(text), expected)

    def test_legal_abbreviation_v(self):
        """Test that 'v.' does not cause a split in case names."""
        text = "The case of Smith v. Jones is often cited. It is from 1995."
        results = self.structuring.sentence_chunker(text)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0], "The case of Smith v. Jones is often cited.")

    def test_legal_abbreviation_id(self):
        """Test that 'id.' does not cause a split."""
        text = "See id. at 45. Further discussion follows."
        results = self.structuring.sentence_chunker(text)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0], "See id. at 45.")

    def test_us_citation(self):
        """Test that 'U.S.' in citations does not cause a split."""
        text = "Refer to 410 U.S. 113 for details. That is the Roe case."
        results = self.structuring.sentence_chunker(text)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0], "Refer to 410 U.S. 113 for details.")

    def test_usa_abbreviation(self):
        """Test that 'U.S.A.' does not cause a split."""
        text = "Made in the U.S.A. for the world. Next sentence."
        results = self.structuring.sentence_chunker(text)
        # This currently fails (splits at A.), but will pass after improvement
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0], "Made in the U.S.A. for the world.")

    def test_corporate_abbreviations(self):
        """Test that corporate abbreviations do not cause splits."""
        text = "Apple Inc. released a new product. Microsoft Corp. followed suit."
        results = self.structuring.sentence_chunker(text)
        # This currently fails (splits at Inc. and Corp.), but will pass after improvement
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0], "Apple Inc. released a new product.")
        self.assertEqual(results[1], "Microsoft Corp. followed suit.")

    def test_multiple_punctuations(self):
        """Test question marks and exclamation points."""
        text = "Is this Smith v. Jones? Yes! Definitely."
        expected = ["Is this Smith v. Jones?", "Yes!", "Definitely."]
        self.assertEqual(self.structuring.sentence_chunker(text), expected)

    def test_newlines_and_extra_spaces(self):
        """Test handling of newlines and multiple spaces."""
        text = "First sentence.\nSecond   sentence. \nThird sentence."
        results = self.structuring.sentence_chunker(text)
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0], "First sentence.")
        # Note: current implementation does not collapse internal spaces
        self.assertIn("Second", results[1])
        self.assertIn("sentence.", results[1])

    def test_all_protected_abbreviations(self):
        """Test all abbreviations in the expanded list."""
        # Expanded list includes: u.s.a, u.s, v, id, no, see, cf, e.g, i.e, ref, inc, corp, ltd, stat, fed, supp, ex, viz, vol, p, pp
        abbrs = ["u.s.a.", "u.s.", "v.", "id.", "no.", "see.", "cf.", "e.g.", "i.e.", "ref.", "inc.", "corp.", "ltd.", "stat.", "fed.", "supp.", "ex.", "viz.", "vol.", "p.", "pp."]
        for abbr in abbrs:
            text = f"Test with {abbr} abbreviation here. Next sentence."
            results = self.structuring.sentence_chunker(text)
            self.assertEqual(len(results), 2, f"Failed for {abbr}")
            self.assertEqual(results[1], "Next sentence.")

if __name__ == '__main__':
    unittest.main()
