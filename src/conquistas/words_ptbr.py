"""Geração de consultas de busca em português, sem repetições."""

from __future__ import annotations

import random

TEMAS = (
    "notícias de hoje",
    "previsão do tempo",
    "resultado do jogo",
    "receita de bolo",
    "receita fitness",
    "como economizar dinheiro",
    "novidades de tecnologia",
    "lançamentos de celular",
    "séries para assistir",
    "filmes de ação",
    "música brasileira",
    "história do Brasil",
    "curiosidades sobre animais",
    "dicas de produtividade",
    "como aprender inglês",
    "viagem barata",
    "trilhas no Brasil",
    "carros elétricos",
    "inteligência artificial",
    "segurança digital",
    "mercado de trabalho",
    "concurso público",
    "receitas vegetarianas",
    "exercícios em casa",
    "jogos para celular",
    "campeonato brasileiro",
    "fórmula 1",
    "olimpíadas",
    "ciência e espaço",
    "mudanças climáticas",
    "livros recomendados",
    "concertos e shows",
    "teatro em cartaz",
    "economia do Brasil",
    "inflação hoje",
    "dólar hoje",
    "bolsa de valores",
    "empreendedorismo",
    "marketing digital",
    "plantas para apartamento",
    "jardinagem para iniciantes",
    "fotografia com celular",
    "dicas de culinária",
    "saúde do coração",
    "qualidade do sono",
)

COMPLEMENTOS = (
    "hoje",
    "2026",
    "passo a passo",
    "para iniciantes",
    "o que é",
    "como funciona",
    "melhores opções",
    "vale a pena",
    "dicas rápidas",
    "guia completo",
    "notícias recentes",
    "tutorial",
    "comparativo",
    "preço",
    "onde encontrar",
    "principais erros",
)

PERGUNTAS = (
    "por que {tema}?",
    "qual o melhor {tema}?",
    "quanto custa {tema}?",
    "{tema} funciona mesmo?",
    "como começar com {tema}?",
)


def generate_queries(count: int, rng: random.Random | None = None) -> list[str]:
    """Gera `count` consultas únicas e naturais em pt-BR."""
    if count <= 0:
        return []
    rng = rng or random.Random()
    queries: list[str] = []
    seen: set[str] = set()
    attempts = 0
    max_attempts = count * 40 + 100
    while len(queries) < count and attempts < max_attempts:
        attempts += 1
        tema = rng.choice(TEMAS)
        roll = rng.random()
        if roll < 0.2:
            query = rng.choice(PERGUNTAS).format(tema=tema)
        elif roll < 0.55:
            query = f"{tema} {rng.choice(COMPLEMENTOS)}"
        else:
            query = f"{tema} {rng.choice(COMPLEMENTOS)} {rng.choice(COMPLEMENTOS)}"
        query = " ".join(query.split())
        if query.lower() in seen:
            continue
        seen.add(query.lower())
        queries.append(query)
    return queries
