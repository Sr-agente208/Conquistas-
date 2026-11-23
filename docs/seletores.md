# Consertando seletores

A Microsoft altera o HTML do Rewards/Bing com frequência. Quase todo problema de
"não encontra os pontos" ou "não acha os cartões" se resolve editando
[`src/conquistas/selectors.py`](../src/conquistas/selectors.py).

## Onde cada seletor é usado

| Constante | Usada em | Efeito quando quebra |
| --- | --- | --- |
| `POINTS_COUNTER` | `auth.read_points_from_page` | saldo não é lido → `ensure_signed_in` falha |
| `SIGNED_IN` | `auth.is_signed_in` | login não é detectado |
| `DAILY_CARD_LINKS` | `tasks/daily._collect_cards` | "0 cartões encontrados" |
| `QUIZ_OPTIONS` | `tasks/daily._click_first` | quiz abre mas não avança |
| `ADVANCE_BUTTONS` / `ADVANCE_TEXT` | `tasks/daily._click_advance` | fica preso na primeira pergunta |
| `THANKS_TEXT` | `tasks/daily._already_done` | não reconhece conclusão (inofensivo) |

## Passo a passo

1. Rode com janela e log detalhado:

   ```bash
   conquistas -v run --only daily
   ```

2. Abra o DevTools (F12) na página do problema:

   ```js
   // saldo de pontos
   document.querySelector('#id_rc')?.innerText

   // cartões do dashboard
   [...document.querySelectorAll('#daily-sets a[href], #more-activities a[href]')]
     .map(a => a.getAttribute('href'))
   ```

3. Adicione o novo seletor **no começo** da tupla correspondente em `selectors.py`
   (a ordem é de tentativa; o primeiro que existir vence).

4. Rode os testes e confirme que nada quebrou:

   ```bash
   pytest
   ruff check .
   ```

5. Envie um PR descrevendo a região/idioma da conta e o trecho de HTML relevante.
   **Não** inclua prints com e-mail, nome ou ID da conta.

## Dicas

- Prefira atributos estáveis (`#id_rc`) a classes geradas (`css-1x2y3z`).
- `mee-card` é um componente web da Microsoft; use `a[href]` dentro dele.
- Quizzes podem viver em **iframe**: `daily.py` já percorre até 4 frames.
- Se o dashboard mudar de rota, ajuste `REWARDS_DASHBOARD` (hoje
  `https://rewards.bing.com/dashboard`).
