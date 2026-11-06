"""Dois casos novos de 06/11/2026: "Matematicamente impossível" e "A câmera coberta".

    venv/bin/python -m tools.migracoes.2026-11-06-casos-novos <pasta-dos-reels>      (de app/)

A pasta tem `<id>.info.json` e `<id>.jpg` de cada reel (yt-dlp) e
`camera-print.webp`, o print do post do TSE. Acrescenta ao `casos_videos.json`
os dois vídeos, as fontes e os totais por estado de 2026 e 2022 que os cartões
usam (soma das seções, `apuracao/cache/secoes_*.pkl`), e grava as capas.

Se `2026-10-30-casos-videos.py` for rodado de novo, ele reescreve o JSON inteiro:
rode este depois dele.
"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import numpy as np
from PIL import Image

RAIZ = Path(__file__).resolve().parents[2]
ARQ = RAIZ / "apuracao" / "data" / "arquivo" / "2026-2t"
CAPAS = RAIZ / "static" / "casos"
CAMPOS = ("l1", "f1", "t1", "bn1", "c1", "l2", "f2", "bn2", "c2")
VIDEOS = {"impossivel": "DfYSliYJ28X", "camera-coberta": "DfYL8VJOLR1"}
UFS_2026 = ("go", "sp", "rj", "sc", "rr", "ac", "pe")
UFS_2022 = ("pi", "ce")
FONTES = {
    "nd_flavio": {"rot": "ND Mais", "url": "https://ndmais.com.br/politica/flavio-bolsonaro-questiona-resultado-urnas-crescimento-lula-sc/"},
    "tse_camera": {"rot": "Justiça Eleitoral, Fato ou Boato", "url": "https://www.justicaeleitoral.jus.br/fato-ou-boato/checagens"},
    "manual_2026": {"rot": "Manual do Mesário 2026, p. 12", "url": "https://mesario.tre-rn.jus.br/wp-content/uploads/sites/6/2026/07/Manual-do-Mesario-2026-web.pdf"},
}


def por_uf(arquivo: str, ufs: tuple[str, ...]) -> dict:
    t = pickle.load(open(RAIZ / "apuracao" / "cache" / arquivo, "rb"))
    A = t["A"].astype(np.int64)
    uf = np.array([c[0] for c in t["chaves"]])
    return {u: dict(zip(CAMPOS, map(int, A[uf == u][:, :9].sum(0)))) for u in ufs}


def capa_3x4(im: Image.Image, destino: Path) -> None:
    im.convert("RGB").resize((360, 480), Image.LANCZOS).save(destino, quality=82, optimize=True)


def main(pasta: Path) -> None:
    d = json.loads((ARQ / "casos_videos.json").read_text())
    for caso, rid in VIDEOS.items():
        info = json.loads((pasta / f"{rid}.info.json").read_text())
        d["videos"][caso] = {"url": info["webpage_url"], "perfil": info["channel"],
                             "curtidas": info["like_count"], "comentarios": info["comment_count"],
                             "capa": f"/static/casos/{caso}.jpg"}
    d["fontes"].update(FONTES)
    d["dados"]["ufs"] = por_uf("secoes_2026.pkl", UFS_2026)
    d["dados"]["ufs_2022"] = por_uf("secoes_2022.pkl", UFS_2022)
    (ARQ / "casos_videos.json").write_text(json.dumps(d, ensure_ascii=False, indent=1))

    # Quadro do reel, 3:4, sem a legenda; e, do print do post do TSE, a imagem
    # da seção com o homem junto à parede (o reel só repete o print, menor).
    im = Image.open(pasta / "DfYSliYJ28X.jpg")
    w, h = im.size
    nw = int(h * 3 / 4)
    capa_3x4(im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h)), CAPAS / "impossivel.jpg")
    capa_3x4(Image.open(pasta / "camera-print.webp").crop((468, 250, 674, 525)), CAPAS / "camera-coberta.jpg")
    print(json.dumps(d["dados"]["ufs"]["go"]), d["videos"]["impossivel"])


if __name__ == "__main__":
    main(Path(sys.argv[1]))
