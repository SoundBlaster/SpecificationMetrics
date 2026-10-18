"""Conservative static local-import closure plus installed validation runtimes."""
import ast
import hashlib
import importlib
import importlib.metadata
import sys
from pathlib import Path


def local_closure(root, seeds):
    def candidates(name):
        parts = name.split('.') if name else []
        paths = [root.joinpath(*parts[:i], '__init__.py') for i in range(1, len(parts) + 1)]
        if parts:
            paths.append(root.joinpath(*parts).with_suffix('.py'))
        return [p for p in paths if p.is_file()]

    pending, seen = list(seeds), set()
    while pending:
        path = pending.pop()
        if path in seen:
            continue
        seen.add(path)
        package = path.parent.relative_to(root).parts
        for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                prefix = package[:len(package) - node.level + 1] if node.level else ()
                base = '.'.join((*prefix, node.module)) if node.module else '.'.join(prefix)
                names = [base] + ['.'.join(filter(None, (base, alias.name))) for alias in node.names]
            for name in names:
                pending.extend(candidates(name))
    return sorted(seen)


def producer_inventory(root):
    paths = local_closure(root, [root / 'adapt_retrieval_facts_v1.py'])
    result = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    result['@runtime/python'] = hashlib.sha256(sys.version.encode()).hexdigest()
    for name, distribution in (
            ('specification_core', 'specification-core'), ('pydantic', 'pydantic'),
            ('pydantic_core', 'pydantic-core'), ('typing_extensions', 'typing-extensions'),
            ('typing_inspection', 'typing-inspection'), ('annotated_types', 'annotated-types')):
        module = importlib.import_module(name)
        origin = Path(module.__file__).resolve()
        sources = (sorted(p for p in origin.parent.rglob('*')
                          if p.is_file() and p.suffix in ('.py', '.so', '.pyd', '.dylib'))
                   if hasattr(module, '__path__') else [origin])
        for path in sources:
            key = '@dependency/' + name + '/' + str(path.relative_to(origin.parent))
            result[key] = hashlib.sha256(path.read_bytes()).hexdigest()
        result['@distribution/' + distribution] = hashlib.sha256(
            importlib.metadata.version(distribution).encode()).hexdigest()
    return dict(sorted(result.items()))
