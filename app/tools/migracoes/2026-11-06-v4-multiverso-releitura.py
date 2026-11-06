"""Relê o multiverso com o REML corrigido (v2.md §8, 06/11), a partir dos valores gravados.

    venv/bin/python -m tools.migracoes.2026-11-06-v4-multiverso-releitura
"""
from __future__ import annotations

import importlib
import json
import sys
from collections import Counter

mv = importlib.import_module("tools.migracoes.2026-11-05-v2-multiverso")


def main() -> int:
    arq = mv.vt.SAIDA / "multiverso.json"
    m = json.loads(arq.read_text(encoding="utf-8"))
    principais = {k: json.loads((mv.vt.SAIDA / f"{k}.json").read_text(encoding="utf-8")) for k in mv.DISPUTAS}
    antes = Counter((v["teste"], v["leitura"]) for v in m["variacoes"])
    for v in m["variacoes"]:
        v["leitura"] = mv.ler_variacao(v["teste"], v["valores"], principais)
    print(antes, "\n", Counter((v["teste"], v["leitura"]) for v in m["variacoes"]))
    arq.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
