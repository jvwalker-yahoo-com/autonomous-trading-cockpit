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


def test_python_symtable_no_undefined_globals():
    """Verify all Python source files have zero undefined global references via symtable."""
    import builtins
    import pathlib
    import symtable

    builtin_names = set(dir(builtins)) | {"__file__", "__name__", "__doc__", "__package__", "__all__", "__annotations__"}
    root_dir = pathlib.Path(__file__).resolve().parent.parent
    undefined = []

    for p in sorted(root_dir.rglob("*.py")):
        if ".git" in p.parts or "__pycache__" in p.parts:
            continue
        code = p.read_text(encoding="utf-8", errors="replace")
        st = symtable.symtable(code, str(p), "exec")

        def check_table(t, parent_defined):
            defined = set(parent_defined)
            for s in t.get_symbols():
                if s.is_imported() or s.is_assigned() or s.is_parameter() or s.is_declared_global() or s.is_namespace():
                    defined.add(s.get_name())
            for s in t.get_symbols():
                name = s.get_name()
                if s.is_referenced() and not (s.is_local() or s.is_parameter()) and name not in defined and name not in builtin_names:
                    undefined.append(f"{p.relative_to(root_dir)}:{t.get_lineno()} undefined {name!r} in {t.get_name()}")
            for child in t.get_children():
                if t.get_type() == "class":
                    check_table(child, parent_defined | {t.get_name()})
                else:
                    check_table(child, defined)

        check_table(st, set())

    assert not undefined, "Undefined global names detected:\n" + "\n".join(undefined)

