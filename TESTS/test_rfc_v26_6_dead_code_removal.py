"""RFC V26.6 — Remocao de codigo morto que interrompia o fluxo de sinais.

`main.py:1049` continha `_gate_name = ... if callable(__builtins__.get(...))
...` — codigo morto (valor nunca consumido) que lancava AttributeError em
producao real. `__builtins__` e o MODULO `builtins` (sem `.get()`) quando o
script roda como `__main__` (exatamente como o PM2 inicia main.py), mas e um
dict comum quando o modulo e importado (exatamente como o pytest importa
main.py) — por isso a suite inteira passava sem nunca exercitar o bug real.

Estes testes: (1) provam essa diferenca de comportamento do `__builtins__`
entre execucao como `__main__` e como modulo importado, documentando a
causa raiz; (2) impedem que o padrao `__builtins__.get(` volte a aparecer
em main.py.
"""
import subprocess
import sys
import inspect


def test_builtins_dot_get_raises_when_run_as_main():
    """Reproduz o ambiente real: quando um script roda como __main__ (como
    o PM2 executa main.py), __builtins__ e o MODULO builtins — sem .get().
    Isso e exatamente o AttributeError visto em producao 3900+ vezes em
    34 minutos, sempre que uma decisao era rejeitada."""
    script = 'print(type(__builtins__).__name__); __builtins__.get("x")'
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode != 0
    assert "module" in result.stdout
    assert "AttributeError" in result.stderr
    assert "'module' object has no attribute 'get'" in result.stderr or \
           "module 'builtins' has no attribute 'get'" in result.stderr


def test_builtins_dot_get_works_when_imported_as_module():
    """Contraste: quando o MESMO codigo roda dentro de um modulo importado
    (exatamente como pytest importa main.py para os outros testes deste
    arquivo), __builtins__ e um dict e .get() funciona normalmente — por
    isso a suite completa (584/584) nunca acusou esse bug."""
    import types
    mod = types.ModuleType("_rfc_v26_6_probe")
    exec(compile('RESULT = __builtins__.get("nonexistent", "ok")', "<probe>", "exec"), mod.__dict__)
    assert mod.__dict__["RESULT"] == "ok"


def test_main_py_never_calls_get_on_builtins():
    """Guarda de regressao: main.py nao pode voltar a chamar .get() em
    __builtins__ — o padrao que causou o AttributeError em producao."""
    import main
    source = inspect.getsource(main)
    assert "__builtins__.get(" not in source


def test_gate_name_dead_variable_was_removed():
    """RFC V26.6: _gate_name era codigo morto (calculado, nunca consumido)
    e a linha inteira responsavel pelo AttributeError foi removida —
    nao substituida por outra implementacao."""
    import main
    source = inspect.getsource(main)
    assert "_gate_name" not in source


def test_rejection_recording_still_uses_reject_reason_directly():
    """Confirma que a remocao nao alterou o comportamento observavel:
    record_rejection() continua recebendo o gate a partir de
    sd.reject_reason, exatamente como antes da linha morta ser removida."""
    import main
    source = inspect.getsource(main)
    idx = source.index('filter_name=sd.reject_reason or "Desconhecido"')
    block = source[idx:idx + 500]
    assert 'gate=sd.reject_reason or "Desconhecido"' in block
