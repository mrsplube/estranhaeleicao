"""Monta docs/analise-tres-papeis.md a partir de static/casos/lados.json.

    venv/bin/python app/tools/lados_md.py
"""
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
d = json.loads((RAIZ / "app/static/casos/lados.json").read_text())
ROT = {"estranho": "Verdade e estranho", "falsa": "Premissa falsa", "normal": "Verdade, mas normal"}
L = ["# Os casos em três papéis", "", d["_sobre"], "",
     "## 1. Red team: o melhor argumento de fraude", ""]
L += [f"- **{k}**: {v['fraude']}" for k, v in d["casos"].items()]
L += ["", "## 2. Defesa: a melhor resposta", ""]
L += [f"- **{k}**: {v['defesa']}" for k, v in d["casos"].items()]
L += ["", "## 3. Juiz: decisão e síntese", "", "| caso | etiqueta | decisão | síntese |", "|---|---|---|---|"]
L += [f"| {k} | {ROT[v['juiz']['tag']]} | {v['juiz']['decisao']} | {v['juiz']['sintese']} |" for k, v in d["casos"].items()]
g = d["geral"]
L += ["", "## O argumento geral contra a conferência", "", f"- **Acusação:** {g['fraude']}", f"- **Defesa:** {g['defesa']}", f"- **Decisão:** {g['juiz']}", ""]
(RAIZ / "docs/analise-tres-papeis.md").write_text("\n".join(L))
print("ok", len(d["casos"]), "casos")
