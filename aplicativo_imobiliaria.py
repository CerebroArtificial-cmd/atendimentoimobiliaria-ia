import os
import re
import time
import uuid
import hashlib
import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from typing import Optional

# Tenta importar OpenAI de forma segura (opcional)
try:
    from openai import OpenAI  # noqa: F401
except Exception:  # pacote ausente ou incompatível
    OpenAI = None  # type: ignore


# -----------------------------------------------------------------------------
# Configuração básica da página
st.set_page_config(page_title="Ayla • Assistente de Imobiliária", page_icon="🏠")

# Carrega variáveis de ambiente
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
COMPANY_NAME = os.getenv("COMPANY_NAME", "Imobiliária XYZ")
COMPANY_BLURB = os.getenv("COMPANY_BLURB", "A melhor escolha para sua casa nova!")
APP_ORIGIN = os.getenv("APP_ORIGIN", "")

# Flags de comportamento
AYLA_USE_OPENAI = (os.getenv("AYLA_USE_OPENAI", "0").strip().lower() in {"1", "true", "yes", "on"})
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Inicializa cliente OpenAI (usado apenas se AYLA_USE_OPENAI habilitado)
client = None
if AYLA_USE_OPENAI and OpenAI and OPENAI_API_KEY:
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
    except Exception:
        client = None


# Mensagem de boas-vindas
WELCOME_MSG = (
    f"Oi! Sou a **Ayla**, da **{COMPANY_NAME}**. {COMPANY_BLURB}\n\n"
    "Posso te ajudar a encontrar o seu imóvel dos sonhos, que cabe no seu bolso. Vamos começar?"
)


# Perguntas do funil de coleta
PERGUNTAS = {
    "nome": "Qual é o seu nome completo?",
    "telefone": "Informe seu telefone com DDD (11 dígitos, ex: 11987654321):",
    "email": "Qual é o seu e-mail?",
    "operacao": "Você deseja comprar ou alugar? (Digite 1 para Compra ou 2 para Aluguel)",
    "tipo_imovel": "Qual tipo de imóvel você procura? (casa, apartamento ou outro)",
    "metragem": "Qual a metragem desejada? (apenas números, ex: 80)",
    "quartos": "Quantos quartos você deseja? (apenas números)",
    "faixa_preco": "Qual a faixa de preço que você tem em mente? (pode responder livremente)",
    "urgencia": "Qual é a urgência da sua busca? (alta, media, baixa)",
}


# Validadores
def validar_nome(nome: str) -> bool:
    return len((nome or "").strip().split()) >= 2


def validar_telefone(telefone: str) -> bool:
    return re.fullmatch(r"\d{11}", telefone or "") is not None


def validar_email(email: str) -> bool:
    return re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email or "") is not None


def validar_operacao(op: str) -> bool:
    return op in ("1", "2")


def validar_tipo_imovel(tipo: str) -> bool:
    return (tipo or "").strip().lower() in ("casa", "apartamento", "outro")


def validar_numero(valor: str) -> bool:
    return (valor or "").isdigit()


def validar_urgencia(u: str) -> bool:
    return (u or "").strip().lower() in ("alta", "media", "baixa")


VALIDADORES = {
    "nome": validar_nome,
    "telefone": validar_telefone,
    "email": validar_email,
    "operacao": validar_operacao,
    "tipo_imovel": validar_tipo_imovel,
    "metragem": validar_numero,
    "quartos": validar_numero,
    "faixa_preco": lambda x: True,  # livre
    "urgencia": validar_urgencia,
}


def normalizar_campo(chave: str, valor: str):
    v = (valor or "").strip()
    if chave in {"metragem", "quartos"} and v.isdigit():
        return int(v)
    if chave in {"tipo_imovel", "urgencia"}:
        return v.lower()
    if chave == "operacao":
        return "compra" if v == "1" else "aluguel"
    return v


def _append_to_excel(path: Path, df: pd.DataFrame) -> None:
    """Anexa (ou cria) uma planilha Excel com o registro informado."""
    try:
        if path.exists():
            atual = pd.read_excel(path, engine="openpyxl")
            combinado = pd.concat([atual, df], ignore_index=True)
        else:
            combinado = df
        combinado.to_excel(path, index=False, engine="openpyxl")
    except Exception as e:
        raise e


def _append_to_csv(path: Path, df: pd.DataFrame) -> None:
    """Anexa (ou cria) um CSV com o registro informado."""
    header = not path.exists()
    df.to_csv(path, mode="a", index=False, encoding="utf-8", header=header)


def _gerar_dedup_key(lead: dict) -> str:
    """Gera uma chave de deduplicação a partir de telefone e e-mail normalizados."""
    tel_raw = str(lead.get("telefone", ""))
    tel = re.sub(r"\D+", "", tel_raw)
    tel = tel if len(tel) == 11 else ""
    email = (lead.get("email", "") or "").strip().lower()
    base = f"{tel}|{email}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def salvar_lead(lead: dict):
    """Salva o lead preferencialmente em Excel; se falhar, usa CSV.

    Retorna uma tupla (caminho_do_arquivo: Path, resultado: str),
    onde resultado ∈ {"created", "updated", "appended_csv"}.
    """
    # Campos adicionais: id, origem e UTM
    utm = st.session_state.get("utm", {}) if hasattr(st, "session_state") else {}
    lead_id = st.session_state.get("lead_id", "") if hasattr(st, "session_state") else ""

    base_campos = [
        "lead_id",
        "dedup_key",
        "criado_em",
        "app_origin",
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
    ]
    ordem = base_campos + list(PERGUNTAS.keys())

    registro = {
        "lead_id": lead_id,
        "criado_em": datetime.datetime.now().isoformat(timespec="seconds"),
        "app_origin": APP_ORIGIN,
        "utm_source": utm.get("utm_source", ""),
        "utm_medium": utm.get("utm_medium", ""),
        "utm_campaign": utm.get("utm_campaign", ""),
        "utm_term": utm.get("utm_term", ""),
        "utm_content": utm.get("utm_content", ""),
        **{k: lead.get(k, "") for k in PERGUNTAS.keys()},
    }
    # Adiciona chave de deduplicação
    registro["dedup_key"] = _gerar_dedup_key(registro)
    df = pd.DataFrame([registro])

    xlsx_path = Path("imobiliaria_leads.xlsx")
    csv_path = Path("imobiliaria_leads.csv")
    try:
        # Upsert em Excel: se já existir dedup_key, atualiza; senão, cria/anexa
        if xlsx_path.exists():
            atual = pd.read_excel(xlsx_path, engine="openpyxl")
            key = str(registro["dedup_key"])
            if "dedup_key" in atual.columns:
                mask = atual["dedup_key"].astype(str) == key
                if mask.any():
                    idx = atual.index[mask][0]
                    # Garante todas as colunas e atualiza valores
                    for col in df.columns:
                        if col not in atual.columns:
                            atual[col] = ""
                        atual.at[idx, col] = df.iloc[0][col]
                    atual.to_excel(xlsx_path, index=False, engine="openpyxl")
                    return xlsx_path, "updated"
            combinado = pd.concat([atual, df], ignore_index=True)
            combinado.to_excel(xlsx_path, index=False, engine="openpyxl")
            return xlsx_path, "created"
        else:
            df.to_excel(xlsx_path, index=False, engine="openpyxl")
            return xlsx_path, "created"
    except Exception:
        _append_to_csv(csv_path, df)
        return csv_path, "appended_csv"


def _mensagem_ai_ack_e_pergunta(chave_proxima: str) -> Optional[str]:
    """Gera uma mensagem curta e amigável com OpenAI, agradecendo e perguntando o próximo campo.

    Retorna o texto ou None em caso de indisponibilidade/erro.
    """
    if not client:
        return None
    try:
        historico = st.session_state.messages[-6:]  # limita contexto
        conversas = []
        for m in historico:
            role = m.get("role", "assistant")
            content = m.get("content", "")
            conversas.append({"role": role, "content": content})

        proxima_pergunta = PERGUNTAS[chave_proxima]
        system = (
            "Você é Ayla, uma assistente de imobiliária atenciosa e objetiva da empresa "
            f"{COMPANY_NAME}. Responda em no máximo duas frases. A primeira deve reconhecer e "
            "agradecer a resposta do cliente de forma simpática; a segunda deve fazer a próxima "
            "pergunta exatamente como fornecida: '" + proxima_pergunta + "'."
        )
        msgs = ([{"role": "system", "content": system}] + conversas)
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.3,
            messages=msgs,
        )
        texto = (resp.choices[0].message.content or "").strip()
        return texto or None
    except Exception:
        return None


def perguntar_proximo_campo():
    if st.session_state.step < len(PERGUNTAS):
        chave = list(PERGUNTAS.keys())[st.session_state.step]
        pergunta = PERGUNTAS[chave]
        # Se habilitado, tenta gerar mensagem mais conversacional com a IA
        texto_ai = _mensagem_ai_ack_e_pergunta(chave) if AYLA_USE_OPENAI else None
        conteudo = texto_ai or pergunta
        st.session_state.messages.append({"role": "assistant", "content": conteudo})
        with st.chat_message("assistant"):
            st.markdown(conteudo)
    else:
        caminho, resultado = salvar_lead(st.session_state.lead)
        msg_final = (
            "Perfeito! Seu cadastro está completo e salvo.\n\n"
            f"Arquivo: `{caminho.name}` (na pasta do app).\n\n"
            + ("Registro atualizado (deduplicado).\n\n" if resultado == "updated" else "")
            + "Em breve nossa equipe entrará em contato. "
        )
        st.session_state.messages.append({"role": "assistant", "content": msg_final})
        with st.chat_message("assistant"):
            st.markdown(msg_final)
            try:
                if caminho.suffix.lower() == ".xlsx" and caminho.exists():
                    with open(caminho, "rb") as f:
                        st.download_button(
                            label="Baixar planilha Excel",
                            data=f,
                            file_name=caminho.name,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )
                elif caminho.suffix.lower() == ".csv" and caminho.exists():
                    with open(caminho, "rb") as f:
                        st.download_button(
                            label="Baixar CSV",
                            data=f,
                            file_name=caminho.name,
                            mime="text/csv",
                        )
            except Exception:
                pass


def app():
    st.header("Atendente de Imobiliária com IA")

    # Banner opcional sobre OpenAI
    if not OPENAI_API_KEY:
        st.info("OPENAI_API_KEY não definida. O fluxo de coleta não usa OpenAI.")
    if AYLA_USE_OPENAI:
        if client is not None:
            st.sidebar.success("IA conversacional ativa (OpenAI)")
        else:
            st.sidebar.warning(
                "AYLA_USE_OPENAI habilitado, mas o cliente OpenAI não pôde ser inicializado."
            )

    # Estado inicial
    if "lead" not in st.session_state:
        st.session_state.lead = {}
        st.session_state.step = 0
        st.session_state.messages = []
        st.session_state.prev_question_timestamp = datetime.datetime.now() - datetime.timedelta(seconds=5)
        # ID único do lead
        st.session_state.lead_id = str(uuid.uuid4())
        # Captura parâmetros UTM da URL (se houver)
        try:
            qp = dict(st.query_params)
        except Exception:
            qp = {}
        st.session_state.utm = {
            "utm_source": qp.get("utm_source", ""),
            "utm_medium": qp.get("utm_medium", ""),
            "utm_campaign": qp.get("utm_campaign", ""),
            "utm_term": qp.get("utm_term", ""),
            "utm_content": qp.get("utm_content", ""),
        }

    # Exibe histórico
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Primeira vez: saudação + primeira pergunta
    if not any(m["role"] == "assistant" for m in st.session_state.messages):
        st.session_state.messages.append({"role": "assistant", "content": WELCOME_MSG})
        with st.chat_message("assistant"):
            st.markdown(WELCOME_MSG)
        perguntar_proximo_campo()

    # Sidebar: exibe ID do lead para referência
    try:
        st.sidebar.caption(f"Lead ID: {st.session_state.get('lead_id', '')}")
    except Exception:
        pass

    # Entrada do usuário
    user_message = st.chat_input("Digite sua resposta e pressione Enter...")
    if user_message:
        # Pequeno rate limit entre perguntas
        now = datetime.datetime.now()
        delta = now - st.session_state.prev_question_timestamp
        if delta < datetime.timedelta(seconds=1):
            time.sleep(1 - delta.total_seconds())
        st.session_state.prev_question_timestamp = datetime.datetime.now()

        st.session_state.messages.append({"role": "user", "content": user_message})
        with st.chat_message("user"):
            st.text(user_message)

        if st.session_state.step < len(PERGUNTAS):
            chave = list(PERGUNTAS.keys())[st.session_state.step]
            validador = VALIDADORES.get(chave, lambda x: True)
            valido = bool(validador(user_message))

            if valido:
                st.session_state.lead[chave] = normalizar_campo(chave, user_message)
                st.session_state.step += 1
                with st.chat_message("assistant"):
                    st.markdown(":white_check_mark: Entendi!")
                st.session_state.messages.append({"role": "assistant", "content": ":white_check_mark: Entendi!"})
                perguntar_proximo_campo()
            else:
                mensagens_erro = {
                    "nome": "Por favor, informe nome e sobrenome.",
                    "telefone": "Telefone deve ter 11 dígitos (DDD + número), ex.: 11987654321.",
                    "email": "Digite um e-mail válido, ex.: nome@dominio.com.",
                    "operacao": "Responda com 1 (Compra) ou 2 (Aluguel).",
                    "tipo_imovel": "Escolha entre casa, apartamento ou outro.",
                    "metragem": "Digite apenas números, ex.: 80.",
                    "quartos": "Digite apenas números, ex.: 2.",
                    "urgencia": "Responda alta, media ou baixa.",
                }
                erro = mensagens_erro.get(chave, "A resposta não é válida. Tente novamente.")
                with st.chat_message("assistant"):
                    st.markdown(f"⚠️ {erro}")
                st.session_state.messages.append({"role": "assistant", "content": f"⚠️ {erro}"})
                with st.chat_message("assistant"):
                    st.markdown(PERGUNTAS[chave])
                st.session_state.messages.append({"role": "assistant", "content": PERGUNTAS[chave]})
        else:
            resposta = (
                "Obrigada! Se quiser, posso anotar mais preferências (bairro, vagas, pet-friendly, "
                "condomínio, lazer). Também posso encaminhar seu contato para um corretor agora."
            )
            with st.chat_message("assistant"):
                st.markdown(resposta)
            st.session_state.messages.append({"role": "assistant", "content": resposta})

    st.caption(f"© {COMPANY_NAME} • {COMPANY_BLURB}")


if __name__ == "__main__":
    app()

