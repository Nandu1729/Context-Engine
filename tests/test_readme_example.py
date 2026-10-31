"""The README quick example runs offline and shows what it claims."""

import re
from pathlib import Path

README = Path(__file__).resolve().parents[1] / "README.md"


def test_readme_quick_example_fits_budget_and_retrieves_answer():
    code = re.search(r"## Quick example\n\n```python\n(.*?)```", README.read_text(), re.S)
    assert code, "README quick example block not found"
    namespace = {}
    exec(compile(code.group(1), "README.md", "exec"), namespace)
    result = namespace["result"]
    assert result.diagnostics.estimate.estimated_tokens <= result.diagnostics.input_allowance
    assert "t42" in result.diagnostics.retrieved_turn_ids
    assert "D-42" in "".join(m["content"] for m in namespace["messages"])
