import datetime as dt

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from charts import campaign_bar_chart, funnel_chart, trend_and_conversions
from meta_api import MetaAPIError, buscar_insights, listar_contas
from mock_data import gerar_dados_diarios
from theme import get_palette, global_css

st.set_page_config(
    page_title="Dashboard Meta Ads",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

PERIODOS = {
    "Últimos 7 dias": 7,
    "Últimos 14 dias": 14,
    "Últimos 30 dias": 30,
    "Este mês": None,
    "Personalizado": None,
}

THEME_STORAGE_KEY = "meta_ads_theme"


def bloquear_traducao_automatica():
    """Nomes de cliente/campanha sao texto fixo (as vezes em ingles/espanhol) - o Google
    Translate do Chrome pode tentar traduzir e distorcer o nome (ex: "Mustachios" -> "Bigodes").
    Marca a pagina inteira como 'notranslate' para o navegador nao oferecer/aplicar traducao."""
    components.html(
        """
        <script>
        const doc = window.parent.document;
        doc.documentElement.setAttribute('translate', 'no');
        doc.documentElement.classList.add('notranslate');
        if (!doc.querySelector('meta[name="google"]')) {
            const meta = doc.createElement('meta');
            meta.name = 'google';
            meta.content = 'notranslate';
            doc.head.appendChild(meta);
        }
        </script>
        """,
        height=0,
    )


def resolver_tema() -> str:
    tema_url = st.query_params.get("theme")
    if tema_url in ("dark", "light"):
        return tema_url

    # sem parametro na URL: usa o ultimo tema salvo em cookie (funciona mesmo em carga fria,
    # pois o cookie viaja com a propria requisicao HTTP, sem depender de JS no iframe)
    try:
        tema_cookie = st.context.cookies.get(THEME_STORAGE_KEY)
    except Exception:
        tema_cookie = None

    if tema_cookie in ("dark", "light"):
        return tema_cookie

    return "dark"


def persistir_tema(theme: str):
    components.html(
        f"<script>document.cookie = '{THEME_STORAGE_KEY}={theme}; path=/; max-age=31536000; SameSite=Lax';</script>",
        height=0,
    )


def calcular_intervalo(periodo: str) -> tuple[dt.date, dt.date]:
    hoje = dt.date.today()
    if periodo == "Este mês":
        return hoje.replace(day=1), hoje
    dias = PERIODOS.get(periodo, 30)
    return hoje - dt.timedelta(days=dias - 1), hoje


def formatar_moeda(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_numero(valor: float) -> str:
    return f"{valor:,.0f}".replace(",", ".")


def render_kpis(kpis: list[tuple[str, str]]):
    cards = "".join(
        f'<div class="kpi-card"><div class="kpi-accent"></div>'
        f'<div class="kpi-label">{titulo}</div>'
        f'<div class="kpi-value">{valor}</div></div>'
        for titulo, valor in kpis
    )
    st.markdown(f'<div class="kpi-grid">{cards}</div>', unsafe_allow_html=True)


def chart_shell_start(titulo: str, subtitulo: str):
    st.markdown(
        f'<div class="chart-shell"><div class="chart-head">'
        f'<div class="chart-title">{titulo}</div>'
        f'<div class="chart-subtitle">{subtitulo}</div></div>',
        unsafe_allow_html=True,
    )


def chart_shell_end():
    st.markdown("</div>", unsafe_allow_html=True)


def tabela_campanhas(df: pd.DataFrame) -> pd.DataFrame:
    agrupado = df.groupby(["campanha", "status"], as_index=False).agg(
        gasto=("gasto", "sum"),
        impressoes=("impressoes", "sum"),
        cliques=("cliques", "sum"),
        conversoes=("conversoes", "sum"),
    )
    agrupado["ctr"] = (agrupado["cliques"] / agrupado["impressoes"].replace(0, pd.NA) * 100).fillna(0)
    agrupado["cpc"] = (agrupado["gasto"] / agrupado["cliques"].replace(0, pd.NA)).fillna(0)
    agrupado["cpa"] = (agrupado["gasto"] / agrupado["conversoes"].replace(0, pd.NA)).fillna(0)
    agrupado = agrupado.sort_values("gasto", ascending=False)

    fmt = agrupado.copy()
    fmt["gasto"] = fmt["gasto"].apply(formatar_moeda)
    fmt["cpc"] = fmt["cpc"].apply(formatar_moeda)
    fmt["cpa"] = fmt["cpa"].apply(formatar_moeda)
    fmt["ctr"] = fmt["ctr"].apply(lambda v: f"{v:.2f}%")
    fmt["impressoes"] = fmt["impressoes"].apply(formatar_numero)
    fmt["cliques"] = fmt["cliques"].apply(formatar_numero)
    fmt["conversoes"] = fmt["conversoes"].apply(formatar_numero)
    fmt.columns = ["Campanha", "Status", "Gasto", "Impressões", "Cliques", "Conversões", "CTR", "CPC", "CPA"]
    return fmt


def token_salvo() -> str:
    return (st.secrets.get("META_ACCESS_TOKEN") or "").strip()


@st.cache_data(ttl=300, show_spinner=False)
def _contas_cache(token: str):
    return listar_contas(token)


@st.dialog("Conexão")
def dialog_conexao():
    """So a chave de API entra aqui - qual conta ver e escolhido direto na tela inicial."""
    modo = st.radio(
        "Fonte de dados",
        ["Dados de demonstração", "Conta real (Meta API)"],
        index=0 if st.session_state.get("cfg_modo", "Dados de demonstração") == "Dados de demonstração" else 1,
    )

    token = token_salvo()

    if modo == "Conta real (Meta API)":
        if not token:
            token = st.text_input(
                "Token de acesso",
                value=st.session_state.get("cfg_token", ""),
                type="password",
                help="Cole aqui ou salve em .streamlit/secrets.toml para não precisar colar toda vez.",
            )
        else:
            st.caption("Token de acesso salvo — não precisa colar de novo.")

    if st.button("Aplicar", use_container_width=True, type="primary"):
        st.session_state["cfg_modo"] = modo
        st.session_state["cfg_token"] = token
        st.rerun()


def barra_controles(theme: str):
    """Controles no topo da tela: cliente e periodo sempre visiveis, conexao/tema discretos."""
    barra = st.container(key="topbar")
    with barra:
        return _controles(theme)


def _controles(theme: str):
    modo = st.session_state.get("cfg_modo", "Dados de demonstração")
    token = st.session_state.get("cfg_token") or token_salvo() or None

    col_cliente, col_periodo, col_datas, col_conexao, col_tema = st.columns([3.0, 1.6, 1.6, 1.3, 1.3])

    ad_account_id = None
    nome_cliente = None

    with col_cliente:
        if modo == "Conta real (Meta API)" and token:
            try:
                contas = _contas_cache(token)
            except MetaAPIError as e:
                contas = []
                st.error(f"Não foi possível listar as contas: {e}")

            if contas:
                rotulos = [f"{c['name']} ({c['id']})" for c in contas]
                ids = [c["id"] for c in contas]
                conta_salva = st.session_state.get("cfg_conta") or st.secrets.get("META_AD_ACCOUNT_ID", "")
                indice_padrao = ids.index(conta_salva) if conta_salva in ids else 0
                escolha = st.selectbox(
                    "Conta do cliente", rotulos, index=indice_padrao, key="sel_cliente", label_visibility="collapsed"
                )
                idx = rotulos.index(escolha)
                ad_account_id = ids[idx]
                nome_cliente = contas[idx]["name"]
                st.session_state["cfg_conta"] = ad_account_id
                st.session_state["cfg_conta_nome"] = nome_cliente
            else:
                st.caption("Sem contas encontradas para esse token.")
        elif modo == "Conta real (Meta API)":
            st.caption("Configure o token em Conexão →")
        else:
            st.caption("Modo demonstração")

    with col_periodo:
        periodo = st.selectbox(
            "Período", list(PERIODOS.keys()), index=2, key="sel_periodo", label_visibility="collapsed"
        )

    with col_datas:
        if periodo == "Personalizado":
            with st.popover("Datas", use_container_width=True):
                data_ini = st.date_input("De", dt.date.today() - dt.timedelta(days=30), key="dt_ini")
                data_fim = st.date_input("Até", dt.date.today(), key="dt_fim")
        else:
            data_ini, data_fim = calcular_intervalo(periodo)

    with col_conexao:
        if st.button("Conexão", use_container_width=True, key="btn_conexao", type="tertiary"):
            dialog_conexao()

    with col_tema:
        rotulo = "Tema claro" if theme == "dark" else "Tema escuro"
        if st.button(rotulo, use_container_width=True, key="botao_tema", type="tertiary"):
            st.query_params["theme"] = "light" if theme == "dark" else "dark"
            st.rerun()

    return theme, modo, ad_account_id, token, data_ini, data_fim


def main():
    bloquear_traducao_automatica()

    theme_inicial = resolver_tema()
    st.markdown(global_css(theme_inicial), unsafe_allow_html=True)

    st.markdown('<div class="topbar-anchor"></div>', unsafe_allow_html=True)
    theme, modo, ad_account_id, access_token, data_ini, data_fim = barra_controles(theme_inicial)

    st.markdown(global_css(theme), unsafe_allow_html=True)
    palette = get_palette(theme)
    persistir_tema(theme)

    if modo == "Conta real (Meta API)" and ad_account_id and access_token:
        try:
            with st.spinner("Buscando dados na Meta API..."):
                df = buscar_insights(ad_account_id, access_token, str(data_ini), str(data_fim))
            if df.empty:
                st.warning("Nenhum dado retornado para o período selecionado.")
                st.stop()
            nome_cliente = st.session_state.get("cfg_conta_nome") or ad_account_id
            fonte = f'Cliente <b class="notranslate" translate="no">{nome_cliente}</b>'
        except MetaAPIError as e:
            st.error(f"Erro ao consultar a Meta API: {e}")
            st.info("Verifique se o token não expirou e se a conta tem permissão de leitura de anúncios.")
            st.stop()
    else:
        df = gerar_dados_diarios(pd.Timestamp(data_ini), pd.Timestamp(data_fim))
        fonte = "Dados de <b>demonstração</b>"

    periodo_label = f"{data_ini.strftime('%d/%m/%Y')} — {data_fim.strftime('%d/%m/%Y')}"
    st.markdown(
        f'<div class="hero-row"><div>'
        f'<div class="kicker">Meta Ads · Relatório de campanha</div>'
        f'<div class="hero-title">Painel de Performance</div>'
        f'</div><div class="hero-meta">{fonte}<br/>Período <b>{periodo_label}</b></div></div>',
        unsafe_allow_html=True,
    )

    gasto_total = df["gasto"].sum()
    conversoes_total = int(df["conversoes"].sum())
    cliques_total = int(df["cliques"].sum())
    impressoes_total = int(df["impressoes"].sum())
    cpa = gasto_total / conversoes_total if conversoes_total else 0
    ctr = cliques_total / impressoes_total * 100 if impressoes_total else 0
    cpm = gasto_total / impressoes_total * 1000 if impressoes_total else 0
    cpc = gasto_total / cliques_total if cliques_total else 0

    render_kpis([
        ("Gasto Total", formatar_moeda(gasto_total)),
        ("Conversões", formatar_numero(conversoes_total)),
        ("Custo por Resultado", formatar_moeda(cpa)),
        ("CTR", f"{ctr:.2f}%"),
        ("CPM", formatar_moeda(cpm)),
        ("CPC", formatar_moeda(cpc)),
    ])

    diario = df.groupby("data", as_index=False).agg(gasto=("gasto", "sum"), conversoes=("conversoes", "sum"))
    datas_fmt = diario["data"].dt.strftime("%d/%m").tolist()

    cpa_medio = cpa
    agrupado = df.groupby("campanha", as_index=False).agg(gasto=("gasto", "sum"), conversoes=("conversoes", "sum"))
    agrupado["cpa"] = (agrupado["gasto"] / agrupado["conversoes"].replace(0, pd.NA)).fillna(0)

    tab_tendencia, tab_funil, tab_campanhas, tab_tabela = st.tabs(
        ["Tendência", "Funil", "Campanhas", "Tabela completa"]
    )

    with tab_tendencia:
        chart_shell_start("Gasto e Conversões", "Evolução diária — passe o mouse para comparar")
        components.html(
            trend_and_conversions(datas_fmt, diario["gasto"].round(2).tolist(), diario["conversoes"].tolist(), theme),
            height=352,
        )
        chart_shell_end()

    with tab_funil:
        chart_shell_start("Funil de Performance", "Do alcance à conversão — onde o público se perde")
        components.html(funnel_chart(impressoes_total, cliques_total, conversoes_total, theme), height=352)
        chart_shell_end()

    with tab_campanhas:
        chart_shell_start(
            "Gasto por Campanha",
            f'<span style="color:{palette["good"]}">●</span> CPA abaixo da média &nbsp; '
            f'<span style="color:{palette["critical"]}">●</span> CPA acima da média',
        )
        components.html(
            campaign_bar_chart(
                agrupado["campanha"].tolist(),
                agrupado["gasto"].tolist(),
                agrupado["cpa"].tolist(),
                cpa_medio,
                theme,
            ),
            height=352,
        )
        chart_shell_end()

    with tab_tabela:
        st.dataframe(tabela_campanhas(df), use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
