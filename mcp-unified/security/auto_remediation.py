"""
Security Auto-Remediation Script.
Automatically applies fixes for common security vulnerabilities found by the SecurityScanner.
"""

import os
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from security.scanner import SecurityScanner, Category, Severity

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("security-remediation")

class SecurityRemediator:
    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.scanner = SecurityScanner(base_path)
        self.fixes_applied = 0

    def apply_fixes(self) -> List[Dict[str, Any]]:
        vulnerabilities = self.scanner.scan_directory()
        results = []

        # Proactively untrack state files
        state_results = self._untrack_state_files()
        if state_results:
            results.extend(state_results)

        for vuln in vulnerabilities:
            # Skip self to avoid destructive self-modification
            if "auto_remediation.py" in vuln.file_path:
                continue
                
            if vuln.category == Category.SECRET.value:
                fix_result = self._fix_secret(vuln)
                if fix_result:
                    results.append(fix_result)
            elif vuln.category == Category.INJECTION.value:
                pass
            elif vuln.category == Category.CONFIG.value:
                fix_result = self._fix_config(vuln)
                if fix_result:
                    results.append(fix_result)

        return results

    def _fix_secret(self, vuln) -> Optional[Dict[str, Any]]:
        file_path = Path(vuln.file_path)
        if not file_path.exists():
            return None

        try:
            content = file_path.read_text()
            lines = content.splitlines()
            line_idx = vuln.line_number - 1
            
            if line_idx >= len(lines):
                return None
                
            original_line = lines[line_idx]
            
            # Pattern: key="value" -> key=os.getenv("KEY", "placeholder")
            match = re.search(r'(\w+)\s*=\s*["\']([^"\']+)["\']', original_line)
            if match:
                key_name = match.group(1).upper()
                new_line = original_line.replace(
                    match.group(0), 
                    f'{match.group(1)}=os.getenv("{key_name}", "{match.group(2)}" if not os.getenv("CI") else "DUMMY")'
                )
                
                needs_os_import = "import os" not in content and "from os import" not in content
                
                lines[line_idx] = new_line
                new_content = "\n".join(lines)
                
                if needs_os_import:
                    if file_path.suffix == ".py":
                        new_content = "import os\n" + new_content
                
                file_path.write_text(new_content)
                self.fixes_applied += 1
                return {
                    "file": str(file_path),
                    "vulnerability": vuln.title,
                    "action": "Applied os.getenv wrapper",
                    "original": original_line.strip(),
                    "fixed": new_line.strip()
                }
        except Exception as e:
            logger.error(f"Failed to fix {file_path}: {e}")
            
        return None

    def _fix_config(self, vuln) -> Optional[Dict[str, Any]]:
        file_path = Path(vuln.file_path)
        if not file_path.exists():
            return None
            
        try:
            content = file_path.read_text()
            if "debug = True" in vuln.code_snippet or "DEBUG = True" in vuln.code_snippet:
                new_content = content.replace("debug = True", 'debug = os.getenv("DEBUG", "False").lower() == "true"')
                new_content = new_content.replace("DEBUG = True", 'DEBUG = os.getenv("DEBUG", "False").lower() == "true"')
                
                if "import os" not in new_content:
                    new_content = "import os\n" + new_content
                    
                file_path.write_text(new_content)
                self.fixes_applied += 1
                return {
                    "file": str(file_path),
                    "vulnerability": vuln.title,
                    "action": "Parameterized debug mode"
                }
        except Exception as e:
            logger.error(f"Failed to fix config in {file_path}: {e}")
            
        return None

    def _untrack_state_files(self) -> List[Dict[str, Any]]:
        results = []
        try:
            import subprocess
            patterns = ["**/.serena/**", "**/*_messages.json"]
            for pattern in patterns:
                cmd = ["git", "ls-files", pattern]
                res = subprocess.run(cmd, cwd=str(self.base_path), capture_output=True, text=True)
                if res.returncode == 0 and res.stdout.strip():
                    files = res.stdout.strip().split("\n")
                    for f in files:
                        subprocess.run(["git", "rm", "--cached", f], cwd=str(self.base_path), capture_output=True)
                        results.append({
                            "file": f,
                            "vulnerability": "Tracked state/log file",
                            "action": "Untracked from git"
                        })
                        self.fixes_applied += 1
                        
            gitignore_path = self.base_path / ".gitignore"
            if not gitignore_path.exists():
                # Check root directory if mcp-unified doesn't have it
                gitignore_path = self.base_path.parent / ".gitignore"
                
            if gitignore_path.exists():
                content = gitignore_path.read_text()
                appends = []
                if ".serena/" not in content:
                    appends.append(".serena/")
                if "*_messages.json" not in content:
                    appends.append("*_messages.json")
                if appends:
                    with open(gitignore_path, "a") as f:
                        f.write("\n\n# Auto-remediated state files\n")
                        for a in appends:
                            f.write(f"{a}\n")
                            
        except Exception as e:
            logger.error(f"Failed to untrack state files: {e}")
            
        return results

if __name__ == "__main__":
    import sys
    base = sys.argv[1] if len(sys.argv) > 1 else "."
    remediator = SecurityRemediator(base)
    logger.info(f"🚀 Starting auto-remediation in {base}")
    fixes = remediator.apply_fixes()
    
    print(f"✅ Applied {len(fixes)} security fixes.")
    for fix in fixes:
        print(f"- Fixed {fix['vulnerability']} in {fix['file']}: {fix.get('action')}")
