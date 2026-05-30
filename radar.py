from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import feedparser
import pandas as pd
import random
import re
import os
import html
from datetime import datetime


# =========================================================
# RADAR CINEMATOGRÁFICO PROFISSIONAL SEM RASTROS - V4.2
# =========================================================

ANO_ATUAL = datetime.now().year

PASTA_RESULTADOS = "resultados"
CSV_SAIDA = os.path.join(PASTA_RESULTADOS, "casos_cinematicos.csv")
PDF_SAIDA = os.path.join(PASTA_RESULTADOS, "dossie_cinematografico.pdf")

RSS_FEEDS = [
    "https://www.reddit.com/r/UnresolvedMysteries/.rss",
    "https://www.reddit.com/r/MissingPersons/.rss",
    "https://www.reddit.com/r/TrueCrime/.rss",
    "https://www.reddit.com/r/UnsolvedMysteries/.rss",
]

USER_AGENT = "SemRastrosRadar/4.2"

COLUNAS = [
    "Caso",
    "Resumo Original",
    "Score",
    "Potencial Documental",
    "Relevância para Sem Rastros",
    "Classificação",
    "Tipo de Caso",
    "Uso Recomendado",
    "Decisão Editorial",
    "Ano do Caso",
    "Idade do Caso",
    "Status Detectado",
    "Segurança da Pauta",
    "Elementos Detectados",
    "Motivo Editorial",
    "Hook",
    "Link",
]


# =========================================================
# LIMPEZA DE TEXTO
# =========================================================

def limpar_html(texto):
    texto = html.unescape(str(texto or ""))
    texto = re.sub(r"<[^>]+>", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()

    texto = re.sub(
        r"\s*submitted by\s*/u/.*$",
        "",
        texto,
        flags=re.IGNORECASE
    ).strip()

    texto = re.sub(
        r"\s*\[link\]\s*\[comments\]\s*$",
        "",
        texto,
        flags=re.IGNORECASE
    ).strip()

    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def seguro_pdf(texto):
    return html.escape(str(texto or ""))


def normalizar(texto):
    return limpar_html(texto).lower()


def contem(texto, termo):
    texto = normalizar(texto)
    termo = termo.lower().strip()
    padrao = r"(?<!\w)" + re.escape(termo).replace(r"\ ", r"\s+") + r"(?!\w)"
    return re.search(padrao, texto, flags=re.IGNORECASE) is not None


def resumo_inutil(resumo):
    resumo = limpar_html(resumo)

    if not resumo:
        return True

    texto = resumo.lower()
    texto = texto.replace("submitted by", " ")
    texto = texto.replace("[link]", " ")
    texto = texto.replace("[comments]", " ")
    texto = re.sub(r"[^a-zA-Z0-9À-ÿ]+", " ", texto).strip()

    return len(texto) < 120


def titulo_meta_ou_inutil(titulo):
    titulo = normalizar(titulo)

    bloqueios = [
        "megathread",
        "weekly thread",
        "discussion thread",
        "podcast",
        "for a video",
        "researching",
        "recommendations",
        "looking for cases",
        "what are your thoughts",
        "does anyone remember",
        "help me find",
        "need help finding",
        "case suggestions",
        "where can i find",
    ]

    return any(b in titulo for b in bloqueios)


# =========================================================
# EXTRAÇÃO INTELIGENTE DO ANO DO CASO
# =========================================================

def extrair_ano_contextual(titulo, resumo):
    """
    Extrai o ano mais provável do evento principal do caso.

    Regra profissional:
    1. Se o título contém ano e termos de caso, o ano do título tem prioridade.
    2. Depois, procura expressões diretamente ligadas ao evento:
       missing since, went missing, last seen, found dead, murdered, body found etc.
    3. Ignora anos de nascimento, NamUs, podcast, reportagem, documentário,
       "current age", "added in", eventos secundários e referências históricas.
    """
    titulo_norm = normalizar(titulo)
    texto_total = limpar_html(f"{titulo}. {resumo}")
    texto = normalizar(texto_total)

    termos_de_caso_no_titulo = [
        "missing",
        "disappeared",
        "vanished",
        "vanishes",
        "murder",
        "murdered",
        "homicide",
        "found dead",
        "body found",
        "remains",
        "jane doe",
        "john doe",
        "since",
        "last seen",
        "last contacted",
        "what happened",
        "who was",
        "who is",
    ]

    anos_titulo = [
        int(a) for a in re.findall(r"\b(19\d{2}|20[0-2]\d)\b", titulo_norm)
    ]

    # Quando o título já descreve o evento, ele costuma ser mais confiável que o resumo.
    if anos_titulo and any(t in titulo_norm for t in termos_de_caso_no_titulo):
        ano = min(anos_titulo)
        return ano, ANO_ATUAL - ano

    meses = (
        "january|february|march|april|may|june|july|august|"
        "september|october|november|december|jan|feb|mar|apr|jun|jul|aug|"
        "sep|sept|oct|nov|dec"
    )

    padroes_fortes = [
        rf"(?:missing since|went missing|reported missing|listed as missing|has been missing|"
        rf"last seen|last contacted|last confirmed contact|disappeared|vanished|vanishes)"
        rf"[^.?!]{{0,100}}\b(19\d{{2}}|20[0-2]\d)\b",

        rf"\b(19\d{{2}}|20[0-2]\d)\b[^.?!]{{0,100}}"
        rf"(?:went missing|reported missing|listed as missing|has been missing|last seen|"
        rf"last contacted|last confirmed contact|disappeared|vanished|vanishes)",

        rf"(?:found dead|body was found|body found|remains were found|remains found|"
        rf"was murdered|murdered|killed|homicide|death occurred)"
        rf"[^.?!]{{0,100}}\b(19\d{{2}}|20[0-2]\d)\b",

        rf"\b(19\d{{2}}|20[0-2]\d)\b[^.?!]{{0,100}}"
        rf"(?:found dead|body was found|body found|remains were found|remains found|"
        rf"was murdered|murdered|killed|homicide)",

        rf"(?:on|in|since|from|around)\s+"
        rf"(?:(?:{meses})\s+)?"
        rf"(?:\d{{1,2}}(?:st|nd|rd|th)?(?:,)?\s+)?"
        rf"\b(19\d{{2}}|20[0-2]\d)\b",
    ]

    termos_exclusao_janela = [
        "born",
        "was born",
        "dob",
        "date of birth",
        "current age",
        "age at disappearance",
        "age at the time",
        "released in",
        "episode",
        "podcast",
        "article",
        "documentary",
        "case number",
        "namus",
        "report from",
        "reports from",
        "as of",
        "posted",
        "submitted",
        "added in",
        "grammys",
        "attendance",
        "school to study",
        "graduated",
        "formed in",
        "sentenced in",
    ]

    candidatos = []

    for prioridade, padrao in enumerate(padroes_fortes):
        for match in re.finditer(padrao, texto, flags=re.IGNORECASE):
            ano = int(match.group(1))

            inicio = max(0, match.start() - 100)
            fim = min(len(texto), match.end() + 100)
            janela = texto[inicio:fim]

            if any(ex in janela for ex in termos_exclusao_janela):
                continue

            if 1900 <= ano <= ANO_ATUAL:
                candidatos.append((prioridade, ano))

    if candidatos:
        # Prioridade menor é melhor; dentro da mesma prioridade, ano mais antigo tende a ser o evento.
        candidatos.sort(key=lambda item: (item[0], item[1]))
        ano = candidatos[0][1]
        return ano, ANO_ATUAL - ano

    return None, None

# =========================================================
# STATUS E TIPO DE CASO
# =========================================================

def detectar_status(titulo, resumo):
    """
    Classifica status com cautela.
    Não marca como resolvido só porque o texto menciona 'identified',
    'recovered' ou 'arrest' em contexto secundário.
    """
    titulo_norm = normalizar(titulo)
    texto = normalizar(f"{titulo} {resumo}")

    termos_resolvido_titulo = [
        "killer identified",
        "has been identified",
        "has been named",
        "arrest",
        "arrested",
        "case solved",
        "solved",
        "remains have been recovered",
        "body has been recovered",
        "recovered in",
        "recovered from",
    ]

    if any(t in titulo_norm for t in termos_resolvido_titulo):
        return "RESOLVIDO/ATUALIZAÇÃO"

    termos_resolvido_resumo = [
        "officially arrested",
        "has been arrested",
        "was arrested",
        "has been named",
        "identified the killer",
        "killer has been identified",
        "case was solved",
        "case has been solved",
        "dna match",
        "genetic genealogy breakthrough",
        "recovered the remains",
        "confirmed her identity",
        "confirmed his identity",
        "provided investigators a location",
    ]

    if any(t in texto for t in termos_resolvido_resumo):
        return "RESOLVIDO/ATUALIZAÇÃO"

    termos_aberto = [
        "still missing",
        "has been missing",
        "been missing",
        "listed as missing",
        "listed as a missing person",
        "is listed as a missing person",
        "missing from",
        "missing since",
        "never came home",
        "still has no name",
        "has no name",
        "no name",
        "never found",
        "no trace",
        "case is still open",
        "unsolved",
        "where is",
        "what happened to",
        "who was",
        "who is",
        "no arrests",
        "no suspect",
        "no confirmed sightings",
        "no one has been charged",
        "remains unsolved",
        "not been solved",
        "no closer to finding",
        "never seen again",
    ]

    if any(t in texto for t in termos_aberto):
        return "ABERTO"

    return "INDEFINIDO"

def caso_famoso_ou_saturado(titulo):
    titulo = normalizar(titulo)

    famosos = [
        "lars mittank",
        "emanuela orlandi",
        "brandon swanson",
        "aarushi talwar",
        "mary bell",
        "madeleine mccann",
        "elisa lam",
        "brian shaffer",
        "maura murray",
    ]

    return any(nome in titulo for nome in famosos)


def detectar_tipo_caso(titulo, resumo, status):
    texto = normalizar(f"{titulo} {resumo}")

    if caso_famoso_ou_saturado(titulo):
        return "CASO FAMOSO/SATURADO"

    if status == "RESOLVIDO/ATUALIZAÇÃO":
        return "CASO RESOLVIDO/ATUALIZAÇÃO"

    if any(t in texto for t in [
        "jane doe",
        "john doe",
        "unidentified body",
        "unidentified remains",
        "unidentified victim",
        "still has no name",
        "has no name",
        "no name",
    ]):
        return "IDENTIDADE DESCONHECIDA"

    if any(t in texto for t in [
        "still missing",
        "has been missing",
        "been missing",
        "listed as missing",
        "listed as a missing person",
        "is listed as a missing person",
        "missing from",
        "missing since",
        "missing person",
        "went missing",
        "reported missing",
        "disappeared",
        "vanished",
        "never found",
        "no trace",
        "never seen again",
    ]):
        return "DESAPARECIMENTO ABERTO"

    if any(t in texto for t in [
        "murder",
        "murdered",
        "homicide",
        "found dead",
        "body found",
        "shot to death",
        "stabbed",
        "killed",
        "death was listed as undetermined",
    ]):
        return "HOMICÍDIO/MORTE SUSPEITA"

    return "CASO DE APOIO/PESQUISA"

# =========================================================
# SCORE PROFISSIONAL
# =========================================================

def pontuar_grupo(texto, regras, limite, elementos, categoria, modo="soma"):
    pontos = 0
    encontrados = []

    for termo, valor in regras.items():
        if contem(texto, termo):
            encontrados.append((termo, valor))

    if encontrados:
        if modo == "max":
            termo, valor = max(encontrados, key=lambda x: x[1])
            pontos = valor
            elementos.append(f"{termo} / {categoria}")
        else:
            for termo, valor in encontrados:
                pontos += valor
                elementos.append(f"{termo} / {categoria}")

    return min(pontos, limite)


def calcular_score_profissional(titulo, resumo):
    resumo_util = not resumo_inutil(resumo)
    texto_base = f"{titulo} {resumo}" if resumo_util else titulo
    texto = normalizar(texto_base)

    elementos = []
    categorias = {}

    ano_caso, idade_caso = extrair_ano_contextual(titulo, resumo)

    categorias["Mistério Central"] = pontuar_grupo(
        texto,
        {
            "missing": 16,
            "disappearance": 16,
            "disappeared": 16,
            "vanished": 20,
            "vanishes": 18,
            "without trace": 22,
            "no trace": 20,
            "never found": 20,
            "still missing": 20,
            "unsolved": 16,
            "cold case": 18,
            "jane doe": 20,
            "john doe": 20,
            "unidentified body": 18,
            "unidentified remains": 18,
            "body found": 14,
            "remains": 12,
            "murdered": 12,
            "murder": 10,
            "homicide": 10,
        },
        24,
        elementos,
        "mistério central",
        modo="max",
    )

    tempo = 0

    if idade_caso is not None:
        if idade_caso >= 40:
            tempo = 15
            elementos.append(f"{idade_caso} anos sem resposta / tempo histórico")
        elif idade_caso >= 25:
            tempo = 12
            elementos.append(f"{idade_caso} anos sem resposta / tempo relevante")
        elif idade_caso >= 10:
            tempo = 9
            elementos.append(f"{idade_caso} anos sem resposta / caso antigo")
        elif idade_caso >= 3:
            tempo = 5
            elementos.append(f"{idade_caso} anos sem resposta / caso recente")

    tempo = max(
        tempo,
        pontuar_grupo(
            texto,
            {
                "decades": 14,
                "50 years": 15,
                "40 years": 14,
                "30 years": 12,
                "20 years": 10,
                "10 years": 8,
                "years later": 6,
            },
            15,
            elementos,
            "tempo sem solução",
            modo="max",
        )
    )

    categorias["Tempo Sem Solução"] = min(tempo, 15)

    categorias["Prova Visual ou Último Registro"] = pontuar_grupo(
        texto,
        {
            "last seen": 14,
            "last contacted": 12,
            "last image": 15,
            "cctv": 16,
            "surveillance": 15,
            "security footage": 16,
            "footage": 13,
            "camera": 10,
            "photograph": 8,
            "photo": 7,
            "phone call": 9,
            "voicemail": 9,
        },
        17,
        elementos,
        "último registro ou prova visual",
    )

    categorias["Ambiente Cinematográfico"] = pontuar_grupo(
        texto,
        {
            "national park": 10,
            "wilderness": 10,
            "forest": 9,
            "woods": 9,
            "mountain": 9,
            "airport": 9,
            "island": 9,
            "highway": 8,
            "road": 6,
            "river": 8,
            "canal": 8,
            "train": 8,
            "hotel": 6,
            "motel": 6,
            "night": 6,
            "snow": 6,
            "desert": 6,
            "trailhead": 8,
        },
        12,
        elementos,
        "cenário cinematográfico",
    )

    categorias["Complexidade Investigativa"] = pontuar_grupo(
        texto,
        {
            "false trails": 12,
            "missing files": 12,
            "foul play": 10,
            "unknown": 7,
            "unidentified": 9,
            "investigation": 8,
            "police": 4,
            "theory": 5,
            "theories": 6,
            "witness": 7,
            "dna": 7,
            "genetic genealogy": 8,
            "inheritance dispute": 8,
            "no evidence": 6,
            "no arrests": 7,
            "no suspect": 7,
        },
        16,
        elementos,
        "complexidade investigativa",
    )

    categorias["Impacto Humano"] = pontuar_grupo(
        texto,
        {
            "child": 8,
            "teen": 7,
            "teenager": 7,
            "15 year old": 8,
            "daughter": 5,
            "son": 5,
            "mother": 4,
            "father": 4,
            "family": 4,
            "children": 5,
        },
        8,
        elementos,
        "impacto humano",
    )

    qualidade = 0

    if resumo_util:
        tamanho = len(resumo)

        if tamanho >= 900:
            qualidade += 8
            elementos.append("resumo longo e apurável / qualidade da fonte")
        elif tamanho >= 400:
            qualidade += 5
            elementos.append("resumo suficiente para triagem / qualidade da fonte")

        nomes = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", resumo)

        if len(nomes) >= 2:
            qualidade += 3
            elementos.append("nomes próprios identificáveis / qualidade da fonte")

        if ano_caso:
            qualidade += 2
            elementos.append("ano contextual identificado / qualidade da fonte")
    else:
        elementos.append("resumo RSS ausente ou pobre / exige apuração manual")

    categorias["Qualidade da Fonte"] = min(qualidade, 10)

    score = sum(categorias.values())

    status = detectar_status(titulo, resumo)
    tipo = detectar_tipo_caso(titulo, resumo, status)

    if not resumo_util:
        score -= 12

    if categorias["Mistério Central"] < 10:
        score -= 14
        elementos.append("mistério central fraco / risco de pauta genérica")

    if len(titulo.split()) < 6:
        score -= 6
        elementos.append("título curto ou pouco específico / baixa segurança editorial")

    if status == "RESOLVIDO/ATUALIZAÇÃO":
        score -= 10
        elementos.append("caso resolvido ou atualização / menor prioridade para vídeo principal")

    if tipo == "CASO FAMOSO/SATURADO":
        score -= 8
        elementos.append("caso famoso ou saturado / exige ângulo novo")

    if status == "RESOLVIDO/ATUALIZAÇÃO":
        score = min(score, 76)

    if tipo == "CASO FAMOSO/SATURADO":
        score = min(score, 82)

    if not resumo_util:
        score = min(score, 70)

    score = max(0, min(int(round(score)), 100))

    return score, elementos, categorias, resumo_util, ano_caso, idade_caso, status, tipo


# =========================================================
# CLASSIFICAÇÃO EDITORIAL
# =========================================================

def potencial_documental(score):
    if score >= 88:
        return "Muito Alto"
    if score >= 74:
        return "Alto"
    if score >= 55:
        return "Médio"
    return "Baixo"


def relevancia_sem_rastros(score):
    if score >= 88:
        return "ALTÍSSIMA"
    if score >= 74:
        return "ALTA"
    if score >= 55:
        return "MÉDIA"
    return "BAIXA"


def classificacao_caso(score):
    if score >= 88:
        return "CASO PRINCIPAL"
    if score >= 74:
        return "MUITO FORTE"
    if score >= 55:
        return "OBSERVAR"
    return "BAIXO"


def uso_recomendado(score, status, tipo, resumo_util):
    if tipo == "CASO FAMOSO/SATURADO":
        if score >= 74:
            return "Vídeo principal somente com ângulo novo"
        return "Pesquisa complementar"

    if status == "RESOLVIDO/ATUALIZAÇÃO":
        if score >= 60:
            return "Atualização de caso ou short documental"
        return "Nota curta"

    if score >= 88 and resumo_util:
        return "Vídeo principal"

    if score >= 74:
        return "Lista curta para roteiro"

    if score >= 55:
        return "Pesquisa complementar"

    return "Descartar por enquanto"


def decisao_editorial(score, status, tipo, resumo_util):
    uso = uso_recomendado(score, status, tipo, resumo_util)

    if uso == "Vídeo principal":
        return "PRIORIDADE DE ROTEIRO"

    if uso == "Lista curta para roteiro":
        return "ENTRA NA LISTA CURTA"

    if uso == "Atualização de caso ou short documental":
        return "USAR COMO ATUALIZAÇÃO/SHORT"

    if uso == "Nota curta":
        return "USAR COMO NOTA CURTA"

    if "ângulo novo" in uso:
        return "APENAS COM GANCHO DIFERENCIADO"

    if uso == "Pesquisa complementar":
        return "GUARDAR PARA PESQUISA"

    return "DESCARTAR POR ENQUANTO"

def seguranca_pauta(score, resumo_util, status):
    if score >= 74 and resumo_util and status != "INDEFINIDO":
        return "ALTA"

    if score >= 55 and resumo_util:
        return "MÉDIA"

    return "BAIXA"


def motivo_editorial(categorias, resumo_util, status, tipo):
    motivos = []

    if categorias.get("Mistério Central", 0) >= 16:
        motivos.append("tem mistério central claro")

    if categorias.get("Tempo Sem Solução", 0) >= 9:
        motivos.append("possui tempo relevante sem resposta")

    if categorias.get("Prova Visual ou Último Registro", 0) >= 10:
        motivos.append("oferece último registro, pista visual ou material concreto de narrativa")

    if categorias.get("Ambiente Cinematográfico", 0) >= 8:
        motivos.append("possui cenário com potencial visual")

    if categorias.get("Complexidade Investigativa", 0) >= 8:
        motivos.append("tem perguntas investigativas abertas")

    if categorias.get("Impacto Humano", 0) >= 5:
        motivos.append("carrega conexão emocional com vítima ou família")

    if categorias.get("Qualidade da Fonte", 0) >= 5:
        motivos.append("tem resumo útil para triagem inicial")

    if status == "RESOLVIDO/ATUALIZAÇÃO":
        motivos.append("porém funciona melhor como atualização ou short, não como caso principal")

    if tipo == "CASO FAMOSO/SATURADO":
        motivos.append("porém exige ângulo novo para não repetir conteúdo já saturado")

    if not resumo_util:
        motivos.append("mas exige apuração manual porque o RSS não trouxe resumo confiável")

    if motivos:
        return "Caso selecionado porque " + "; ".join(motivos) + "."

    return "Caso com potencial limitado; precisa de pesquisa complementar antes de virar pauta."


def gerar_hook(titulo, elementos, tipo, status):
    texto = normalizar(f"{titulo} {' '.join(elementos)}")

    if tipo == "IDENTIDADE DESCONHECIDA":
        return "Por anos, a vítima não teve nome — e descobrir quem ela era pode ser só o começo do mistério."

    if status == "RESOLVIDO/ATUALIZAÇÃO":
        return "Depois de anos sem resposta, uma nova descoberta mudou completamente a leitura do caso."

    if "cctv" in texto or "security footage" in texto or "footage" in texto:
        return "A última imagem parecia comum, mas se tornou uma das pistas mais inquietantes do caso."

    if "vanished" in texto or "without trace" in texto or "no trace" in texto:
        return "A pessoa desapareceu sem deixar rastro, e cada detalhe parece abrir uma nova pergunta."

    if "50 years" in texto or "40 years" in texto or "30 years" in texto or "decades" in texto:
        return "Décadas se passaram, mas uma pergunta continuou sem resposta."

    return random.choice([
        "O caso parecia simples, até os detalhes começarem a não fazer sentido.",
        "A última vez que alguém o viu, tudo parecia normal.",
        "As autoridades tinham pistas, mas nenhuma resposta definitiva.",
        "O desaparecimento começou como uma ocorrência comum e virou um mistério inquietante.",
    ])


# =========================================================
# COLETA RSS
# =========================================================

def coletar_posts():
    posts = []

    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url, agent=USER_AGENT)

            for entry in getattr(feed, "entries", []):
                posts.append(entry)

        except Exception as erro:
            print(f"ERRO AO LER FEED {url}: {erro}")

    return posts


# =========================================================
# PROCESSAMENTO
# =========================================================

def processar_posts(posts):
    dados = []
    links_vistos = set()
    titulos_vistos = set()

    for entry in posts:
        titulo = getattr(entry, "title", "").strip()
        resumo = limpar_html(getattr(entry, "summary", ""))
        link = getattr(entry, "link", "").strip()

        if not titulo:
            continue

        if titulo_meta_ou_inutil(titulo):
            continue

        chave_titulo = normalizar(titulo)
        chave_link = link.lower()

        if chave_link and chave_link in links_vistos:
            continue

        if chave_titulo in titulos_vistos:
            continue

        if chave_link:
            links_vistos.add(chave_link)

        titulos_vistos.add(chave_titulo)

        score, elementos, categorias, resumo_util, ano_caso, idade_caso, status, tipo = calcular_score_profissional(
            titulo,
            resumo
        )

        if score < 50:
            continue

        if resumo_util:
            resumo_exibido = resumo[:1800]
        else:
            resumo_exibido = (
                "Resumo não disponível no RSS. Caso selecionado pelo potencial do título; "
                "abrir o link para apuração completa antes da produção."
            )

        uso = uso_recomendado(score, status, tipo, resumo_util)

        dados.append({
            "Caso": titulo,
            "Resumo Original": resumo_exibido,
            "Score": score,
            "Potencial Documental": potencial_documental(score),
            "Relevância para Sem Rastros": relevancia_sem_rastros(score),
            "Classificação": classificacao_caso(score),
            "Tipo de Caso": tipo,
            "Uso Recomendado": uso,
            "Decisão Editorial": decisao_editorial(score, status, tipo, resumo_util),
            "Ano do Caso": ano_caso if ano_caso else "Não identificado",
            "Idade do Caso": idade_caso if idade_caso is not None else "Não identificada",
            "Status Detectado": status,
            "Segurança da Pauta": seguranca_pauta(score, resumo_util, status),
            "Elementos Detectados": ", ".join(elementos[:20]),
            "Motivo Editorial": motivo_editorial(categorias, resumo_util, status, tipo),
            "Hook": gerar_hook(titulo, elementos, tipo, status),
            "Link": link,
        })

    return dados


# =========================================================
# SAÍDAS
# =========================================================

def gerar_dataframe(dados):
    if dados:
        df = pd.DataFrame(dados, columns=COLUNAS)
        df = df.sort_values(by="Score", ascending=False)
    else:
        df = pd.DataFrame(columns=COLUNAS)

    return df


def salvar_csv(df):
    os.makedirs(PASTA_RESULTADOS, exist_ok=True)
    df.to_csv(CSV_SAIDA, index=False, encoding="utf-8-sig")


def gerar_pdf(df):
    os.makedirs(PASTA_RESULTADOS, exist_ok=True)

    pdf = SimpleDocTemplate(PDF_SAIDA)
    styles = getSampleStyleSheet()
    conteudo = []

    conteudo.append(
        Paragraph(
            "<b>RADAR CINEMATOGRÁFICO PROFISSIONAL SEM RASTROS</b>",
            styles["Title"]
        )
    )

    conteudo.append(Spacer(1, 20))

    if df.empty:
        texto = """
        <b>Nenhum caso válido encontrado nesta execução.</b><br/>
        O radar rodou corretamente, mas os feeds não retornaram casos acima do corte editorial mínimo.
        """
        conteudo.append(Paragraph(texto, styles["BodyText"]))
    else:
        for _, row in df.head(20).iterrows():
            texto = f"""
            <b>Caso:</b> {seguro_pdf(row['Caso'])}<br/>
            <b>Resumo:</b> {seguro_pdf(row['Resumo Original'])}<br/>
            <b>Score:</b> {seguro_pdf(row['Score'])}<br/>
            <b>Potencial:</b> {seguro_pdf(row['Potencial Documental'])}<br/>
            <b>Relevância Sem Rastros:</b> {seguro_pdf(row['Relevância para Sem Rastros'])}<br/>
            <b>Classificação:</b> {seguro_pdf(row['Classificação'])}<br/>
            <b>Tipo de Caso:</b> {seguro_pdf(row['Tipo de Caso'])}<br/>
            <b>Uso Recomendado:</b> {seguro_pdf(row['Uso Recomendado'])}<br/>
            <b>Decisão Editorial:</b> {seguro_pdf(row['Decisão Editorial'])}<br/>
            <b>Ano do Caso:</b> {seguro_pdf(row['Ano do Caso'])}<br/>
            <b>Idade do Caso:</b> {seguro_pdf(row['Idade do Caso'])}<br/>
            <b>Status Detectado:</b> {seguro_pdf(row['Status Detectado'])}<br/>
            <b>Segurança da Pauta:</b> {seguro_pdf(row['Segurança da Pauta'])}<br/>
            <b>Elementos Detectados:</b> {seguro_pdf(row['Elementos Detectados'])}<br/>
            <b>Motivo Editorial:</b> {seguro_pdf(row['Motivo Editorial'])}<br/>
            <b>Hook:</b> {seguro_pdf(row['Hook'])}<br/>
            <b>Link:</b> {seguro_pdf(row['Link'])}<br/><br/>
            """

            conteudo.append(Paragraph(texto, styles["BodyText"]))
            conteudo.append(Spacer(1, 18))

    pdf.build(conteudo)


# =========================================================
# EXECUÇÃO
# =========================================================

def main():
    posts = coletar_posts()
    dados = processar_posts(posts)
    df = gerar_dataframe(dados)

    print(df.head(20))

    salvar_csv(df)
    gerar_pdf(df)

    print("\nRADAR CINEMATOGRÁFICO PROFISSIONAL FINALIZADO")
    print(f"TOTAL DE POSTS COLETADOS: {len(posts)}")
    print(f"TOTAL DE CASOS APROVADOS: {len(df)}")
    print(f"CSV SALVO EM: {CSV_SAIDA}")
    print(f"PDF SALVO EM: {PDF_SAIDA}")


if __name__ == "__main__":
    main()
