"""Cliente simples para a Meta Marketing API (leitura de insights)."""
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

GRAPH_API_VERSION = "v21.0"
BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

FIELDS = "campaign_name,spend,impressions,clicks,ctr,cpc,cpm,actions,optimization_goal,date_start,date_stop"

# Cada campanha otimiza para um objetivo diferente (venda, lead, conversa no whatsapp,
# clique, etc.) - o "resultado" tem que ser contado de acordo com esse objetivo, igual
# o proprio Gerenciador de Anuncios faz. Sem isso, campanhas de mensagem/engajamento
# aparecem com 0 conversoes mesmo estando ativas e performando bem.
METAS_POR_OBJETIVO = {
    "OFFSITE_CONVERSIONS": ["offsite_conversion.fb_pixel_purchase", "purchase", "omni_purchase"],
    "VALUE": ["offsite_conversion.fb_pixel_purchase", "purchase", "omni_purchase"],
    "LEAD_GENERATION": ["lead", "onsite_conversion.lead_grouped"],
    "QUALITY_LEAD": ["lead", "onsite_conversion.lead_grouped"],
    "CONVERSATIONS": [
        "onsite_conversion.messaging_conversation_started_7d",
        "onsite_conversion.total_messaging_connection",
    ],
    "REPLIES": ["onsite_conversion.messaging_first_reply"],
    "LINK_CLICKS": ["link_click"],
    "LANDING_PAGE_VIEWS": ["landing_page_view"],
    "POST_ENGAGEMENT": ["post_engagement"],
    "PAGE_LIKES": ["like"],
    "APP_INSTALLS": ["mobile_app_install", "omni_app_install"],
    "THRUPLAY": ["video_view"],
    "VIDEO_VIEWS": ["video_view"],
}

# Usado quando o objetivo nao esta mapeado acima, ou quando o mapeado nao bate com
# nenhum action_type retornado (ex: relatorio agregando varios conjuntos de anuncio
# com objetivos diferentes sob a mesma campanha).
METAS_PADRAO = {
    "lead",
    "purchase",
    "omni_purchase",
    "complete_registration",
    "offsite_conversion.fb_pixel_purchase",
    "onsite_conversion.messaging_conversation_started_7d",
}


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
    df["cliques"] = pd.to_numeric(df.get("clicks", 0), errors="coerce").fillna(0).astype(int)
    df["data"] = pd.to_datetime(df["date_start"])
    df["campanha"] = df["campaign_name"]

    def _somar(actions, tipos):
        if not isinstance(actions, list):
            return 0
        return sum(int(float(a.get("value", 0))) for a in actions if a.get("action_type") in tipos)

    def extrair_conversoes(row):
        actions = row.get("actions")
        objetivo = row.get("optimization_goal")
        tipos_do_objetivo = METAS_POR_OBJETIVO.get(objetivo)

        if tipos_do_objetivo:
            total = _somar(actions, tipos_do_objetivo)
            if total > 0:
                return total

        # objetivo nao mapeado (ou mapeado mas sem esse action_type nos dados): usa o conjunto padrao
        return _somar(actions, METAS_PADRAO)

    if "optimization_goal" not in df.columns:
        df["optimization_goal"] = None
    df["conversoes"] = df.apply(extrair_conversoes, axis=1)

    df["ctr"] = (df["cliques"] / df["impressoes"].replace(0, pd.NA) * 100).fillna(0)
    df["cpc"] = (df["gasto"] / df["cliques"].replace(0, pd.NA)).fillna(0)
    df["cpm"] = (df["gasto"] / df["impressoes"].replace(0, pd.NA) * 1000).fillna(0)
    df["cpa"] = (df["gasto"] / df["conversoes"].replace(0, pd.NA)).fillna(0)
    df["status"] = "Ativo"

    return df[["data", "campanha", "status", "gasto", "impressoes", "cliques", "conversoes", "ctr", "cpc", "cpm", "cpa"]]


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
