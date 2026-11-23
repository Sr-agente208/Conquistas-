# Conquistas

Automação **local** das buscas e das tarefas diárias do Microsoft Rewards, escrita em
Python + Playwright. O nome vem de "conquistas" — as tarefas que rendem pontos.

```
$ conquistas run
[pc 01/30] notícias de hoje economia
...
[pc 30/30] dicas de produtividade para iniciantes
[mobile 01/20] previsão do tempo hoje
...
Resumo da execução
==============================================
tarefa           feito  observação
----------------------------------------------
buscas:desktop   30/30
buscas:mobile    20/20
diario           4/6
----------------------------------------------
Saldo antes: 4.320   depois: 4.520
Ganho nesta execução: +200 pontos
```

---

## Site: todos os projetos do tópico `microsoft-rewards`

**Já está no ar — é só abrir e usar:**
<https://raw.githack.com/Sr-agente208/Conquistas-/arena/8c858577-conquistas/docs/projetos-offline.html>

Sem instalar nada, sem rodar comando e sem login. O link serve
`docs/projetos-offline.html` (página única, com CSS/JS/dados embutidos) através do
**raw.githack**, um CDN que entrega arquivos do GitHub com o `Content-Type` correto
(`text/html`). Como aponta para a branch, atualizar os arquivos atualiza o site.

> **Por que não no Supabase?** Testado e descartado: tanto Edge Functions quanto o
> Storage do Supabase reescrevem o `Content-Type` para `text/plain` — o navegador exibe
> o código-fonte em vez da página. Confirmado via `pg_net` (HTTP 200, 88.992 bytes,
> `text/plain`). As funções e o bucket usados no teste foram removidos.

Além da automação, o repositório publica uma **página estática** que reúne os
**71 projetos públicos** do tópico
[microsoft-rewards](https://github.com/topics/microsoft-rewards) — com busca, filtro por
linguagem, ordenação por estrelas/atualização/forks e cartões pensados para o celular.

```
docs/
  index.html        # página única, sem framework
  styles.css        # mobile-first, tema claro/escuro automático
  app.js            # busca, filtros, ordenação e renderização
  data/repos.json   # dados da API do GitHub
  data/repos.js     # mesmos dados como JS (funciona abrindo o arquivo direto)
  projetos-offline.html # versão em arquivo único, gerada pelo script
  seletores.md      # documentação da automação
```

Rodar localmente:

```bash
python3 -m http.server 8000 --directory docs
# abra http://localhost:8000
```

Alternativa: publicar no GitHub Pages (sem CI, sem build) em **Settings → Pages →
Deploy from a branch → escolha a branch e a pasta `/docs` → Save**. Funciona com `main` **ou com
qualquer outra branch** — por exemplo, a branch de um pull request, o que permite publicar
antes do merge. A página fica em `https://sr-agente208.github.io/Conquistas-/`.

Atualizar a lista com dados novos (requer `gh` autenticado):

```bash
python3 scripts/fetch_repos.py
```

Gerar a **versão offline** (um único `.html` com CSS, JS e dados embutidos, que abre
direto no celular sem servidor nem internet):

```bash
python3 scripts/build_standalone.py   # → docs/projetos-offline.html
```

---

## ⚠️ Aviso importante (leia antes de usar)

- O **Contrato de Serviços da Microsoft** não permite automação de pontos. Usar este
  projeto pode resultar em **suspensão da conta Rewards** ou perda de pontos.
- Use **somente na sua própria conta** e por sua conta e risco. Não há garantia de
  funcionamento, nem de que os pontos sejam creditados.
- Este repositório **não** contém: resolução de CAPTCHA, rotação de proxies, contas
  múltiplas ou qualquer mecanismo para burlar verificações da Microsoft.
- O projeto **não é afiliado, patrocinado ou endossado** pela Microsoft.
- Prefira ritmo lento (`min_delay_s`/`max_delay_s` altos). Rajadas de busca são o
  principal gatilho de bloqueio.

Se você só quer praticidade sem risco, considere a extensão oficial de busca do próprio
navegador ou fazer as buscas manualmente.

---

## O que ele faz

| Tarefa | Comando | Como funciona |
| --- | --- | --- |
| Buscas no PC | `conquistas run --only searches` | Digita consultas pt-BR no Bing, com pausas irregulares |
| Buscas no celular | idem | Usa um contexto com user-agent/viewport de iPhone |
| Conjunto diário e atividades extras | `conquistas run --only daily` | Abre cada cartão do dashboard e avança pelas respostas (**experimental**) |
| Saldo e histórico | `conquistas status`, `conquistas report` | SQLite local com execuções e evolução dos pontos |

O script **detecta a cota já cumprida**: se o saldo para de subir após algumas
checagens, ele encerra aquela etapa em vez de repetir buscas inúteis.

## Como funciona

1. `conquistas login` abre o Chromium **com janela** e espera você entrar normalmente
   (senha, 2FA, "manter conectado"). Nada de senha é armazenado: apenas os **cookies**
   da sessão, em `data/session/storage_state.json` (permissão `600`).
2. `conquistas run` reaproveita esses cookies, alterna entre os perfis de PC e celular
   e executa as tarefas com atrasos aleatórios (4–9 s por busca, por padrão).
3. Cada execução é registrada em `data/conquistas.sqlite3`, permitindo acompanhar
   ganhos por dia.

## Requisitos

- Python **3.11+**
- Chromium do Playwright (`playwright install chromium`) — ou Chrome/Edge já instalados
  (`channel = "chrome"` / `"msedge"`)
- Uma conta Microsoft com acesso ao Rewards

## Instalação

```bash
git clone https://github.com/Sr-agente208/Conquistas-.git
cd Conquistas-
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
playwright install chromium
cp config.example.toml conquistas.toml
```

Verifique o ambiente:

```bash
conquistas doctor
```

## Primeiro uso

```bash
# 1) login manual (a janela do navegador abre; entre na conta)
conquistas login

# 2) simulação: mostra as consultas e os cartões, sem executar nada
conquistas run --dry-run

# 3) execução real, com janela (recomendado nos primeiros dias)
conquistas run

# 4) depois de confiar no comportamento, pode rodar sem janela
conquistas run --headless
```

Atalhos úteis:

```bash
conquistas run --only searches --pc 10 --mobile 5   # teste curto
conquistas run --only daily --dry-run               # lista os cartões do dia
conquistas status                                   # saldo e resumo de hoje
conquistas report --days 30                         # ganhos por dia
```

Como o `python -m` também funciona: `python -m conquistas status`.

## Configuração (`conquistas.toml`)

O arquivo é opcional: sem ele, os padrões abaixo são usados. Caminhos relativos são
resolvidos a partir da pasta do TOML. Variáveis de ambiente úteis:
`CONQUISTAS_CONFIG`, `CONQUISTAS_HEADLESS`, `CONQUISTAS_STORAGE_STATE`, `CONQUISTAS_DB`.

```toml
[account]
locale = "pt-BR"
timezone = "America/Sao_Paulo"

[browser]
headless = false              # true = sem janela
slow_mo_ms = 0
channel = ""                  # "" = Chromium do Playwright; "chrome"; "msedge"
timeout_ms = 45000
storage_state = "data/session/storage_state.json"

[searches]
enabled = true
pc = 30                       # buscas no PC (90 pts no Brasil)
mobile = 20                   # buscas no celular (60 pts)
min_delay_s = 4.0
max_delay_s = 9.0
check_every = 5               # a cada N buscas, consulta o saldo
max_stalled_checks = 3        # encerra após N checagens sem ganho
human_typing = true
query_language = "pt-BR"

[daily]
enabled = true
max_cards = 12
max_steps_per_card = 15
per_card_timeout_s = 25.0

[storage]
database = "data/conquistas.sqlite3"

[logging]
level = "INFO"
file = "data/logs/conquistas.log"
```

> As cotas mudam por país e por conta. Ajuste `pc`/`mobile` ao que o seu painel mostra.

## Agendamento

**Linux/macOS (cron, todo dia às 9h):**

```cron
0 9 * * * cd /caminho/Conquistas- && .venv/bin/conquistas run --headless >> data/logs/cron.log 2>&1
```

**systemd (usuário):** `~/.config/systemd/user/conquistas.service`

```ini
[Unit]
Description=Conquistas diário

[Service]
Type=oneshot
WorkingDirectory=%h/Conquistas-
ExecStart=%h/Conquistas-/.venv/bin/conquistas run --headless
```

`~/.config/systemd/user/conquistas.timer`

```ini
[Unit]
Description=Executa o Conquistas todo dia

[Timer]
OnCalendar=*-*-* 09:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now conquistas.timer
```

**Windows:** Agendador de Tarefas → "Criar tarefa básica" → diariamente → ação
"Iniciar programa" → `.venv\Scripts\conquistas.exe` com argumento `run`.

## Docker

O login exige interface gráfica; o caminho mais simples é fazer o login **na máquina
host** e montar a pasta `data/` no contêiner:

```bash
docker build -t conquistas .
docker run --rm -v "$PWD/data:/app/data" -v "$PWD/conquistas.toml:/app/conquistas.toml" \
  conquistas run --headless
```

## Dados e privacidade

| Caminho | Conteúdo | Cuidado |
| --- | --- | --- |
| `data/session/storage_state.json` | cookies de sessão da sua conta | **trate como senha**; nunca comite |
| `data/conquistas.sqlite3` | histórico de execuções e pontos | local, sem dados pessoais |
| `data/logs/` | logs de execução | contém consultas feitas |

Tudo em `data/` e o `conquistas.toml` já estão no `.gitignore`.

## Solução de problemas

| Sintoma | Causa provável | O que fazer |
| --- | --- | --- |
| `Sessão inválida ou expirada` | cookies venceram | rode `conquistas login` de novo |
| `Executable doesn't exist ... chromium` | navegador não instalado | `playwright install chromium` |
| Buscas "funcionam" mas o saldo não sobe | cota já cumprida, região diferente ou conta sinalizada | confira o painel; reduza o ritmo |
| Nenhum cartão encontrado em `daily` | HTML do dashboard mudou | ver [docs/seletores.md](docs/seletores.md) |
| Rewards pede verificação/CAPTCHA | comportamento automatizado detectado | pare, use o navegador manualmente por alguns dias |
| `headless` não completa o login | Microsoft bloqueia navegador sem janela | rode `conquistas login` com janela |

## Limitações e estado do projeto

- **Buscas**: estáveis em relação à lógica; dependem do Bing continuar aceitando buscas
  via navegador.
- **Conjunto diário/quizzes**: **experimental** e melhor esforço. Os quizzes têm
  estruturas diferentes (inclusive em iframes) e o código tenta avançar até o fim; ele
  registra quantos cartões foram abertos, não uma confirmação de pontos.
- Não há resolução de CAPTCHA: se aparecer, a execução falha e você deve intervir.
- O projeto foi validado com testes automatizados (`pytest`, 41 testes) e simulação de
  CLI; a execução real depende da sua conta, região e da interface atual do Rewards.

## Desenvolvimento

```bash
pip install -e ".[dev]"
pytest             # testes unitários (não abrem navegador)
ruff check .
ruff format .
```

Um pipeline de CI pronto para copiar está em [`docs/ci.yml.example`](docs/ci.yml.example)
(copie para `.github/workflows/ci.yml`).

Estrutura:

```
src/conquistas/
  cli.py          # comandos: login, run, status, report, doctor
  config.py       # TOML + validação + variáveis de ambiente
  browser.py      # Playwright, perfis desktop/mobile, sessão salva
  auth.py         # login assistido e leitura de pontos
  human.py        # atrasos, digitação e rolagem "humanos"
  words_ptbr.py   # geração de consultas em português
  storage.py      # SQLite (execuções e histórico)
  selectors.py    # todos os seletores em um só lugar
  tasks/
    searches.py   # buscas PC e celular
    daily.py      # conjunto diário (melhor esforço)
scripts/
  fetch_repos.py     # atualiza os dados do site a partir da API do GitHub
  build_standalone.py # gera a versão offline em arquivo único
docs/             # página estática do tópico (publicável no GitHub Pages)
tests/            # pytest, sem dependência de navegador
docs/seletores.md # como consertar seletores quebrados
docs/ci.yml.example # pipeline de CI para copiar
```

Contribuições são bem-vindas — especialmente **correções de seletores** acompanhadas de
um print da tela (sem dados da conta) e ajustes de configuração por região.

## Licença

MIT — veja [LICENSE](LICENSE). Software fornecido "como está", sem garantias.
