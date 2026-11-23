"""
platform/ — mundo plataforma admin del monorepo.

Este directorio se llama 'platform', igual que el módulo stdlib de Python.
Para evitar que Django falle con ImportError al hacer
`from platform import python_implementation`, cargamos el módulo stdlib
directamente desde su ruta en disco y re-exportamos sus atributos públicos.
"""
import os as _os
import sys as _sys
import importlib.util as _importlib_util


def _load_stdlib_platform():
    _this_dir = _os.path.realpath(_os.path.dirname(_os.path.abspath(__file__)))
    for _path in _sys.path:
        if not _path:
            continue
        _resolved = _os.path.realpath(_path)
        if _resolved == _this_dir:
            continue
        _candidate = _os.path.join(_path, "platform.py")
        if _os.path.isfile(_candidate):
            _spec = _importlib_util.spec_from_file_location("_stdlib_platform", _candidate)
            _mod = _importlib_util.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
            return _mod
    return None


_stdlib = _load_stdlib_platform()
if _stdlib is not None:
    globals().update({k: v for k, v in vars(_stdlib).items() if not k.startswith("__")})
