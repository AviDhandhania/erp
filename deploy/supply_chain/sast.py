"""Static Application Security Testing (SAST) engine for Clothing ERP Python codebase."""

import ast
import os
from pathlib import Path


class SASTVisitor(ast.NodeVisitor):
    def __init__(self, filename: str, rel_path: str):
        self.filename = filename
        self.rel_path = rel_path
        self.findings = []

    def add_finding(self, node: ast.AST, severity: str, rule: str, message: str):
        self.findings.append({
            "severity": severity,
            "rule": rule,
            "file": self.rel_path,
            "line": getattr(node, "lineno", 0),
            "message": message,
        })

    def visit_Call(self, node: ast.Call):
        # Check for eval() or exec()
        if isinstance(node.func, ast.Name):
            if node.func.id in ("eval", "exec"):
                self.add_finding(
                    node,
                    "HIGH",
                    "DYNAMIC_CODE_EXECUTION",
                    f"Use of {node.func.id}() allows arbitrary code execution.",
                )
            elif node.func.id == "mktemp":
                self.add_finding(
                    node,
                    "HIGH",
                    "INSECURE_TEMPFILE",
                    "Use of insecure tempfile.mktemp(); use tempfile.NamedTemporaryFile instead.",
                )

        # Check for subprocess calls with shell=True
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
            # os.system, os.popen
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "os":
                if func_name in ("system", "popen"):
                    self.add_finding(
                        node,
                        "HIGH",
                        "OS_COMMAND_EXECUTION",
                        f"Direct invocation of os.{func_name}() can lead to shell command injection.",
                    )

            # subprocess.Popen(..., shell=True)
            if func_name in ("Popen", "call", "run", "check_call", "check_output"):
                for keyword in node.keywords:
                    if keyword.arg == "shell":
                        if isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                            self.add_finding(
                                node,
                                "HIGH",
                                "SUBPROCESS_SHELL_TRUE",
                                f"subprocess.{func_name} invoked with shell=True creates command injection risk.",
                            )

            # yaml.load without SafeLoader
            if func_name == "load" and isinstance(node.func.value, ast.Name) and node.func.value.id == "yaml":
                has_safe_loader = False
                for keyword in node.keywords:
                    if keyword.arg == "Loader":
                        if isinstance(keyword.value, ast.Attribute) and keyword.value.attr in ("SafeLoader", "CSafeLoader"):
                            has_safe_loader = True
                if not has_safe_loader and len(node.args) == 1:
                    self.add_finding(
                        node,
                        "HIGH",
                        "UNSAFE_YAML_DESERIALIZATION",
                        "yaml.load without Loader=SafeLoader allows arbitrary object deserialization.",
                    )

            # pickle.loads
            if func_name in ("loads", "load") and isinstance(node.func.value, ast.Name) and node.func.value.id in ("pickle", "_pickle", "cPickle"):
                self.add_finding(
                    node,
                    "CRITICAL",
                    "UNSAFE_PICKLE_DESERIALIZATION",
                    f"Use of {node.func.value.id}.{func_name}() allows remote code execution via object deserialization.",
                )

        self.generic_visit(node)


def scan_file(file_path: Path, root_path: Path) -> list[dict]:
    rel_path = str(file_path.relative_to(root_path))
    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))
        visitor = SASTVisitor(str(file_path), rel_path)
        visitor.visit(tree)
        return visitor.findings
    except SyntaxError as e:
        return [{
            "severity": "LOW",
            "rule": "SYNTAX_ERROR",
            "file": rel_path,
            "line": e.lineno or 0,
            "message": f"Syntax error during AST parse: {e.msg}",
        }]
    except Exception as e:
        return [{
            "severity": "LOW",
            "rule": "PARSE_ERROR",
            "file": rel_path,
            "line": 0,
            "message": str(e),
        }]


def run_sast_scan(root_dir: str | Path, targets: list[str] | None = None) -> list[dict]:
    root = Path(root_dir).resolve()
    target_dirs = targets or ["sales_erp", "warehouse_erp", "quality_erp", "deploy"]
    findings = []

    for target in target_dirs:
        target_path = root / target
        if not target_path.exists():
            continue
        for current_dir, _, files in os.walk(target_path):
            if any(p in current_dir for p in ("tests", "__pycache__", "fixtures")):
                continue
            for file in files:
                if file.endswith(".py"):
                    file_findings = scan_file(Path(current_dir) / file, root)
                    findings.extend(file_findings)

    return findings
