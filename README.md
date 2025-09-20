# Ayla — Assistente de Imobiliária (Streamlit)

Aplicativo em Streamlit para coletar leads de clientes de imobiliária de forma guiada, com:
- Coleta passo a passo via chat (nome, telefone, e‑mail, preferências etc.)
- Salvamento em `imobiliaria_leads.xlsx` (ou CSV de fallback) com deduplicação por telefone/e‑mail
- Mensagens mais conversacionais opcionais usando OpenAI (sem expor a chave no código)
- Suporte a UTM e ID único por lead

## Requisitos
- Python 3.10+ (recomendado)
- Pip e ambiente virtual (venv)

## Instalação e uso local
1) Crie e ative um ambiente virtual
- Windows (PowerShell):
  - `python -m venv .venv`
  - `.\.venv\Scripts\Activate.ps1`
- macOS/Linux:
  - `python3 -m venv .venv`
  - `source .venv/bin/activate`

2) Instale as dependências
- `python -m pip install -r requirements.txt`

3) Configure as variáveis de ambiente
- Copie o exemplo: `cp .env.example .env` (no Windows: `Copy-Item .env.example .env`)
- Edite `.env` e preencha conforme necessário:
  - `OPENAI_API_KEY`: sua chave da OpenAI (opcional; necessária apenas para IA conversacional)
  - `AYLA_USE_OPENAI`: `1` para habilitar tom conversacional com OpenAI, `0` para desabilitar
  - `OPENAI_MODEL`: modelo OpenAI, ex.: `gpt-4o-mini`
  - `COMPANY_NAME`, `COMPANY_BLURB`: personalização do texto da Ayla
  - `APP_ORIGIN`: URL do app (ex.: `http://localhost:8501`)

4) Rode o app
- `python -m streamlit run aplicativo_imobiliaria.py`

## Salvamento de leads
- O app salva em `imobiliaria_leads.xlsx` (Excel, engine `openpyxl`). Se houver erro, usa `imobiliaria_leads.csv` (append).
- Deduplicação: cria/atualiza registros conforme a chave `dedup_key` (SHA‑256 de telefone 11 dígitos + e‑mail em minúsculas).
- Colunas salvas:
  - `lead_id`, `dedup_key`, `criado_em`, `app_origin`
  - `utm_source`, `utm_medium`, `utm_campaign`, `utm_term`, `utm_content`
  - Campos do funil: `nome`, `telefone`, `email`, `operacao`, `tipo_imovel`, `metragem`, `quartos`, `faixa_preco`, `urgencia`

Observação: ao rodar em serviços de cloud (ex.: Streamlit Cloud), o sistema de arquivos pode ser efêmero; considere uma persistência externa (Google Sheets, S3/Supabase/DB).

## Deploy no Streamlit Cloud
1) Garanta que o repositório contenha:
- `aplicativo_imobiliaria.py`, `requirements.txt`, `.gitignore`, `.env.example`, `README.md`

2) No Streamlit Cloud
- New app → conecte ao GitHub → escolha o repositório (ex.: `CerebroArtificial-cmd/atendimentoimobiliaria-ia`)
- Branch: `main` (ou a que usar)
- Main file path: `aplicativo_imobiliaria.py`
- Configure Secrets (Settings → Secrets):
  - `OPENAI_API_KEY = sk-...` (se usar IA conversacional)
  - `AYLA_USE_OPENAI = 1`
  - `COMPANY_NAME`, `COMPANY_BLURB`, `APP_ORIGIN` (opcional)

3) Deploy
- O app sobe e fica acessível pela URL pública do Streamlit Cloud.

## O que subir ao GitHub
- Subir: `aplicativo_imobiliaria.py`, `requirements.txt`, `.gitignore`, `.env.example`, `README.md`
- Não subir: `.env`, `.venv/`, `imobiliaria_leads.xlsx`, `imobiliaria_leads.csv`, `__pycache__/`, `*.pyc`, `.streamlit/`

Exemplo de comandos:
- `git init`
- `git remote add origin https://github.com/SEU_USUARIO/SEU_REPO.git`
- `git add -A && git commit -m "Primeiro deploy Ayla"`
- `git branch -M main && git push -u origin main`

## Solução de problemas
- “streamlit não encontrado”: ative a venv e reinstale `pip install -r requirements.txt`.
- Erro ao salvar Excel: verifique se o arquivo não está aberto; o app faz fallback para CSV.
- Chave OpenAI: não committe `.env`. Em cloud, configure em “Secrets”.
- Mensagens não conversacionais: defina `AYLA_USE_OPENAI=1` e `OPENAI_API_KEY` válido.
- Telefone inválido: a deduplicação exige 11 dígitos (DDD + número) para usar o telefone.

---
Sugestões de evolução: integração com Google Sheets/DB para persistência confiável; painel administrativo para leitura de leads; e-mails automáticos para a equipe.
