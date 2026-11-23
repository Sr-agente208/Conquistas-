"""Seletores e URLs do Microsoft Rewards/Bing, centralizados.

A Microsoft muda o HTML com frequência. Se algo parar de funcionar, ajuste
**apenas este arquivo** — veja `docs/seletores.md`.
"""

from __future__ import annotations

import re

REWARDS_HOME = "https://rewards.bing.com/"
REWARDS_DASHBOARD = "https://rewards.bing.com/dashboard"
BING_HOME = "https://www.bing.com/?setlang=pt-br&cc=BR"

# Ordem de tentativa: do mais específico ao mais genérico.
POINTS_COUNTER = (
    "#id_rc",
    "#id_rc_chest",
    "mee-rewards-user-status-banner #id_rc",
    "[data-testid='points-counter']",
    "#rewards-user-info [class*='points']",
)

SIGNED_IN = (
    "#id_rc",
    "#mectrl_headerPicture",
    "#mectrl_main_trigger",
    "#id_rc_chest",
)

# Cartões de tarefas: conjunto diário e atividades extras.
DAILY_CARD_LINKS = (
    "#daily-sets mee-card a[href]",
    "#daily-sets a[href]",
    "#more-activities mee-card a[href]",
    "#more-activities a[href]",
    "mee-card a[href]",
    "section[class*='daily'] a[href]",
)

# Elementos clicáveis de quiz (respostas).
QUIZ_OPTIONS = (
    "#btoption0",
    "#btoption1",
    "div[class*='btOptionCard']",
    "label[for^='btoption']",
    "div[role='radio']",
    "input[type='radio']",
    "div[class*='option'] a",
    "div[class*='answer']",
)

# Botões de avanço/envio.
ADVANCE_BUTTONS = (
    "#nextQuestionbtn",
    "#rqSubmit",
    "button[class*='next']",
    "input[type='submit']",
    "button[type='submit']",
)

ADVANCE_TEXT = re.compile(
    r"pr[oó]xim|continuar|enviar|concluir|finalizar|verificar|next|continue|submit|finish|done",
    re.IGNORECASE,
)

# Sinais de que a tarefa terminou.
THANKS_TEXT = re.compile(
    r"obrigad|parab[eé]ns|conclu[ií]d|conclu[ií]da|voc[eê] ganhou|thanks|completed|you earned",
    re.IGNORECASE,
)
