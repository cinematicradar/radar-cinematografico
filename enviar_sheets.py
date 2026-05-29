import os
import glob
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests


PASTA_RESULTADOS = "resultados"


def encontrar_csv_mais_recente():
    arquivos = glob.glob(os.path.join(PASTA_RESULTADOS, "*.csv"))

    if not arquivos:
        raise FileNotFoundError("Nenhum arquivo CSV foi encontrado dentro da pasta resultados/")

    arquivos.sort(key=os.path.getmtime, reverse=True)
    return arquivos[0]


def carregar_csv(csv_path):
    print(f"Lendo arquivo CSV: {csv_path}")

    df = pd.read_csv(csv_path, sep=None, engine="python")
    df = df.fillna("")

    agora = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%Y-%m-%d %H:%M:%S")

    df["data_envio_sheets"] = agora
    df["arquivo_origem"] = os.path.basename(csv_path)
    df["github_run_url"] = os.environ.get("GITHUB_RUN_URL", "")

    return df


def enviar_para_apps_script(df):
    webhook_url = os.environ.get("RADAR_WEBHOOK_URL")
    token = os.environ.get("RADAR_TOKEN")

    if not webhook_url:
        raise ValueError("Secret RADAR_WEBHOOK_URL não encontrado.")

    if not token:
        raise ValueError("Secret RADAR_TOKEN não encontrado.")

    registros = df.astype(str).to_dict(orient="records")

    payload = {
        "token": token,
        "registros": registros
    }

    print(f"Enviando {len(registros)} registros para o Google Sheets...")

    resposta = requests.post(
        webhook_url,
        json=payload,
        timeout=60
    )

    print("Status da resposta:", resposta.status_code)
    print("Resposta:", resposta.text)

    if resposta.status_code not in [200, 201, 302]:
        raise RuntimeError("Erro ao enviar dados para o Google Sheets.")

    print("Dados enviados com sucesso para o Google Sheets.")


def main():
    csv_path = encontrar_csv_mais_recente()
    df = carregar_csv(csv_path)
    enviar_para_apps_script(df)


if __name__ == "__main__":
    main()
