cript auxiliar para executar o app Streamlit com checagens básicas.

Uso:
  python teste.py [--port 8501] [--headless]

Exemplos:
  python teste.py
  python teste.py --port 8502 --headless
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def _check_prereqs() -> list[str]:
    problemas: list[str] = []

    if not Path("aplicativo_imobiliaria.py").exists():
        problemas.append("Arquivo 'aplicativo_imobiliaria.py' não encontrado na pasta atual.")

    # Verifica se Streamlit está instalado
    if shutil.which("streamlit") is None:
        # Tenta ao menos importar pelo módulo
        try:
            __import__("streamlit")
        except Exception:
            problemas.append(
                "Pacote 'streamlit' não está instalado. Rode: pip install -r requirements.txt"
            )

    # Aviso sobre secrets (opcional)
    secrets_path = Path(".streamlit/secrets.toml")
    if not secrets_path.exists():
        # Apenas aviso; o app pode rodar sem OpenAI/Sheets
        problemas.append(
            "Aviso: '.streamlit/secrets.toml' não encontrado. Recursos opcionais (OpenAI/Sheets) podem ficar inativos."
        )

    return problemas


def main() -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--port", type=int, default=8501, help="Porta do servidor Streamlit")
    parser.add_argument(
        "--headless", action="store_true", help="Executa em modo headless (não abre navegador)"
    )
    args, unknown = parser.parse_known_args()

    problemas = _check_prereqs()
    for p in problemas:
        # Imprime cada problema/aviso em sua própria linha
        print(f"[verificação] {p}")

    # Monta o comando do Streamlit via módulo para portabilidade
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

    # Encaminha argumentos extras desconhecidos diretamente ao Streamlit
    if unknown:
        cmd += unknown

    print("[execução] ", " ".join(cmd))
    try:
        return subprocess.call(cmd)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())


