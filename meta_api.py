"""Cliente simples para a Meta Marketing API (leitura de insights)."""
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

GRAPH_API_VERSION = "v21.0"
BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

FIELDS = "campaign_name,spend,impressions,clicks,ctr,cpc,cpm,actions,date_start,date_stop"


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

    def extrair_conversoes(actions):
        if not isinstance(actions, list):
            return 0
        alvo = {"lead", "purchase", "complete_registration", "offsite_conversion.fb_pixel_purchase"}
        total = sum(int(float(a.get("value", 0))) for a in actions if a.get("action_type") in alvo)
        return total

    df["conversoes"] = df.get("actions", pd.Series([[]] * len(df))).apply(extrair_conversoes)

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
