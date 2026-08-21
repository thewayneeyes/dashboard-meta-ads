"""Paleta e CSS global - identidade de agencia: neon, editorial, compacto (sem scroll)."""

THEMES = {
    "dark": {
        "page": "#07060d",
        "surface": "#0f0d1a",
        "surface_2": "#171327",
        "card": "rgba(23,19,39,0.72)",
        "card_hover": "rgba(32,26,54,0.88)",
        "border": "rgba(255,255,255,0.08)",
        "border_strong": "rgba(239,209,0,0.45)",
        "text_primary": "#ffffff",
        "text_secondary": "#a29ec2",
        "muted": "#736f8f",
        "gridline": "rgba(255,255,255,0.05)",
        "baseline": "rgba(255,255,255,0.12)",
        # amarelo da marca tambem nos botoes e na linha de Gasto do grafico (a pedido do
        # cliente) - accent_2 fica um preto/carvao pra dar profundidade ao degrade dos
        # botoes (amarelo -> preto), em vez de duas cores amarelas iguais
        "accent_1": "#efd100",
        "accent_2": "#1a1a1a",
        "accent_3": "#efd100",
        "series_blue": "#efd100",
        "series_aqua": "#2dd4bf",
        "series_pink": "#f0399b",
        "good": "#2dd4bf",
        "warning": "#fbbf24",
        "critical": "#f0399b",
        "glow_blue": "rgba(239,209,0,0.55)",
        "glow_aqua": "rgba(45,212,191,0.50)",
        "glow_pink": "rgba(240,57,155,0.50)",
        # marca da agencia (amarelo/preto) - usado em elementos decorativos de fonte e
        # layout (titulo, kicker, barra de destaque do KPI)
        "marca_amarelo": "#efd100",
        "marca_glow": "rgba(239,209,0,0.45)",
    },
    "light": {
        "page": "#faf8ff",
        "surface": "#ffffff",
        "surface_2": "#ffffff",
        "card": "rgba(255,255,255,0.80)",
        "card_hover": "#ffffff",
        "border": "rgba(30,15,60,0.09)",
        "border_strong": "rgba(184,134,11,0.45)",
        "text_primary": "#140b26",
        "text_secondary": "#5f5580",
        "muted": "#857da3",
        "gridline": "rgba(20,11,38,0.06)",
        "baseline": "rgba(20,11,38,0.15)",
        "accent_1": "#b8860b",
        "accent_2": "#141414",
        "accent_3": "#b8860b",
        "series_blue": "#b8860b",
        "series_aqua": "#0d9488",
        "series_pink": "#db2777",
        "good": "#0d9488",
        "warning": "#b45309",
        "critical": "#db2777",
        "glow_blue": "rgba(184,134,11,0.30)",
        "glow_aqua": "rgba(13,148,136,0.24)",
        "glow_pink": "rgba(219,39,119,0.24)",
        # amarelo puro da marca so aparece em elementos decorativos SEM texto em cima
        # (pontinho do kicker, sublinhado do titulo, barra do KPI, glow de fundo) -
        # exatamente como a propria logo da Vanti resolve isso (amarelo so no fundo
        # escuro; no fundo claro ela usa preto). Sem texto amarelo, pode usar a cor
        # crua da marca sem risco de ficar ilegivel.
        "marca_amarelo": "#efd100",
        "marca_glow": "rgba(239,209,0,0.35)",
    },
}


def get_palette(theme: str) -> dict:
    return THEMES.get(theme, THEMES["dark"])


def global_css(theme: str) -> str:
    p = get_palette(theme)
    return f"""
    <style>
    html, body, [class*="css"] {{
        font-family: -apple-system, "Segoe UI", system-ui, sans-serif;
    }}

    /* ---- compacta o layout: cabe tudo em uma tela, mesmo com barra de favoritos ocupando espaco ---- */
    [data-testid="stMainBlockContainer"] {{
        padding-top: clamp(0.6rem, 2vh, 1.2rem);
        padding-bottom: clamp(0.3rem, 1vh, 0.6rem);
        padding-left: clamp(1rem, 3vw, 2.6rem);
        padding-right: clamp(1rem, 3vw, 2.6rem);
        max-width: 100%;
        position: relative;
        z-index: 1;
    }}
    [data-testid="stVerticalBlock"] {{ gap: 0.4rem; }}
    [data-testid="stToolbar"], [data-testid="stDecoration"], footer {{ display: none !important; }}
    [data-testid="stHeader"] {{ background: transparent; height: 0; }}

    [data-testid="stAppViewContainer"] {{
        background: {p['page']};
    }}
    [data-testid="stAppViewContainer"]::before {{
        content: "";
        position: fixed;
        inset: 0;
        z-index: 0;
        pointer-events: none;
        background:
            radial-gradient(900px circle at 0% -10%, {p['glow_blue']}, transparent 55%),
            radial-gradient(700px circle at 100% 0%, {p['marca_glow']}, transparent 50%),
            radial-gradient(700px circle at 60% 110%, {p['glow_aqua']}, transparent 50%);
        opacity: 0.42;
        animation: drift 20s ease-in-out infinite alternate;
    }}
    @keyframes drift {{
        0%   {{ transform: translate3d(0,0,0) scale(1); }}
        100% {{ transform: translate3d(-2%, 2%, 0) scale(1.08); }}
    }}
    @media (prefers-reduced-motion: reduce) {{
        [data-testid="stAppViewContainer"]::before {{ animation: none; }}
    }}

    [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {{ display: none !important; }}
    .stApp, .stMarkdown, p, span, label {{ color: {p['text_primary']}; }}

    /* o cabecalho nativo do Streamlit usa z-index altissimo (~999990) e fica ancorado no
       topo da pagina mesmo escondido visualmente - avisos/toasts de conexao que ele mostra
       ocasionalmente podem competir pelo clique bem na regiao onde nossa barra de controles
       fica (perto do topo). Garantimos que nossa barra sempre vence essa disputa. */
    [data-testid="stHeader"] {{ pointer-events: none !important; }}
    [data-testid="stHeader"] * {{ pointer-events: none !important; }}

    /* ---- barra de controles do topo (discreta) ---- */
    .topbar-anchor {{ display: none; }}
    .st-key-topbar {{
        margin-bottom: 2px;
        position: relative;
        z-index: 1000000;
    }}
    .st-key-topbar [data-testid="stHorizontalBlock"] {{
        gap: 8px;
        align-items: center;
    }}
    /* botoes e selectbox: contorno tenue, mas o TEXTO fica sempre legivel (nao depende
       do hover para aparecer) - antes o texto ficava quase invisivel em repouso e so
       "acendia" no hover; como o Streamlit redesenha o botao a cada clique, o mouse
       perdia o :hover no instante do clique e o texto sumia de novo, parecendo bug.
       altura minima de 40px para a area clicavel real ficar confortavel. */
    .st-key-topbar button,
    .st-key-topbar [data-testid="stSelectbox"] .react-aria-ComboBox > div {{
        background: transparent !important;
        border: 1px solid {p['border']} !important;
        border-radius: 10px !important;
        min-height: 40px !important;
        height: 40px !important;
        color: {p['text_secondary']} !important;
        transition: border-color 180ms ease, background 180ms ease;
        user-select: none !important;
        -webkit-user-select: none !important;
        cursor: pointer !important;
    }}
    /* a palavra dentro do botao (ex: "Conexao") e texto normal, entao e SELECIONAVEL por
       padrao - um clique real de mouse sempre tem um micro-arrasto entre apertar/soltar,
       e o navegador interpreta isso como "selecionar o texto" em vez de "clicar no botao"
       quando o cursor esta exatamente em cima da palavra. Desativando a selecao aqui. */
    .st-key-topbar button *,
    .st-key-topbar [data-testid="stPopoverButton"] *,
    .stTabs [data-baseweb="tab"] * {{
        user-select: none !important;
        -webkit-user-select: none !important;
        pointer-events: none !important;
    }}
    /* toggle (Gasto/Conversoes): so tira a selecao de texto do rotulo, sem desativar
       pointer-events no input - esse widget usa o proprio elemento <input> pra detectar
       o clique internamente, entao "furar" ele pra baixo (como fizemos nos botoes)
       quebra o toggle inteiro em vez de consertar. */
    [data-testid="stCheckbox"] label {{
        user-select: none !important;
        -webkit-user-select: none !important;
    }}
    .st-key-topbar [data-testid="stPopoverButton"] {{
        background: transparent !important;
        background-color: transparent !important;
        border: 1px solid {p['border']} !important;
        border-radius: 10px !important;
        min-height: 40px !important;
        height: 40px !important;
        color: {p['text_secondary']} !important;
    }}
    .st-key-topbar [data-testid="stPopoverButton"]:hover {{
        background-color: {p['card']} !important;
        border-color: {p['border_strong']} !important;
        color: {p['text_primary']} !important;
    }}
    /* qualquer outro botao de popover fora da barra do topo (ex: "Ocultar colunas" na
       Tabela completa) - sem isso ele ficava preso no visual escuro padrao do Streamlit,
       com o texto quase invisivel no tema claro. */
    [data-testid="stPopoverButton"] {{
        background: {p['surface_2']} !important;
        border: 1px solid {p['border_strong']} !important;
        color: {p['text_primary']} !important;
    }}
    [data-testid="stPopoverButton"] * {{
        color: {p['text_primary']} !important;
        user-select: none !important;
        -webkit-user-select: none !important;
        pointer-events: none !important;
    }}
    [data-testid="stPopoverButton"]:hover {{
        background: {p['card_hover']} !important;
        border-color: {p['accent_1']} !important;
    }}
    .st-key-topbar button:hover,
    .st-key-topbar [data-testid="stSelectbox"] .react-aria-ComboBox > div:hover {{
        color: {p['text_primary']} !important;
        border-color: {p['border_strong']} !important;
        background: {p['card']} !important;
    }}
    .st-key-topbar button p,
    .st-key-topbar button div,
    .st-key-topbar input {{
        font-size: 11.5px !important;
        font-weight: 600 !important;
        letter-spacing: 0.04em;
        color: {p['text_secondary']} !important;
    }}
    .st-key-topbar button:hover p,
    .st-key-topbar button:hover div {{ color: {p['text_primary']} !important; }}
    .st-key-topbar input {{ height: 38px !important; }}
    .st-key-topbar svg {{ width: 14px; height: 14px; opacity: 0.6; }}
    .st-key-topbar [data-testid="stSelectbox"] label {{ display: none !important; }}
    [data-testid="stCaptionContainer"] {{ color: {p['muted']} !important; font-size: 12px; }}

    /* ---- header editorial ---- */
    .hero-row {{
        display: flex;
        align-items: flex-end;
        justify-content: space-between;
        gap: 20px;
        flex-wrap: wrap;
        border-bottom: 1px solid {p['border']};
        padding-bottom: clamp(6px, 1.4vh, 14px);
        margin-bottom: clamp(6px, 1.4vh, 14px);
    }}
    .kicker {{
        display: inline-flex;
        align-items: center;
        gap: 9px;
        font-size: 11px;
        font-weight: 800;
        letter-spacing: 0.22em;
        text-transform: uppercase;
        color: {p['text_secondary']};
        margin-bottom: 6px;
    }}
    .kicker::before {{
        content: "";
        width: 8px; height: 8px;
        border-radius: 50%;
        background: {p['marca_amarelo']};
        box-shadow: 0 0 0 0 {p['marca_glow']};
        animation: pulse 2.4s ease-out infinite;
    }}
    @keyframes pulse {{
        0%   {{ box-shadow: 0 0 0 0 {p['marca_glow']}; }}
        70%  {{ box-shadow: 0 0 0 10px rgba(0,0,0,0); }}
        100% {{ box-shadow: 0 0 0 0 rgba(0,0,0,0); }}
    }}
    .hero-title {{
        position: relative;
        font-size: clamp(24px, 3vw, 48px);
        font-weight: 900;
        line-height: 0.98;
        letter-spacing: -0.035em;
        margin: 0;
        text-transform: uppercase;
        color: {p['text_primary']};
    }}
    .hero-title::after {{
        content: "";
        position: absolute;
        left: 2px; right: 6%;
        bottom: -8px;
        height: 0.11em;
        min-height: 4px;
        border-radius: 3px;
        background: {p['marca_amarelo']};
    }}
    .hero-meta {{
        text-align: right;
        color: {p['text_secondary']};
        font-size: 12px;
        line-height: 1.7;
    }}
    .hero-meta b {{ color: {p['text_primary']}; font-weight: 700; }}
    /* logo na barra de controles do topo - alinhada com os outros campos (40px de altura) */
    .st-key-topbar .topbar-logo {{
        display: block;
        height: 34px;
        width: auto;
        margin-top: 3px;
    }}

    /* ---- KPI row ---- */
    .kpi-grid {{
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 10px;
        margin-bottom: clamp(6px, 1.4vh, 14px);
    }}
    @media (max-width: 1200px) {{ .kpi-grid {{ grid-template-columns: repeat(3, 1fr); }} }}
    @media (max-width: 760px)  {{ .kpi-grid {{ grid-template-columns: repeat(2, 1fr); }} }}

    .kpi-card {{
        background: {p['card']};
        backdrop-filter: blur(18px);
        -webkit-backdrop-filter: blur(18px);
        border: 1px solid {p['border']};
        border-radius: 16px;
        padding: clamp(10px, 1.6vh, 15px) 14px clamp(10px, 1.6vh, 15px) 14px;
        position: relative;
        overflow: hidden;
        transition: transform 240ms cubic-bezier(.2,.8,.2,1), box-shadow 240ms ease, border-color 240ms ease, background 240ms ease;
    }}
    .kpi-card::after {{
        content: "";
        position: absolute;
        top: -55%; right: -35%;
        width: 150px; height: 150px;
        background: radial-gradient(circle, {p['glow_blue']}, transparent 68%);
        opacity: 0.55;
        pointer-events: none;
        transition: opacity 240ms ease;
    }}
    .kpi-card:hover {{
        transform: translateY(-4px);
        border-color: {p['border_strong']};
        background: {p['card_hover']};
        box-shadow: 0 18px 44px -14px {p['glow_blue']};
    }}
    .kpi-card:hover::after {{ opacity: 1; }}
    .kpi-accent {{
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 2px;
        background: linear-gradient(90deg, {p['text_primary']}, {p['marca_amarelo']});
    }}
    .kpi-label {{
        color: {p['text_secondary']};
        font-size: 10.5px;
        font-weight: 800;
        letter-spacing: 0.13em;
        text-transform: uppercase;
        margin-bottom: clamp(4px, 1vh, 9px);
        position: relative; z-index: 1;
    }}
    .kpi-value {{
        font-size: clamp(18px, 1.6vw, 27px);
        font-weight: 900;
        font-variant-numeric: tabular-nums;
        line-height: 1;
        letter-spacing: -0.025em;
        color: {p['text_primary']};
        position: relative; z-index: 1;
    }}

    /* ---- tabs ----
       o Streamlit trocou a estrutura interna das abas (nao usa mais data-baseweb) -
       os seletores agora miram role="tab"/"tablist", que sao estaveis (vem do padrao
       de acessibilidade ARIA, nao mudam entre versoes do componente). */
    .stTabs [role="tablist"] {{
        gap: 5px;
        background: {p['card']};
        border: 1px solid {p['border']};
        border-radius: 13px;
        padding: 5px;
        backdrop-filter: blur(18px);
        width: fit-content;
    }}
    .stTabs [role="tab"] {{
        height: 40px;
        border-radius: 9px;
        color: {p['text_secondary']};
        font-weight: 700;
        font-size: 13px;
        letter-spacing: 0.02em;
        padding: 0 26px;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: color 180ms ease, background 180ms ease;
    }}
    .stTabs [role="tab"] p {{
        padding: 0 2px;
        white-space: nowrap;
    }}
    .stTabs [role="tab"]:hover {{ color: {p['text_primary']}; }}
    .stTabs [role="tab"][aria-selected="true"] {{
        background: {p['marca_amarelo']};
        color: #14110a !important;
        box-shadow: 0 6px 20px -7px {p['marca_glow']};
    }}
    .stTabs [role="tabpanel"] {{ padding-top: clamp(4px, 1vh, 10px); }}

    /* ---- chart shell ---- */
    .chart-shell {{
        background: {p['card']};
        backdrop-filter: blur(18px);
        -webkit-backdrop-filter: blur(18px);
        border: 1px solid {p['border']};
        border-radius: 18px;
        padding: 2px;
    }}
    .chart-head {{
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 16px;
        flex-wrap: wrap;
        padding: clamp(8px, 1.4vh, 13px) 18px clamp(5px, 1vh, 9px) 18px;
    }}
    .chart-title {{
        color: {p['text_primary']};
        font-size: 15px;
        font-weight: 800;
        letter-spacing: -0.01em;
    }}
    .chart-subtitle {{
        color: {p['muted']};
        font-size: 12px;
    }}

    [data-testid="stDataFrame"] {{
        border-radius: 14px;
        overflow: hidden;
        border: 1px solid {p['border']};
    }}
    /* ---- modal de conexao: segue o tema atual ---- */
    [data-testid="stDialog"] [role="dialog"],
    [data-testid="stDialog"] > div > div {{
        background: {p['surface_2']} !important;
        border: 1px solid {p['border']} !important;
        border-radius: 18px !important;
        box-shadow: 0 30px 70px -20px rgba(0,0,0,0.55) !important;
    }}
    [data-testid="stDialog"] [role="dialog"] h1,
    [data-testid="stDialog"] [role="dialog"] h2,
    [data-testid="stDialog"] [role="dialog"] h3,
    [data-testid="stDialog"] [role="dialog"] p,
    [data-testid="stDialog"] [role="dialog"] label,
    [data-testid="stDialog"] [role="dialog"] li {{
        color: {p['text_primary']} !important;
    }}
    [data-testid="stDialog"] [role="dialog"] [data-testid="stWidgetLabel"] p {{
        color: {p['text_secondary']} !important;
        font-size: 12px !important;
        font-weight: 700 !important;
        letter-spacing: 0.06em;
        text-transform: uppercase;
    }}
    [data-testid="stDialog"] [role="dialog"] input {{
        color: {p['text_primary']} !important;
        background: {p['surface']} !important;
    }}
    /* mesmo problema de selecao de texto "engolindo" o clique, resolvido igual aos
       botoes do topo: nenhum filho do botao intercepta o clique. */
    [data-testid="stDialog"] [role="dialog"] button * {{
        user-select: none !important;
        -webkit-user-select: none !important;
        pointer-events: none !important;
    }}
    [data-testid="stDialog"] [role="dialog"] button[kind="primary"],
    [data-testid="stDialog"] [role="dialog"] button[kind="primary"] p {{
        background: {p['marca_amarelo']} !important;
        color: #14110a !important;
        border: none !important;
    }}
    [data-testid="stDialog"] [role="dialog"] button[kind="primary"] p {{
        background: none !important;
    }}
    /* botao secundario ("Testar conexao") */
    [data-testid="stDialog"] [role="dialog"] button[kind="secondary"] {{
        background: {p['surface']} !important;
        border: 1px solid {p['border_strong']} !important;
    }}
    [data-testid="stDialog"] [role="dialog"] button[kind="secondary"] p,
    [data-testid="stDialog"] [role="dialog"] button[kind="secondary"] div {{
        color: {p['text_primary']} !important;
    }}
    /* select / combobox (ex: "Conta do cliente") */
    [data-testid="stDialog"] [role="dialog"] input {{
        background: {p['surface']} !important;
        border-color: {p['border_strong']} !important;
    }}
    /* menu suspenso do select: renderiza em portal fora do dialog (react-aria) */
    [role="listbox"] {{
        background: {p['surface_2']} !important;
        border: 1px solid {p['border_strong']} !important;
        border-radius: 12px !important;
        box-shadow: 0 20px 50px -14px rgba(0,0,0,0.5) !important;
    }}
    div:has(> [role="listbox"]) {{
        background: {p['surface_2']} !important;
    }}
    [role="option"] {{
        background: transparent !important;
        color: {p['text_primary']} !important;
        min-height: 40px !important;
        padding: 10px 14px !important;
        display: flex !important;
        align-items: center !important;
        font-size: 14px !important;
        cursor: pointer;
        box-sizing: border-box !important;
    }}
    [role="option"]:hover,
    [role="option"][aria-selected="true"] {{
        background: {p['card_hover']} !important;
        color: {p['text_primary']} !important;
    }}

    /* bloco de codigo (ex: link do cliente em Conexao) sempre tem fundo escuro por
       padrao do Streamlit, mas a regra global de cor do span pintava o texto de dentro
       dele com a cor do tema claro (quase preto) - texto escuro em cima de fundo escuro
       ficava invisivel. Aqui fixamos o texto do codigo sempre claro, ja que o fundo dele
       nunca muda com o tema. */
    [data-testid="stCode"] * {{
        color: #e7e6ee !important;
    }}

    /* popover (ex: "Datas") renderiza em portal fora do fluxo normal e nao herdava o
       tema - ficava sempre no visual escuro padrao do Streamlit mesmo no tema claro. */
    [data-testid="stPopoverBody"] {{
        background: {p['surface_2']} !important;
        border: 1px solid {p['border_strong']} !important;
        border-radius: 14px !important;
        box-shadow: 0 20px 50px -14px rgba(0,0,0,0.5) !important;
    }}
    [data-testid="stPopoverBody"] * {{
        color: {p['text_primary']} !important;
    }}
    [data-testid="stPopoverBody"] [data-testid="stWidgetLabel"] p {{
        color: {p['text_secondary']} !important;
        font-size: 12px !important;
        font-weight: 700 !important;
    }}
    [data-testid="stPopoverBody"] input {{
        background: {p['surface']} !important;
        border-color: {p['border_strong']} !important;
        color: {p['text_primary']} !important;
    }}
    [data-testid="stPopoverBody"] input::placeholder {{
        color: {p['muted']} !important;
        opacity: 1 !important;
    }}
    /* caixa do combobox/multiselect (o campo inteiro, nao so o <input> de digitar) */
    [data-testid="stPopoverBody"] [data-baseweb="select"],
    [data-testid="stPopoverBody"] [data-testid="stMultiSelect"] > div > div {{
        background: {p['surface']} !important;
        border-color: {p['border_strong']} !important;
    }}
    /* calendario que abre ao clicar no campo de data */
    [data-baseweb="calendar"] {{
        background: {p['surface_2']} !important;
    }}
    [data-baseweb="calendar"] * {{
        color: {p['text_primary']} !important;
    }}

    iframe {{ display: block; }}
    /* graficos: altura acompanha a janela em vez do atributo height fixo passado ao
       components.html - evita rolagem quando a barra de favoritos/abas reduz a tela.
       (a div .chart-shell nao chega a envolver o iframe no DOM real, entao miramos
       direto no container que o Streamlit usa para todo st.components.v1.html) */
    [data-testid="stTabPanel"] [data-testid="stIFrame"] {{
        height: clamp(230px, 40vh, 352px) !important;
    }}
    </style>
    """
