# Youtube Summarizer

Youtube Summarizer é uma automação que acessa a página de inscrições do
YouTube, identifica vídeos recentes, envia cada URL para o site do Gemini e
salva os resumos em um banco SQLite local.

O fluxo principal é via Docker. O login Google é feito manualmente uma vez em um
navegador exposto por noVNC; depois disso, as execuções reutilizam o mesmo perfil
autenticado.

Se o leitor for um agente de IA, use também o runbook em
[docs/agent-runbook.md](docs/agent-runbook.md).

## Requisitos

- Docker e Docker Compose.
- Uma conta Google com acesso ao YouTube e ao Gemini.

## 1. Construir a Imagem

```bash
docker compose build
```

## 2. Fazer Login no Google

Inicie o navegador temporário de autenticação:

```bash
docker compose --profile auth up auth
```

Abra no navegador:

```text
http://localhost:6080/vnc.html
```

Faça login na conta Google e confirme que YouTube e Gemini abrem corretamente.
Depois disso, pare o serviço com `Ctrl+C`.

## 3. Verificar a Autenticação

```bash
docker compose run --rm app python -m yt_gemini auth-check
```

Saída esperada:

```text
auth-check: ok
YouTube subscriptions and Gemini are accessible.
```

## 4. Executar a Automação

```bash
docker compose run --rm app python -m yt_gemini run
```

Esse comando busca vídeos recentes, envia as URLs ao Gemini e salva os resumos no
SQLite.

Para processar apenas vídeos publicados a partir de uma data estimada:

```bash
docker compose run --rm app python -m yt_gemini run --since 2026-06-13
```

`--since` aceita data ISO (`YYYY-MM-DD`) ou datetime ISO. Datas sem timezone são
interpretadas como UTC.

## 5. Listar Resumos

```bash
docker compose run --rm app python -m yt_gemini list
```

Para limitar a quantidade exibida:

```bash
docker compose run --rm app python -m yt_gemini list --limit 5
```

Para listar apenas vídeos publicados a partir de uma data estimada:

```bash
docker compose run --rm app python -m yt_gemini list --since 2026-06-13 --limit 20
```

A listagem inclui canal, texto de publicação visto no YouTube, data estimada do
vídeo, data em que o scraper descobriu o vídeo e data em que o resumo foi salvo.

## Dados Persistentes

O Docker Compose usa volumes nomeados:

- `yt_gemini_browser_profile`: guarda o perfil do navegador e a sessão Google.
- `yt_gemini_data`: guarda o SQLite, logs e screenshots de falhas.

Apagar o volume do perfil remove a autenticação. Apagar o volume de dados remove
histórico, resumos e logs.

## Cuidados

- Não exponha o noVNC publicamente; use apenas localhost ou túnel SSH.
- Não automatize usuário, senha ou 2FA da conta Google.
- Não execute `auth-server` ao mesmo tempo que `auth-check` ou `run`, pois todos
  usam o mesmo perfil persistente.
- O aviso do Chrome sobre `--no-sandbox` é esperado dentro do Docker usado neste
  projeto.

## Desenvolvimento

O projeto usa `uv` para ambiente local e verificações:

```bash
uv sync
uv run ruff format --check .
uv run ruff check .
uv run mypy .
uv run pytest
```
