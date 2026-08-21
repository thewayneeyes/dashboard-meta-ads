"""Gera dados ficticios de campanhas Meta Ads para testes visuais."""
import numpy as np
import pandas as pd

CAMPAIGNS = [
    "Institucional - Alcance",
    "Remarketing - Carrinho",
    "Leads - Formulario",
    "Conversao - Catalogo",
    "Trafego - Blog",
    "Engajamento - Stories",
]

STATUS_OPTIONS = ["Ativo", "Ativo", "Ativo", "Pausado", "Em revisao"]


def gerar_dados_diarios(data_inicio: pd.Timestamp, data_fim: pd.Timestamp, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dias = pd.date_range(data_inicio, data_fim, freq="D")

    linhas = []
    for campanha in CAMPAIGNS:
        gasto_base = rng.uniform(80, 400)
        ctr_base = rng.uniform(0.008, 0.025)
        conv_rate_base = rng.uniform(0.02, 0.08)
        status = rng.choice(STATUS_OPTIONS)

        for dia in dias:
            variacao = rng.normal(1.0, 0.18)
            gasto = max(gasto_base * variacao, 5)
            impressoes = int(gasto / rng.uniform(0.015, 0.035))
            # alcance (pessoas unicas) e sempre <= impressoes, ja que a mesma pessoa pode
            # ver o anuncio mais de uma vez (frequencia media aqui fica entre ~1.15x e ~1.6x)
            alcance = int(impressoes / rng.uniform(1.15, 1.6))
            cliques = max(int(impressoes * ctr_base * rng.normal(1.0, 0.15)), 0)
            conversoes = max(int(cliques * conv_rate_base * rng.normal(1.0, 0.2)), 0)

            linhas.append(
                {
                    "data": dia,
                    "campanha": campanha,
                    "status": status,
                    "gasto": round(gasto, 2),
                    "impressoes": impressoes,
                    "alcance": alcance,
                    "cliques": cliques,
                    "conversoes": conversoes,
                }
            )

    df = pd.DataFrame(linhas)
    df["ctr"] = np.where(df["impressoes"] > 0, df["cliques"] / df["impressoes"] * 100, 0)
    df["cpc"] = np.where(df["cliques"] > 0, df["gasto"] / df["cliques"], 0)
    df["cpm"] = np.where(df["impressoes"] > 0, df["gasto"] / df["impressoes"] * 1000, 0)
    df["cpa"] = np.where(df["conversoes"] > 0, df["gasto"] / df["conversoes"], 0)
    df["eh_objetivo_alcance"] = False
    return df
