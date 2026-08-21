import base64
import datetime as dt
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from charts import campaign_bar_chart, funnel_chart, trend_and_conversions
from meta_api import MetaAPIError, buscar_alcance_exato, buscar_insights, listar_contas
from mock_data import gerar_dados_diarios
from theme import get_palette, global_css

ASSETS_DIR = Path(__file__).parent / "assets"


@st.cache_data(show_spinner=False)
def logo_data_uri(theme: str) -> str:
    """Selinho da agencia no cabecalho - amarelo no tema escuro, preto no tema claro."""
    nome_arquivo = "logo-vanti-amarelo.png" if theme == "dark" else "logo-vanti-preto.png"
    caminho = ASSETS_DIR / nome_arquivo
    if not caminho.exists():
        return ""
    dados = base64.b64encode(caminho.read_bytes()).decode()
    return f"data:image/png;base64,{dados}"

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
CLIENT_STORAGE_KEY = "meta_ads_client"


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


def cliente_salvo() -> str:
    """Ultimo cliente (conta de anuncios) acessado, guardado num cookie do navegador -
    cada pessoa da agencia abre o dashboard e ja cai na conta que ela mesma viu por ultimo."""
    try:
        return st.context.cookies.get(CLIENT_STORAGE_KEY) or ""
    except Exception:
        return ""


def persistir_cliente(ad_account_id: str):
    if not ad_account_id:
        return
    components.html(
        f"<script>document.cookie = '{CLIENT_STORAGE_KEY}={ad_account_id}; path=/; max-age=31536000; SameSite=Lax';</script>",
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


def tabela_campanhas(df: pd.DataFrame, alcance_exato: dict | None = None) -> pd.DataFrame:
    agrupado = df.groupby(["campanha", "status"], as_index=False).agg(
        gasto=("gasto", "sum"),
        impressoes=("impressoes", "sum"),
        alcance=("alcance", "sum"),
        cliques=("cliques", "sum"),
        conversoes=("conversoes", "sum"),
        eh_alcance=("eh_objetivo_alcance", "any"),
    )
    if alcance_exato:
        # troca o somatorio diario (aproximado) pelo alcance exato por campanha, do
        # mesmo jeito que a Meta calcula - sem duplicar gente entre dias
        por_campanha = alcance_exato.get("por_campanha", {})
        agrupado["alcance"] = agrupado["campanha"].map(por_campanha).fillna(agrupado["alcance"]).astype(int)

    # campanhas de alcance: o "resultado" e o proprio alcance - sincroniza as duas
    # colunas pra nao ficarem com numeros ligeiramente diferentes entre si
    agrupado.loc[agrupado["eh_alcance"], "conversoes"] = agrupado.loc[agrupado["eh_alcance"], "alcance"]
    agrupado = agrupado.drop(columns=["eh_alcance"])

    agrupado["frequencia"] = (agrupado["impressoes"] / agrupado["alcance"].replace(0, pd.NA)).fillna(0)
    agrupado["ctr"] = (agrupado["cliques"] / agrupado["impressoes"].replace(0, pd.NA) * 100).fillna(0)
    agrupado["cpc"] = (agrupado["gasto"] / agrupado["cliques"].replace(0, pd.NA)).fillna(0)
    agrupado["cpa"] = (agrupado["gasto"] / agrupado["conversoes"].replace(0, pd.NA)).fillna(0)
    agrupado = agrupado.sort_values("gasto", ascending=False)

    fmt = agrupado.copy()
    fmt["gasto"] = fmt["gasto"].apply(formatar_moeda)
    fmt["cpc"] = fmt["cpc"].apply(formatar_moeda)
    fmt["cpa"] = fmt["cpa"].apply(formatar_moeda)
    fmt["ctr"] = fmt["ctr"].apply(lambda v: f"{v:.2f}%")
    fmt["frequencia"] = fmt["frequencia"].apply(lambda v: f"{v:.2f}")
    fmt["impressoes"] = fmt["impressoes"].apply(formatar_numero)
    fmt["alcance"] = fmt["alcance"].apply(formatar_numero)
    fmt["cliques"] = fmt["cliques"].apply(formatar_numero)
    fmt["conversoes"] = fmt["conversoes"].apply(formatar_numero)
    fmt = fmt[
        ["campanha", "status", "gasto", "impressoes", "alcance", "frequencia", "cliques", "conversoes", "ctr", "cpc", "cpa"]
    ]
    fmt.columns = [
        "Campanha", "Status", "Gasto", "Impressões", "Alcance", "Frequência", "Cliques", "Conversões", "CTR", "CPC", "CPA",
    ]
    return fmt


def token_salvo() -> str:
    return (st.secrets.get("META_ACCESS_TOKEN") or "").strip()


@st.cache_data(ttl=300, show_spinner=False)
def _contas_cache(token: str):
    return listar_contas(token)


CLIENT_VIEW_PARAM = "cliente"


def conta_da_url() -> str:
    """Se o link tiver ?cliente=act_123, a tela trava nessa conta - usado pro link que a
    agencia manda pro proprio cliente final acessar so os dados dele."""
    valor = st.query_params.get(CLIENT_VIEW_PARAM, "")
    if valor and not valor.startswith("act_"):
        valor = f"act_{valor}"
    return valor


STATUS_VIEW_PARAM = "status"
STATUS_OPCOES = ["Ativas", "Desativadas"]
_STATUS_URL = {"Ativas": "ativas", "Desativadas": "desativadas"}
_STATUS_URL_INVERSO = {v: k for k, v in _STATUS_URL.items()}


def status_da_url() -> list[str]:
    """Quais status (ativas/desativadas) considerar - lido da URL. Usado no link travado
    do cliente final, que nao tem controle nenhum pra mudar isso (a agencia decide na
    hora de gerar o link, e fica fixo dali pra frente)."""
    bruto = st.query_params.get(STATUS_VIEW_PARAM, "")
    selecionados = [_STATUS_URL_INVERSO[v] for v in bruto.split(",") if v in _STATUS_URL_INVERSO]
    return selecionados or ["Ativas"]


def status_para_url(selecionados: list[str]) -> str:
    return ",".join(_STATUS_URL[s] for s in selecionados if s in _STATUS_URL)


def link_visualizacao_cliente(ad_account_id: str, status_selecionados: list[str] | None = None) -> str:
    """Monta o link publico que, quando aberto, trava a tela nessa conta - sem mostrar as
    outras contas, sem token nenhum na URL (o token fica so no servidor). O status das
    campanhas (ativas/desativadas) tambem fica travado nesse link, escolhido pela agencia
    na hora de gerar - o cliente final so ve o que foi definido pra ele."""
    try:
        host = st.context.headers.get("host", "")
    except Exception:
        host = ""
    base = f"?{CLIENT_VIEW_PARAM}={ad_account_id}" if not host else (
        f"{'http' if host.startswith('localhost') else 'https'}://{host}/?{CLIENT_VIEW_PARAM}={ad_account_id}"
    )
    if status_selecionados:
        base += f"&{STATUS_VIEW_PARAM}={status_para_url(status_selecionados)}"
    return base


@st.dialog("Conexão")
def dialog_conexao():
    """So a chave de API - qual conta ver e escolhido direto na tela inicial, e o dashboard
    ja conecta sozinho sempre que o token estiver disponivel (nada de alternar demo/real)."""
    token_secreto = token_salvo()

    if token_secreto:
        st.success("Token de acesso configurado — o dashboard já conecta automaticamente.")
        st.caption("Para trocar o token, atualize em Settings → Secrets no Streamlit Cloud.")
        _secao_link_cliente(token_secreto)
        if st.button("Fechar", use_container_width=True, type="primary"):
            st.rerun()
        return

    st.caption("Nenhum token salvo no servidor. Cole abaixo para conectar nesta sessão.")
    token = st.text_input(
        "Token de acesso",
        value=st.session_state.get("cfg_token", ""),
        type="password",
        help="Para não precisar colar toda vez, salve em Settings → Secrets no Streamlit Cloud (META_ACCESS_TOKEN).",
    )

    if st.button("Aplicar", use_container_width=True, type="primary"):
        st.session_state["cfg_token"] = token
        st.rerun()


def _secao_link_cliente(token: str):
    """Gera um link que trava a tela numa conta so - pra agencia mandar pro proprio
    cliente final acessar apenas os dados dele, sem ver as outras contas nem o token."""
    st.divider()
    st.markdown("**Link para o cliente**")
    st.caption("Gere um link travado numa única conta — quem abrir só vê aquele cliente.")

    try:
        contas = _contas_cache(token)
    except MetaAPIError:
        contas = []

    if not contas:
        st.caption("Nenhuma conta disponível ainda.")
        return

    rotulos = [f"{c['name']} ({c['id']})" for c in contas]
    ids = [c["id"] for c in contas]
    conta_atual = st.session_state.get("cfg_conta")
    indice_padrao = ids.index(conta_atual) if conta_atual in ids else 0

    escolha = st.selectbox("Cliente", rotulos, index=indice_padrao, key="sel_cliente_link")
    ad_account_id = ids[rotulos.index(escolha)]

    status_link = st.multiselect(
        "Campanhas que esse cliente pode ver",
        STATUS_OPCOES,
        default=["Ativas"],
        key="status_link_cliente",
        help="Escolha aqui antes de copiar o link — depois de gerado, o cliente não consegue mudar isso.",
    )
    st.code(link_visualizacao_cliente(ad_account_id, status_link), language=None)


def barra_controles(theme: str):
    """Controles no topo da tela: cliente e periodo sempre visiveis, conexao/tema discretos."""
    barra = st.container(key="topbar")
    with barra:
        return _controles(theme)


def _controles(theme: str):
    token = st.session_state.get("cfg_token") or token_salvo() or None
    # conecta automaticamente sempre que houver token - sem alternancia manual demo/real
    modo = "Conta real (Meta API)" if token else "Dados de demonstração"

    col_logo, col_cliente, col_periodo, col_datas, col_status, col_conexao, col_tema = st.columns(
        [1.6, 2.3, 1.3, 1.0, 1.1, 0.9, 0.5]
    )

    ad_account_id = None
    nome_cliente = None

    conta_travada = conta_da_url()

    with col_logo:
        logo_src = logo_data_uri(theme)
        if logo_src:
            st.markdown(
                f'<img src="{logo_src}" alt="Vanti Marketing Criativo" class="topbar-logo">',
                unsafe_allow_html=True,
            )

    with col_cliente:
        if modo == "Conta real (Meta API)" and conta_travada:
            # link de cliente final: tela travada numa conta so, sem selectbox, sem ver
            # o resto da carteira da agencia
            try:
                contas = _contas_cache(token)
            except MetaAPIError:
                contas = []
            info_conta = next((c for c in contas if c["id"] == conta_travada), None)
            if info_conta:
                ad_account_id = conta_travada
                nome_cliente = info_conta["name"]
                st.session_state["cfg_conta_nome"] = nome_cliente
                st.markdown(
                    f'<div style="padding-top:8px;font-weight:700;" class="notranslate" translate="no">'
                    f'{nome_cliente}</div>',
                    unsafe_allow_html=True,
                )
            # se a conta do link nao existir mais (removida, token trocado), ad_account_id
            # fica None e o main() mostra uma mensagem de erro clara em vez de vazar dados
        elif modo == "Conta real (Meta API)":
            try:
                contas = _contas_cache(token)
            except MetaAPIError as e:
                contas = []
                st.error(f"Não foi possível listar as contas: {e}")

            if contas:
                rotulos = [f"{c['name']} ({c['id']})" for c in contas]
                ids = [c["id"] for c in contas]
                # prioridade pra escolher a conta padrao: selecao atual > ultimo cliente
                # acessado (cookie do navegador) > conta fixa nos Secrets > primeira da lista
                conta_padrao = (
                    st.session_state.get("cfg_conta")
                    or cliente_salvo()
                    or st.secrets.get("META_AD_ACCOUNT_ID", "")
                )
                indice_padrao = ids.index(conta_padrao) if conta_padrao in ids else 0
                escolha = st.selectbox(
                    "Conta do cliente", rotulos, index=indice_padrao, key="sel_cliente", label_visibility="collapsed"
                )
                idx = rotulos.index(escolha)
                ad_account_id = ids[idx]
                nome_cliente = contas[idx]["name"]
                if ad_account_id != st.session_state.get("cfg_conta"):
                    persistir_cliente(ad_account_id)
                st.session_state["cfg_conta"] = ad_account_id
                st.session_state["cfg_conta_nome"] = nome_cliente
            else:
                st.caption("Sem contas encontradas para esse token.")
        else:
            st.caption("Modo demonstração — configure o token em Conexão →")

    with col_periodo:
        periodo = st.selectbox(
            "Período", list(PERIODOS.keys()), index=2, key="sel_periodo", label_visibility="collapsed"
        )

    with col_datas:
        if periodo == "Personalizado":
            with st.popover("Datas", use_container_width=True):
                data_ini = st.date_input(
                    "De", dt.date.today() - dt.timedelta(days=30), key="dt_ini", format="DD/MM/YYYY"
                )
                data_fim = st.date_input("Até", dt.date.today(), key="dt_fim", format="DD/MM/YYYY")
        else:
            data_ini, data_fim = calcular_intervalo(periodo)

    with col_status:
        if conta_travada:
            # link do cliente final: status fixo, escolhido pela agencia na hora de
            # gerar o link - sem controle nenhum aqui pro cliente mudar
            status_selecionados = status_da_url()
        else:
            with st.popover("Status", use_container_width=True):
                st.caption("Quais campanhas considerar no dashboard")
                status_selecionados = st.multiselect(
                    "Status",
                    STATUS_OPCOES,
                    default=st.session_state.get("status_filtro", ["Ativas"]),
                    key="status_filtro",
                    label_visibility="collapsed",
                )
            if not status_selecionados:
                status_selecionados = ["Ativas"]

    with col_conexao:
        if not conta_travada:
            # visualizacao de cliente (link travado numa conta) nao tem acesso a Conexao
            if st.button("Conexão", use_container_width=True, key="btn_conexao", type="tertiary"):
                dialog_conexao()

    with col_tema:
        icone = "☀️" if theme == "dark" else "🌙"
        if st.button(icone, use_container_width=True, key="botao_tema", type="tertiary", help="Trocar tema"):
            st.query_params["theme"] = "light" if theme == "dark" else "dark"
            st.rerun()

    return theme, modo, ad_account_id, token, data_ini, data_fim, bool(conta_travada), status_selecionados


def main():
    bloquear_traducao_automatica()

    theme_inicial = resolver_tema()
    st.markdown(global_css(theme_inicial), unsafe_allow_html=True)

    st.markdown('<div class="topbar-anchor"></div>', unsafe_allow_html=True)
    theme, modo, ad_account_id, access_token, data_ini, data_fim, conta_travada, status_selecionados = (
        barra_controles(theme_inicial)
    )

    st.markdown(global_css(theme), unsafe_allow_html=True)
    palette = get_palette(theme)
    persistir_tema(theme)

    if conta_travada and not ad_account_id:
        # link de cliente apontando pra uma conta que sumiu (token trocado, conta
        # removida) - mostra erro claro em vez de cair no modo demonstracao por engano
        st.error("Este link não é válido ou a conta não está mais disponível.")
        st.info("Peça um novo link para a agência.")
        st.stop()

    alcance_exato = None  # so preenchido no modo real - vem de uma consulta separada

    if modo == "Conta real (Meta API)" and ad_account_id and access_token:
        try:
            with st.spinner("Buscando dados na Meta API..."):
                df = buscar_insights(ad_account_id, access_token, str(data_ini), str(data_fim))
                if not df.empty:
                    try:
                        alcance_exato = buscar_alcance_exato(
                            ad_account_id, access_token, str(data_ini), str(data_fim)
                        )
                    except MetaAPIError:
                        alcance_exato = None  # sem isso, cai no somatorio diario como reserva
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

    # filtro de status (Ativas/Desativadas) escolhido na barra de controles - ou fixo
    # vindo da URL quando e o link travado de um cliente final. Aplica igual em tudo
    # (tabela, graficos, totais) pra ficar tudo consistente entre si.
    total_campanhas_periodo = df["campanha"].nunique()
    campanha_ativa = df["status"] == "Ativo"
    mostrar = pd.Series(False, index=df.index)
    if "Ativas" in status_selecionados:
        mostrar |= campanha_ativa
    if "Desativadas" in status_selecionados:
        mostrar |= ~campanha_ativa
    df = df[mostrar]
    if df.empty:
        st.warning(
            f"Nenhuma campanha corresponde ao filtro de status selecionado — {total_campanhas_periodo} "
            "campanha(s) teve(veram) veiculação no período."
        )
        st.stop()

    if alcance_exato:
        # a consulta de alcance exato busca TODAS as campanhas (antes do filtro de status
        # acima) - sem isso, o alcance total ficaria contando campanhas desativadas que
        # ja foram excluidas de todo o resto, podendo ate superar as impressoes visiveis
        campanhas_visiveis = set(df["campanha"].unique())
        por_campanha_filtrado = {
            nome: valor for nome, valor in alcance_exato["por_campanha"].items() if nome in campanhas_visiveis
        }
        alcance_exato = {"total": sum(por_campanha_filtrado.values()), "por_campanha": por_campanha_filtrado}

    periodo_label = f"{data_ini.strftime('%d/%m/%Y')} — {data_fim.strftime('%d/%m/%Y')}"
    st.markdown(
        f'<div class="hero-row"><div>'
        f'<div class="kicker">Meta Ads · Relatório de campanha</div>'
        f'<div class="hero-title">Painel de Performance</div>'
        f'</div><div class="hero-meta">{fonte}<br/>Período <b>{periodo_label}</b></div></div>',
        unsafe_allow_html=True,
    )

    gasto_total = df["gasto"].sum()
    cliques_total = int(df["cliques"].sum())
    impressoes_total = int(df["impressoes"].sum())
    # alcance exato (consulta separada, sem duplicar gente entre dias) tem prioridade;
    # so cai no somatorio diario (aproximado) se aquela consulta falhar ou no modo demo
    alcance_total = alcance_exato["total"] if alcance_exato else int(df["alcance"].sum())

    # campanhas de alcance: o "resultado" e o proprio alcance - troca a soma diaria
    # (aproximada) pelo alcance exato por campanha, pra bater com a coluna Conversoes
    # da tabela em vez de ficar um numero levemente diferente
    campanhas_alcance = df.loc[df["eh_objetivo_alcance"], "campanha"].unique().tolist()
    conversoes_total = int(df.loc[~df["campanha"].isin(campanhas_alcance), "conversoes"].sum())
    if alcance_exato:
        por_campanha_exato = alcance_exato.get("por_campanha", {})
        conversoes_total += sum(por_campanha_exato.get(c, 0) for c in campanhas_alcance)
    else:
        conversoes_total += int(df.loc[df["campanha"].isin(campanhas_alcance), "conversoes"].sum())

    cpa = gasto_total / conversoes_total if conversoes_total else 0

    # controles de "o que considerar" no painel - desmarcar Gasto ou Conversoes tira
    # aquele cartao de KPI e a linha correspondente do grafico de Tendencia; marcar de
    # novo traz tudo de volta (nada e recalculado nem perdido, so escondido)
    mostrar_gasto = st.session_state.get("toggle_gasto", True)
    mostrar_conversoes = st.session_state.get("toggle_conversoes", True)

    kpis = [("Alcance", formatar_numero(alcance_total)), ("Impressões", formatar_numero(impressoes_total))]
    if mostrar_gasto:
        kpis.append(("Gasto Total", formatar_moeda(gasto_total)))
    if mostrar_conversoes:
        kpis.append(("Conversões", formatar_numero(conversoes_total)))
    if mostrar_gasto and mostrar_conversoes:
        kpis.append(("Custo por Resultado", formatar_moeda(cpa)))
    render_kpis(kpis)

    diario = df.groupby("data", as_index=False).agg(gasto=("gasto", "sum"), conversoes=("conversoes", "sum"))
    datas_fmt = diario["data"].dt.strftime("%d/%m").tolist()

    cpa_medio = cpa
    agrupado = df.groupby("campanha", as_index=False).agg(gasto=("gasto", "sum"), conversoes=("conversoes", "sum"))
    agrupado["cpa"] = (agrupado["gasto"] / agrupado["conversoes"].replace(0, pd.NA)).fillna(0)

    tab_tendencia, tab_funil, tab_campanhas, tab_tabela = st.tabs(
        ["Tendência", "Funil", "Campanhas", "Tabela completa"]
    )

    with tab_tendencia:
        chart_shell_start("Gasto e Conversões", "Evolução diária — desmarque uma métrica pra tirá-la do painel inteiro")
        col_tg1, col_tg2, _ = st.columns([1, 1.4, 5])
        with col_tg1:
            mostrar_gasto = st.toggle("Gasto", value=mostrar_gasto, key="toggle_gasto")
        with col_tg2:
            mostrar_conversoes = st.toggle("Conversões", value=mostrar_conversoes, key="toggle_conversoes")
        components.html(
            trend_and_conversions(
                datas_fmt,
                diario["gasto"].round(2).tolist(),
                diario["conversoes"].tolist(),
                theme,
                mostrar_gasto,
                mostrar_conversoes,
            ),
            height=352,
        )
        chart_shell_end()

    with tab_funil:
        chart_shell_start("Funil de Performance", "Do alcance à conversão — onde o público se perde")
        components.html(
            funnel_chart(impressoes_total, alcance_total, cliques_total, conversoes_total, theme), height=352
        )
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
        tabela = tabela_campanhas(df, alcance_exato)
        todas_colunas = list(tabela.columns)

        col_filtro, col_reset, _ = st.columns([1.3, 1.5, 3])
        with col_filtro:
            with st.popover("Ocultar colunas", use_container_width=True):
                st.caption("Desmarque o que não quer ver na tabela")
                ocultas = [
                    coluna
                    for coluna in todas_colunas
                    if coluna != "Campanha" and not st.checkbox(coluna, value=True, key=f"col_{coluna}")
                ]
        with col_reset:
            # a propria tabela tem um menu nativo (icone do olho no cabecalho da coluna)
            # que tambem esconde colunas, mas sem jeito nenhum de trazer de volta pela
            # interface - trocar a "key" reinicia esse estado interno da tabela do zero
            if st.button("↺ Restaurar tabela", key="btn_reset_tabela", type="tertiary"):
                st.session_state["tabela_reset"] = st.session_state.get("tabela_reset", 0) + 1
                st.rerun()

        colunas_visiveis = [c for c in todas_colunas if c not in ocultas]
        st.dataframe(
            tabela[colunas_visiveis],
            use_container_width=True,
            hide_index=True,
            key=f"grid_tabela_{st.session_state.get('tabela_reset', 0)}",
        )


if __name__ == "__main__":
    main()
