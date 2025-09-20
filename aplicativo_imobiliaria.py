import os
import re
import time
import datetime

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

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

# Inicializa cliente OpenAI apenas se disponível (não utilizado neste fluxo)
client = None
if OpenAI and OPENAI_API_KEY:
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


def salvar_lead(lead: dict) -> None:
    """Salva o lead em Excel; se falhar, faz fallback para CSV."""
    ordem = list(PERGUNTAS.keys())
    registro = {k: lead.get(k, "") for k in ordem}
    df = pd.DataFrame([registro])
    try:
        # Usa engine openpyxl para garantir compatibilidade
        df.to_excel("imobiliaria_leads.xlsx", index=False, engine="openpyxl")
    except Exception:
        df.to_csv("imobiliaria_leads.csv", index=False, encoding="utf-8")


def perguntar_proximo_campo():
    if st.session_state.step < len(PERGUNTAS):
        chave = list(PERGUNTAS.keys())[st.session_state.step]
        pergunta = PERGUNTAS[chave]
        st.session_state.messages.append({"role": "assistant", "content": pergunta})
        with st.chat_message("assistant"):
            st.markdown(pergunta)
    else:
        salvar_lead(st.session_state.lead)
        msg_final = (
            "Perfeito! Lead completo e salvo.\n\n"
            "Em breve nossa equipe entrará em contato. "
            "Se quiser, pode me contar mais preferências (bairro, vagas, pet-friendly etc.)."
        )
        st.session_state.messages.append({"role": "assistant", "content": msg_final})
        with st.chat_message("assistant"):
            st.markdown(msg_final)


def app():
    st.header("Atendente de Imobiliária com IA")

    # Banner opcional sobre OpenAI
    if not OPENAI_API_KEY:
        st.info("OPENAI_API_KEY não definida. O fluxo de coleta não usa OpenAI.")

    # Estado inicial
    if "lead" not in st.session_state:
        st.session_state.lead = {}
        st.session_state.step = 0
        st.session_state.messages = []
        st.session_state.prev_question_timestamp = datetime.datetime.now() - datetime.timedelta(seconds=5)

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
