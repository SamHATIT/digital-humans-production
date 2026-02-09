"""
Static code analysis for generated Apex and LWC code.
Runs PMD/ESLint, parses results, feeds back to agents for auto-correction.
"""
import subprocess
import json
import tempfile
import logging
from pathlib import Path
from typing import List, Dict

logger = logging.getLogger(__name__)
MAX_FIX_ITERATIONS = 3


class CodeAnalysisService:
    PMD_RULESET = Path(__file__).parent.parent.parent / "data" / "pmd-apex-rules.xml"
    ESLINT_CONFIG = Path(__file__).parent.parent.parent / "data" / ".eslintrc.json"

    def analyze_apex(self, code: str, filename: str = "Generated.cls") -> List[Dict]:
        """Run PMD on Apex code, return list of violations."""
        with tempfile.NamedTemporaryFile(suffix=".cls", mode='w', delete=False) as f:
            f.write(code)
            f.flush()
            try:
                result = subprocess.run(
                    ["pmd", "check", "-d", f.name, "-R", str(self.PMD_RULESET),
                     "-f", "json", "--no-cache"],
                    capture_output=True, text=True, timeout=30
                )
                if result.stdout:
                    data = json.loads(result.stdout)
                    return [
                        {
                            "rule": v.get("rule"),
                            "message": v.get("description"),
                            "line": v.get("beginline"),
                            "priority": v.get("priority"),
                        }
                        for f_data in data.get("files", [])
                        for v in f_data.get("violations", [])
                    ]
                return []
            except subprocess.TimeoutExpired:
                logger.warning(f"PMD timeout on {filename}")
                return []
            except Exception as e:
                logger.error(f"PMD error: {e}")
                return []

    def analyze_lwc(self, code: str, filename: str = "component.js") -> List[Dict]:
        """Run ESLint on LWC code, return list of issues."""
        with tempfile.NamedTemporaryFile(suffix=".js", mode='w', delete=False) as f:
            f.write(code)
            f.flush()
            try:
                result = subprocess.run(
                    ["eslint", f.name, "-f", "json",
                     "-c", str(self.ESLINT_CONFIG)],
                    capture_output=True, text=True, timeout=30
                )
                if result.stdout:
                    data = json.loads(result.stdout)
                    return [
                        {
                            "rule": m.get("ruleId"),
                            "message": m.get("message"),
                            "line": m.get("line"),
                            "severity": m.get("severity"),
                        }
                        for file_result in data
                        for m in file_result.get("messages", [])
                    ]
                return []
            except Exception as e:
                logger.error(f"ESLint error: {e}")
                return []

    def build_fix_prompt(self, code: str, violations: List[Dict], language: str) -> str:
        """Build a prompt for the LLM to fix violations."""
        violation_text = "\n".join(
            f"- Line {v['line']}: [{v.get('rule', 'unknown')}] {v['message']}"
            for v in violations
        )
        return (
            f"The following {language} code has {len(violations)} static analysis violation(s):\n\n"
            f"```{language}\n{code}\n```\n\n"
            f"Violations:\n{violation_text}\n\n"
            f"Fix ALL violations while preserving the original functionality. "
            f"Return ONLY the corrected code, no explanations."
        )
