import subprocess
import os

def test_dashboard_js_syntax():
    """Verify that frontend/dashboard.js contains valid JavaScript without syntax errors."""
    js_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "dashboard.js")
    assert os.path.exists(js_path), f"File not found: {js_path}"

    cmd = [
        "node",
        "-e",
        (
            "const fs = require('fs'); const vm = require('vm'); "
            "const code = fs.readFileSync(process.argv[1], 'utf8'); "
            "try { vm.runInThisContext(code); } catch(e) { "
            "if (e instanceof SyntaxError) { console.error(e); process.exit(1); } }"
        ),
        js_path
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"dashboard.js syntax error: {res.stderr}"
