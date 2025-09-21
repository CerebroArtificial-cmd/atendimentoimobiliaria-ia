este mínimo para iniciar o app Streamlit sem checagens extras.

Uso:
  python teste_minimo.py [--port 8501] [--headless]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--port", type=int, default=8501, help="Porta do servidor Streamlit")
    parser.add_argument("--headless", action="store_true", help="Executa sem abrir o navegador")
    args = parser.parse_args()

    # Verifica rapidamente se o Streamlit está disponível
    if shutil.which("streamlit") is None:
        try:
            __import__("streamlit")
        except Exception:
            print("Streamlit não encontrado. Instale com: pip install -r requirements.txt")
            return 1

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "aplicativo_imobiliaria.py",
        "--server.port",
        str(args.port),
    ]
    if args.headless:
        cmd += ["--server.headless", "true"]

    print("Executando:", " ".join(cmd))
    try:
        return subprocess.call(cmd)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())




