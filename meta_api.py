"""Cliente simples para a Meta Marketing API (leitura de insights)."""
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

GRAPH_API_VERSION = "v21.0"
BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

FIELDS = (
    "campaign_id,campaign_name,spend,impressions,reach,clicks,ctr,cpc,cpm,actions,"
    "optimization_goal,instagram_profile_visits,date_start,date_stop"
)

# "Veiculacao" no Gerenciador de Anuncios = effective_status da campanha. So existe no
# endpoint de campanhas (/campaigns), nao no de insights - por isso precisa de uma
# segunda consulta separada, unida pelo campaign_id.
# Termos identicos aos que a coluna "Veiculacao" mostra no Gerenciador de Anuncios em
# PT-BR - pedido explicito do cliente pra nao inventar rotulo proprio (ex: nao usar
# "Pausado" e sim "Desativado", que e a palavra que a Meta usa).
STATUS_PT = {
    "ACTIVE": "Ativo",
    "PAUSED": "Desativado",
    "CAMPAIGN_PAUSED": "Desativado",
    "ADSET_PAUSED": "Desativado",
    "IN_PROCESS": "Em processamento",
    "WITH_ISSUES": "Erro no pagamento",
    "PENDING_REVIEW": "Em análise",
    "DISAPPROVED": "Reprovado",
    "PREAPPROVED": "Pré-aprovado",
    "PENDING_BILLING_INFO": "Erro no pagamento",
    "ARCHIVED": "Arquivada",
    "DELETED": "Excluída",
}

# Cada campanha otimiza para um objetivo diferente (venda, lead, conversa no whatsapp,
# clique, etc.) - o "resultado" tem que ser o MESMO numero que aparece na coluna
# "Resultados" do Gerenciador de Anuncios pra aquele objetivo. Cada lista abaixo e uma
# ORDEM DE PRIORIDADE (pega o primeiro action_type que existir nos dados, NAO soma
# todos - somar tipos diferentes gerava numero maior que o real).
#
# Nota sobre REPLIES: campanhas de "resposta a mensagem" no Ads Manager mostram como
# resultado principal "Conversas iniciadas por mensagem", nao "Respostas" - confirmado
# comparando com uma campanha real (objetivo tecnico REPLIES, coluna Resultados = 392 =
# onsite_conversion.messaging_conversation_started_7d; nosso calculo antigo pegava
# messaging_first_reply = 349, que e uma metrica diferente).
METAS_POR_OBJETIVO = {
    "OFFSITE_CONVERSIONS": ["omni_purchase", "offsite_conversion.fb_pixel_purchase", "purchase"],
    "VALUE": ["omni_purchase", "offsite_conversion.fb_pixel_purchase", "purchase"],
    "LEAD_GENERATION": ["onsite_conversion.lead_grouped", "lead"],
    "QUALITY_LEAD": ["onsite_conversion.lead_grouped", "lead"],
    "CONVERSATIONS": ["onsite_conversion.messaging_conversation_started_7d"],
    "REPLIES": ["onsite_conversion.messaging_conversation_started_7d"],
    "LINK_CLICKS": ["link_click"],
    "LANDING_PAGE_VIEWS": ["landing_page_view"],
    "POST_ENGAGEMENT": ["post_engagement"],
    "PAGE_LIKES": ["like"],
    "APP_INSTALLS": ["omni_app_install", "mobile_app_install"],
    "THRUPLAY": ["video_view"],
    "VIDEO_VIEWS": ["video_view"],
}

# objetivos de alcance/exibicao pura: no Gerenciador de Anuncios, a coluna "Resultados"
# dessas campanhas E o proprio alcance (ex: "56.575 Alcance") - nao existe uma acao de
# conversao separada, entao repetimos o alcance na coluna Conversoes pra bater 1:1.
OBJETIVOS_DE_ALCANCE = {"REACH", "IMPRESSIONS", "BRAND_AWARENESS"}

# Usado SO quando o optimization_goal nao esta mapeado acima (objetivo desconhecido/novo).
# Tambem em ordem de prioridade - pega o primeiro que existir, nao soma.
METAS_PADRAO = [
    "onsite_conversion.lead_grouped",
    "lead",
    "omni_purchase",
    "offsite_conversion.fb_pixel_purchase",
    "purchase",
    "complete_registration",
    "onsite_conversion.messaging_conversation_started_7d",
]


class MetaAPIError(Exception):
    pass


def _sessao() -> requests.Session:
    """Sessao HTTP com retry automatico - a primeira conexao do processo no Windows
    as vezes trava (antivirus/Defender inspecionando o primeiro acesso de rede),
    entao tentamos de novo sozinhos em vez de estourar erro pro usuario."""
    sessao = requests.Session()
    retry = Retry(
        total=4,
        connect=4,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    sessao.mount("https://", adapter)
    sessao.mount("http://", adapter)
    return sessao


_session = _sessao()


def buscar_insights(ad_account_id: str, access_token: str, data_inicio: str, data_fim: str) -> pd.DataFrame:
    """Busca insights diarios por campanha de uma conta de anuncios.

    ad_account_id deve estar no formato 'act_1234567890'.
    """
    if not ad_account_id.startswith("act_"):
        ad_account_id = f"act_{ad_account_id}"

    url = f"{BASE_URL}/{ad_account_id}/insights"
    params = {
        "level": "campaign",
        "fields": FIELDS,
        "time_range": f'{{"since":"{data_inicio}","until":"{data_fim}"}}',
        "time_increment": 1,
        # mesma janela de atribuicao padrao usada pelo Gerenciador de Anuncios,
        # para os numeros baterem com o que a agencia ja ve la
        "action_attribution_windows": "7d_click,1d_view",
        "access_token": access_token,
        "limit": 500,
    }

    registros = []
    while url:
        try:
            resp = _session.get(url, params=params, timeout=30)
        except requests.exceptions.RequestException as e:
            raise MetaAPIError(
                "Não foi possível conectar à Meta API (falha de rede). Tente novamente em alguns segundos."
            ) from e
        payload = resp.json()

        if "error" in payload:
            erro = payload["error"]
            raise MetaAPIError(erro.get("message", "Erro desconhecido na Meta API"))

        registros.extend(payload.get("data", []))

        proxima = payload.get("paging", {}).get("next")
        url = proxima
        params = None  # paginacao ja vem com query string completa

    if not registros:
        return pd.DataFrame()

    df = pd.DataFrame(registros)
    df["gasto"] = pd.to_numeric(df.get("spend", 0), errors="coerce").fillna(0)
    df["impressoes"] = pd.to_numeric(df.get("impressions", 0), errors="coerce").fillna(0).astype(int)
    # alcance (pessoas unicas) nao e estritamente somavel entre dias diferentes (a mesma
    # pessoa alcancada em dois dias conta 2x na soma) - e uma aproximacao comum em
    # dashboards simples, mas por isso o alcance total pode vir levemente maior que o
    # alcance "real" do periodo inteiro que o Gerenciador de Anuncios mostraria.
    df["alcance"] = pd.to_numeric(df.get("reach", 0), errors="coerce").fillna(0).astype(int)
    df["cliques"] = pd.to_numeric(df.get("clicks", 0), errors="coerce").fillna(0).astype(int)
    df["data"] = pd.to_datetime(df["date_start"])
    df["campanha"] = df["campaign_name"]

    def _valor_da_acao(actions, action_type):
        if not isinstance(actions, list):
            return 0
        for a in actions:
            if a.get("action_type") == action_type:
                return int(float(a.get("value", 0)))
        return 0

    def _primeiro_que_existir(actions, tipos_em_ordem):
        """Pega o valor do PRIMEIRO action_type da lista que aparecer nos dados -
        nao soma varios tipos juntos (isso inflaria o numero alem do que o Gerenciador
        de Anuncios mostra, ja que tipos diferentes podem se sobrepor)."""
        for tipo in tipos_em_ordem:
            valor = _valor_da_acao(actions, tipo)
            if valor > 0:
                return valor
        return 0

    def extrair_conversoes(row):
        actions = row.get("actions")
        objetivo = row.get("optimization_goal")

        if objetivo in OBJETIVOS_DE_ALCANCE:
            # campanha de alcance/exibicao: o "resultado" e o proprio alcance
            return int(row.get("alcance") or 0)

        if objetivo in METAS_POR_OBJETIVO:
            valor = _primeiro_que_existir(actions, METAS_POR_OBJETIVO[objetivo])
            if valor > 0:
                return valor

        # "Visitas ao perfil do Instagram" e um campo dedicado da API, fora do array
        # "actions" - aparece em campanhas de trafego/engajamento sem objetivo mapeado
        # (confirmado comparando com o Gerenciador de Anuncios: campo instagram_profile_visits
        # bate com o numero da coluna Resultados, enquanto nenhum action_type batia).
        visitas_perfil = int(float(row.get("instagram_profile_visits") or 0))
        if visitas_perfil > 0:
            return visitas_perfil

        # objetivo desconhecido/sem nenhum dos anteriores: tenta o conjunto padrao
        return _primeiro_que_existir(actions, METAS_PADRAO)

    if "optimization_goal" not in df.columns:
        df["optimization_goal"] = None
    df["conversoes"] = df.apply(extrair_conversoes, axis=1)
    # marca quais campanhas tem o alcance como "resultado" - usado depois pra sincronizar
    # a coluna Conversoes com o alcance EXATO (sem a duplicacao entre dias que a soma
    # diaria causa), em vez de deixar as duas colunas com numeros ligeiramente diferentes
    df["eh_objetivo_alcance"] = df["optimization_goal"].isin(OBJETIVOS_DE_ALCANCE)

    df["ctr"] = (df["cliques"] / df["impressoes"].replace(0, pd.NA) * 100).fillna(0)
    df["cpc"] = (df["gasto"] / df["cliques"].replace(0, pd.NA)).fillna(0)
    df["cpm"] = (df["gasto"] / df["impressoes"].replace(0, pd.NA) * 1000).fillna(0)
    df["cpa"] = (df["gasto"] / df["conversoes"].replace(0, pd.NA)).fillna(0)

    # "veiculacao" real de cada campanha (ativa, pausada, etc) - so da pra saber
    # consultando o endpoint de campanhas, o de insights nao traz esse campo
    status_por_id = buscar_status_campanhas(ad_account_id, access_token)
    df["status"] = df.get("campaign_id", "").map(status_por_id).fillna("Desconhecido")

    return df[
        [
            "data", "campanha", "status", "gasto", "impressoes", "alcance", "cliques",
            "conversoes", "ctr", "cpc", "cpm", "cpa", "eh_objetivo_alcance",
        ]
    ]


def listar_campanhas(ad_account_id: str, access_token: str) -> list[dict]:
    """Todas as campanhas que ja existiram na conta, com nome e status - independente de
    ter tido gasto no periodo selecionado. Usado no filtro de Campanhas: a agencia
    precisa ver (e poder excluir) uma campanha pausada ha tempos, nao so as que tiveram
    atividade recente (essas o /insights ja nem devolve)."""
    if not ad_account_id.startswith("act_"):
        ad_account_id = f"act_{ad_account_id}"

    url = f"{BASE_URL}/{ad_account_id}/campaigns"
    params = {"fields": "id,name,effective_status", "access_token": access_token, "limit": 500}

    campanhas = []
    while url:
        try:
            resp = _session.get(url, params=params, timeout=30)
        except requests.exceptions.RequestException as e:
            raise MetaAPIError(
                "Não foi possível conectar à Meta API (falha de rede). Tente novamente em alguns segundos."
            ) from e
        payload = resp.json()
        if "error" in payload:
            raise MetaAPIError(payload["error"].get("message", "Erro ao listar campanhas"))
        for row in payload.get("data", []):
            status_bruto = row.get("effective_status", "")
            campanhas.append(
                {
                    "id": row.get("id"),
                    "nome": row.get("name", ""),
                    "status": STATUS_PT.get(status_bruto, status_bruto.title() or "Desconhecido"),
                }
            )
        url = payload.get("paging", {}).get("next")
        params = None

    campanhas.sort(key=lambda c: (c["status"] != "Ativo", c["nome"].lower()))
    return campanhas


def buscar_status_campanhas(ad_account_id: str, access_token: str) -> dict:
    """Status de veiculacao (ativa, pausada, em revisao, etc) de cada campanha da conta -
    campo que so existe no endpoint de campanhas, nao no de insights."""
    if not ad_account_id.startswith("act_"):
        ad_account_id = f"act_{ad_account_id}"

    url = f"{BASE_URL}/{ad_account_id}/campaigns"
    params = {"fields": "id,effective_status", "access_token": access_token, "limit": 500}

    status_por_id = {}
    while url:
        try:
            resp = _session.get(url, params=params, timeout=30)
        except requests.exceptions.RequestException:
            break  # sem status disponivel: as campanhas ficam como "Desconhecido"
        payload = resp.json()
        if "error" in payload:
            break
        for row in payload.get("data", []):
            status_bruto = row.get("effective_status", "")
            status_por_id[row.get("id")] = STATUS_PT.get(status_bruto, status_bruto.title() or "Desconhecido")
        url = payload.get("paging", {}).get("next")
        params = None

    return status_por_id


def buscar_alcance_exato(ad_account_id: str, access_token: str, data_inicio: str, data_fim: str) -> dict:
    """Alcance (pessoas unicas) do periodo inteiro, igual ao numero que aparece no
    Gerenciador de Anuncios - sem quebrar por dia, entao sem duplicar gente que foi
    alcancada em mais de um dia (o que aconteceria se so somassemos os dias).

    Retorna {"total": int, "por_campanha": {nome_campanha: int}}.
    """
    if not ad_account_id.startswith("act_"):
        ad_account_id = f"act_{ad_account_id}"

    url = f"{BASE_URL}/{ad_account_id}/insights"
    params = {
        "level": "campaign",
        "fields": "campaign_name,reach",
        "time_range": f'{{"since":"{data_inicio}","until":"{data_fim}"}}',
        # sem time_increment: a Meta calcula o alcance unico do periodo inteiro de uma vez,
        # em vez de um valor por dia que precisaria ser somado (e duplicaria pessoas)
        "access_token": access_token,
        "limit": 500,
    }

    try:
        resp = _session.get(url, params=params, timeout=30)
    except requests.exceptions.RequestException as e:
        raise MetaAPIError(
            "Não foi possível conectar à Meta API (falha de rede). Tente novamente em alguns segundos."
        ) from e

    payload = resp.json()
    if "error" in payload:
        raise MetaAPIError(payload["error"].get("message", "Erro ao buscar alcance"))

    por_campanha = {}
    for row in payload.get("data", []):
        nome = row.get("campaign_name", "")
        alcance = int(float(row.get("reach", 0) or 0))
        por_campanha[nome] = por_campanha.get(nome, 0) + alcance

    # alcance total da conta tambem e um pedido separado - o alcance de duas campanhas
    # nao e somavel entre si (a mesma pessoa pode ter visto anuncios de ambas), entao o
    # alcance "da conta" e sempre <= soma do alcance de cada campanha isolada
    params_conta = dict(params)
    params_conta["level"] = "account"
    params_conta["fields"] = "reach"
    try:
        resp_conta = _session.get(url, params=params_conta, timeout=30)
        payload_conta = resp_conta.json()
        dados_conta = payload_conta.get("data", [])
        total = int(float(dados_conta[0].get("reach", 0))) if dados_conta else sum(por_campanha.values())
    except Exception:
        total = sum(por_campanha.values())

    return {"total": total, "por_campanha": por_campanha}


def listar_contas(access_token: str) -> list[dict]:
    """Lista as contas de anuncios que o token enxerga (para o seletor de cliente)."""
    url = f"{BASE_URL}/me/adaccounts"
    params = {"fields": "id,name,account_status", "limit": 200, "access_token": access_token}

    contas = []
    while url:
        try:
            resp = _session.get(url, params=params, timeout=20)
        except requests.exceptions.RequestException as e:
            raise MetaAPIError(
                "Não foi possível conectar à Meta API (falha de rede). Tente novamente em alguns segundos."
            ) from e
        payload = resp.json()

        if "error" in payload:
            raise MetaAPIError(payload["error"].get("message", "Erro ao listar contas de anúncio"))

        contas.extend(payload.get("data", []))
        url = payload.get("paging", {}).get("next")
        params = None

    # account_status: 1 = ativa. Ordena ativas primeiro, depois por nome.
    contas.sort(key=lambda c: (c.get("account_status") != 1, c.get("name", "").lower()))
    return contas


def testar_token(ad_account_id: str, access_token: str) -> tuple[bool, str]:
    """Testa se o token e a conta sao validos. Retorna (ok, mensagem)."""
    if not ad_account_id.startswith("act_"):
        ad_account_id = f"act_{ad_account_id}"

    url = f"{BASE_URL}/{ad_account_id}"
    try:
        resp = _session.get(url, params={"fields": "name,account_status", "access_token": access_token}, timeout=15)
    except requests.exceptions.RequestException:
        return False, "Não foi possível conectar à Meta API (falha de rede). Tente novamente em alguns segundos."
    payload = resp.json()

    if "error" in payload:
        return False, payload["error"].get("message", "Token ou conta invalidos")

    nome = payload.get("name", "conta sem nome")
    return True, f"Conectado a conta: {nome}"
