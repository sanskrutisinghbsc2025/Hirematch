
import unittest

from config import AppConfig
from core.models.enums import FileType
from core.services.file_validator import FileValidatorService
from core.utils.errors import (
    BatchSizeExceededError,
    FileSizeExceededError,
    FileValidationError,
    UnsupportedFileTypeError,
)


class TestFileValidation(unittest.TestCase):

    def setUp(self):
        self.config = AppConfig(
            max_resumes_per_session=100,
            max_file_size_bytes=1024 * 1024,
            max_total_upload_size_bytes=5 * 1024 * 1024,
        )
        self.validator = FileValidatorService(self.config)

    def test_detect_supported_file_types(self):
        self.assertEqual(self.validator.detect_file_type("resume.pdf"), FileType.PDF)
        self.assertEqual(self.validator.detect_file_type("RESUME.PDF"), FileType.PDF)
        self.assertEqual(self.validator.detect_file_type("cv.docx"), FileType.DOCX)
        self.assertEqual(self.validator.detect_file_type("notes.txt"), FileType.UNKNOWN)
        self.assertEqual(self.validator.detect_file_type("script.py"), FileType.UNKNOWN)

    def test_unsupported_file_type_raises_error(self):
        with self.assertRaises(UnsupportedFileTypeError):
            self.validator.validate_file("malicious.exe", size_bytes=1000)

        with self.assertRaises(UnsupportedFileTypeError):
            self.validator.validate_file("notes.txt", size_bytes=1000)

    def test_empty_file_raises_error(self):
        with self.assertRaises(FileValidationError):
            self.validator.validate_file("empty.pdf", size_bytes=0)

    def test_file_size_exceeded_raises_error(self):
        oversized = int(1.5 * 1024 * 1024)
        with self.assertRaises(FileSizeExceededError):
            self.validator.validate_file("large_resume.pdf", size_bytes=oversized)

    def test_pdf_header_validation(self):
        valid_pdf_bytes = b"%PDF-1.5 Some resume text"
        meta = self.validator.validate_file("candidate.pdf", size_bytes=len(valid_pdf_bytes), content=valid_pdf_bytes)
        self.assertEqual(meta.file_type, FileType.PDF)

        invalid_pdf_bytes = b"NOT_A_PDF content"
        with self.assertRaises(FileValidationError):
            self.validator.validate_file("corrupt.pdf", size_bytes=len(invalid_pdf_bytes), content=invalid_pdf_bytes)

    def test_docx_header_validation(self):
        valid_docx_bytes = b"PK\x03\x04 Zip container"
        meta = self.validator.validate_file("candidate.docx", size_bytes=len(valid_docx_bytes), content=valid_docx_bytes)
        self.assertEqual(meta.file_type, FileType.DOCX)

        invalid_docx_bytes = b"NOT_ZIP content"
        with self.assertRaises(FileValidationError):
            self.validator.validate_file("corrupt.docx", size_bytes=len(invalid_docx_bytes), content=invalid_docx_bytes)

    def test_batch_total_size_exceeded_raises_error(self):
        class MockFile:
            def __init__(self, size):
                self.size = size

        files = [MockFile(2 * 1024 * 1024), MockFile(2 * 1024 * 1024), MockFile(2 * 1024 * 1024)]
        with self.assertRaises(BatchSizeExceededError):
            self.validator.validate_batch(files)


if __name__ == "__main__":
    unittest.main()
