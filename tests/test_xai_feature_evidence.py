import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from system.xai.engine import XAIExplanationEngine


class XaiFeatureEvidenceTests(unittest.TestCase):
    def test_explanation_includes_file_entropy_sections_and_imports(self):
        section = SimpleNamespace(
            Name=b".text\x00\x00\x00",
            SizeOfRawData=512,
            Misc_VirtualSize=768,
            Characteristics=0x20000000,
            IMAGE_SCN_MEM_EXECUTE=True,
            get_entropy=lambda: 7.5,
        )
        imported_function = SimpleNamespace(name=b"CreateRemoteThread", ordinal=None)
        import_entry = SimpleNamespace(
            dll=b"KERNEL32.dll",
            imports=[imported_function],
        )
        pe = SimpleNamespace(
            FILE_HEADER=SimpleNamespace(Machine=0x14C, NumberOfSections=1),
            OPTIONAL_HEADER=SimpleNamespace(
                Magic=0x10B,
                AddressOfEntryPoint=0x1000,
                Subsystem=3,
            ),
            sections=[section],
            DIRECTORY_ENTRY_IMPORT=[import_entry],
            close=lambda: None,
        )
        fake_pefile = SimpleNamespace(
            PE=lambda data: pe,
            PEFormatError=type("PEFormatError", (Exception,), {}),
            section_characteristics=[("IMAGE_SCN_MEM_EXECUTE", 0x20000000)],
        )

        with patch.dict(sys.modules, {"pefile": fake_pefile}):
            report = XAIExplanationEngine().analyze_file(
                "sample.exe",
                b"MZ" + b"\x00" * 100,
                [],
                0.91,
                "MALICIOUS",
            )

        evidence = {item["title"]: item["description"] for item in report["feature_evidence"]}
        self.assertIn("Data randomness:", evidence["Basic file details"])
        self.assertIn("First four bytes (file signature): 4D 5A 00 00", evidence["Basic file details"])
        self.assertIn(
            "Part .text: stored size 512 bytes; memory size 768 bytes; randomness 7.50/8.00",
            evidence["Main parts of the program (most jumbled first)"],
        )
        self.assertIn(
            "KERNEL32.dll uses: CreateRemoteThread",
            evidence["Windows components and functions this program uses (1 DLL, 1 entry)"],
        )
        self.assertIn("CreateRemoteThread", evidence["Windows functions to review"])
        self.assertTrue(any(
            item["type"] == "suspicious_imports"
            for item in report["suspicious_characteristics"]
        ))


if __name__ == "__main__":
    unittest.main()
