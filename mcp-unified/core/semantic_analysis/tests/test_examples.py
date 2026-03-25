import unittest
import subprocess
from pathlib import Path

class TestExamples(unittest.TestCase):
    def test_basic_usage_example(self):
        result = subprocess.run(
            ['python', 'examples/basic_usage.py'],
            capture_output=True,
            text=True
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn('=== Semantic Analysis Tools Example ===', result.stdout)
        self.assertIn('=== Example completed successfully ===', result.stdout)

    def test_example_file_creation(self):
        example_file = 'example.py'
        if Path(example_file).exists():
            Path(example_file).unlink()

        # Jalankan contoh untuk membuat file
        subprocess.run(['python', 'examples/basic_usage.py'], check=True)

        # Verifikasi file sudah dihapus
        self.assertFalse(Path(example_file).exists())

if __name__ == '__main__':
    unittest.main()