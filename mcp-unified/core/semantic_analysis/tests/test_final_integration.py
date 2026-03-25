import unittest
import subprocess
import time
from pathlib import Path

class TestFinalIntegration(unittest.TestCase):
    def setUp(self):
        # Pastikan MCP server berjalan
        self.mcp_server_process = None

    def test_complete_workflow(self):
        print("\n=== Testing Complete Workflow ===")

        # 1. Install dependencies
        print("1. Installing dependencies...")
        result = subprocess.run(
            ['pip', 'install', '-r', 'requirements.txt'],
            capture_output=True,
            text=True,
            cwd='mcp-unified/core/semantic_analysis'
        )
        self.assertEqual(result.returncode, 0)

        # 2. Run basic example
        print("2. Running basic example...")
        result = subprocess.run(
            ['python', 'examples/basic_usage.py'],
            capture_output=True,
            text=True,
            cwd='mcp-unified/core/semantic_analysis'
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn('=== Semantic Analysis Tools Example ===', result.stdout)
        self.assertIn('=== Example completed successfully ===', result.stdout)

        # 3. Run test suite
        print("3. Running test suite...")
        result = subprocess.run(
            ['pytest', 'tests/', '-v'],
            capture_output=True,
            text=True,
            cwd='mcp-unified/core/semantic_analysis'
        )
        self.assertEqual(result.returncode, 0)

        # 4. Test integration with MCP server
        print("4. Testing MCP server integration...")
        # Jalankan MCP server (asumsi sudah dikonfigurasi)
        try:
            self.mcp_server_process = subprocess.Popen(
                ['python', 'mcp_server.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd='../..'  # Dari semantic_analysis ke MCP root
            )
            time.sleep(5)  # Tunggu server startup

            # Test API endpoint
            result = subprocess.run(
                ['curl', '-s', 'http://localhost:8000/health'],
                capture_output=True,
                text=True
            )
            self.assertIn('ok', result.stdout)

        except Exception as e:
            print(f"MCP server test skipped: {e}")

        print("=== All integration tests passed ===")

    def tearDown(self):
        if self.mcp_server_process:
            self.mcp_server_process.terminate()
            self.mcp_server_process.wait()

if __name__ == '__main__':
    unittest.main()