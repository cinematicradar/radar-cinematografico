from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
import feedparser
import pandas as pd
import random
import re
import os
import html
from datetime import datetime


# =========================================================
# RADAR CINEMATOGRÁFICO PROFISSIONAL SEM RASTROS - V5.3
# Gera automaticamente:
# 1) resultados/casos_cinematicos.csv
# 2) resultados/dossie_cinematografico.pdf
# 3) resultados/briefings_sem_rastros.md
# 4) resultados/briefings_sem_rastros.pdf
# =========================================================

ANO_ATUAL = datetime.now().year

PASTA_RESULTADOS = "resultados"
CSV_SAIDA = os.path.join(PASTA_RESULTADOS, "casos_cinematicos.csv")
PDF_SAIDA = os.path.join(PASTA_RESULTADOS, "dossie_cinematografico.pdf")
BRIEFING_MD_SAIDA = os.path.join(PASTA_RESULTADOS, "briefings_sem_rastros.md")
BRIEFING_PDF_SAIDA = os.path.join(PASTA_RESULTADOS, "briefings_sem_rastros.pdf")

RSS_FEEDS = [
    "https://www.reddit.com/r/UnresolvedMysteries/.rss",
    "https://www.reddit.com/r/MissingPersons/.rss",
    "https://www.reddit.com/r/TrueCrime/.rss",
    "https://www.reddit.com/r/UnsolvedMysteries/.rss",
]

USER_AGENT = "SemRastrosRadar/5.3"

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
# LIMPEZA E UTILITÁRIOS
# =========================================================

def limpar_html(texto):
    texto = html.unescape(str(texto or ""))
    texto = re.sub(r"<[^>]+>", " ", texto)
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


def fora_escopo_sem_rastros(titulo, resumo, link=""):
    texto = normalizar(f"{titulo} {resumo}")
    link_norm = normalizar(link)

    nucleo_sem_rastros = [
        "missing",
        "disappeared",
        "vanished",
        "still missing",
        "never found",
        "no trace",
        "unsolved",
        "cold case",
        "jane doe",
        "john doe",
        "unidentified",
        "who was",
        "who is",
        "what happened",
        "found dead",
        "body found",
        "remains",
        "no arrests",
        "no suspect",
    ]

    tem_nucleo = any(t in texto for t in nucleo_sem_rastros)

    truecrime_comum = [
        "sentenced to death",
        "death row",
        "serial rapist",
        "fatally shot a police officer",
        "patrolman",
        "was indicted",
        "parole violation",
        "pleaded guilty",
        "convicted killer",
        "executed",
        "death sentence",
    ]

    if any(t in texto for t in truecrime_comum) and not tem_nucleo:
        return True

    if "r/truecrime" in link_norm and any(t in texto for t in truecrime_comum):
        return True

    return False


# =========================================================
# EXTRAÇÃO INTELIGENTE DO ANO DO CASO
# =========================================================

def extrair_ano_contextual(titulo, resumo):
    titulo_norm = normalizar(titulo)
    texto_total = normalizar(f"{titulo}. {resumo}")

    termos_titulo = [
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

    if anos_titulo and any(t in titulo_norm for t in termos_titulo):
        ano = min(anos_titulo)
        return ano, ANO_ATUAL - ano

    meses = (
        "january|february|march|april|may|june|july|august|"
        "september|october|november|december|jan|feb|mar|apr|jun|jul|aug|"
        "sep|sept|oct|nov|dec"
    )

    padroes = [
        rf"(?:missing since|went missing|reported missing|listed as missing|has been missing|last seen|last contacted|last confirmed contact|disappeared|vanished|vanishes)[^.?!]{{0,100}}\b(19\d{{2}}|20[0-2]\d)\b",
        rf"\b(19\d{{2}}|20[0-2]\d)\b[^.?!]{{0,100}}(?:went missing|reported missing|listed as missing|has been missing|last seen|last contacted|last confirmed contact|disappeared|vanished|vanishes)",
        rf"(?:found dead|body was found|body found|remains were found|remains found|was murdered|murdered|killed|homicide|death occurred)[^.?!]{{0,100}}\b(19\d{{2}}|20[0-2]\d)\b",
        rf"\b(19\d{{2}}|20[0-2]\d)\b[^.?!]{{0,100}}(?:found dead|body was found|body found|remains were found|remains found|was murdered|murdered|killed|homicide)",
        rf"(?:on|in|since|from|around)\s+(?:{meses})?\s*\d{{0,2}}[^.?!]{{0,35}}\b(19\d{{2}}|20[0-2]\d)\b[^.?!]{{0,80}}(?:missing|disappeared|vanished|murdered|found dead|body found|remains|last seen)",
    ]

    termos_exclusao = [
        "born",
        "dob",
        "date of birth",
        "current age",
        "age at disappearance",
        "was born",
        "released in",
        "episode",
        "podcast",
        "article",
        "documentary",
        "case number",
        "namus",
        "as of",
        "report from",
        "reports from",
        "posted",
        "submitted",
        "added in",
        "grammys",
        "school year",
        "class of",
    ]

    candidatos = []

    for prioridade, padrao in enumerate(padroes):
        for match in re.finditer(padrao, texto_total, flags=re.IGNORECASE):
            ano = int(match.group(1))

            inicio = max(0, match.start() - 90)
            fim = min(len(texto_total), match.end() + 90)
            janela = texto_total[inicio:fim]

            if any(ex in janela for ex in termos_exclusao):
                continue

            if 1900 <= ano <= ANO_ATUAL:
                candidatos.append((prioridade, ano))

    if candidatos:
        candidatos.sort(key=lambda item: (item[0], item[1]))
        ano = candidatos[0][1]
        return ano, ANO_ATUAL - ano

    return None, None


# =========================================================
# STATUS E TIPO DE CASO
# =========================================================

def detectar_status(titulo, resumo):
    titulo_norm = normalizar(titulo)
    texto = normalizar(f"{titulo} {resumo}")

    termos_aberto = [
        "still missing",
        "never found",
        "no trace",
        "case is still open",
        "unsolved",
        "where is",
        "what happened to",
        "what became of",
        "who was",
        "who is",
        "no arrests",
        "no suspect",
        "no confirmed sightings",
        "never seen him again",
        "never seen her again",
        "family continues to search",
        "remains unidentified",
        "still has no name",
        "no name",
        "unidentified victim",
    ]

    if any(t in texto for t in termos_aberto):
        return "ABERTO"

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
    ]

    if any(t in titulo_norm for t in termos_resolvido_titulo):
        return "RESOLVIDO/ATUALIZAÇÃO"

    termos_resolvido_resumo = [
        "officially arrested",
        "has been arrested",
        "has been named",
        "identified the killer",
        "case was solved",
        "dna match",
        "genetic genealogy breakthrough",
        "recovered the remains",
        "confirmed her identity",
        "confirmed his identity",
    ]

    if any(t in texto for t in termos_resolvido_resumo):
        return "RESOLVIDO/ATUALIZAÇÃO"

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
        if any(t in texto for t in ["jane doe", "john doe", "unidentified", "no name"]):
            return "IDENTIDADE DESCONHECIDA"

        return "CASO RESOLVIDO/ATUALIZAÇÃO"

    if any(t in texto for t in [
        "jane doe",
        "john doe",
        "unidentified body",
        "unidentified remains",
        "unidentified victim",
        "still has no name",
        "no name",
    ]):
        return "IDENTIDADE DESCONHECIDA"

    if any(t in texto for t in [
        "still missing",
        "went missing",
        "reported missing",
        "disappeared",
        "vanished",
        "never found",
        "no trace",
        "what became of",
        "missing from",
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
        "drownings",
        "death",
        "deaths",
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
        ),
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

        if fora_escopo_sem_rastros(titulo, resumo, link):
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

        if score < 55:
            continue

        uso = uso_recomendado(score, status, tipo, resumo_util)
        decisao = decisao_editorial(score, status, tipo, resumo_util)

        if decisao == "DESCARTAR POR ENQUANTO":
            continue

        if resumo_util:
            resumo_exibido = resumo[:1800]
        else:
            resumo_exibido = (
                "Resumo não disponível no RSS. Caso selecionado pelo potencial do título; "
                "abrir o link para apuração completa antes da produção."
            )

        dados.append({
            "Caso": titulo,
            "Resumo Original": resumo_exibido,
            "Score": score,
            "Potencial Documental": potencial_documental(score),
            "Relevância para Sem Rastros": relevancia_sem_rastros(score),
            "Classificação": classificacao_caso(score),
            "Tipo de Caso": tipo,
            "Uso Recomendado": uso,
            "Decisão Editorial": decisao,
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


def gerar_dataframe(dados):
    if dados:
        df = pd.DataFrame(dados, columns=COLUNAS)
        df = df.sort_values(by="Score", ascending=False)
    else:
        df = pd.DataFrame(columns=COLUNAS)

    return df


# =========================================================
# SAÍDAS
# =========================================================

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
# BRIEFINGS AUTOMÁTICOS
# =========================================================

def briefing_para_linha(row, indice):
    caso = str(row.get("Caso", "")).strip()
    hook = str(row.get("Hook", "")).strip()
    tipo = str(row.get("Tipo de Caso", "")).strip()
    uso = str(row.get("Uso Recomendado", "")).strip()
    motivo = str(row.get("Motivo Editorial", "")).strip()
    elementos = str(row.get("Elementos Detectados", "")).strip()
    score = str(row.get("Score", "")).strip()
    link = str(row.get("Link", "")).strip()

    promessa = hook if hook else "Um caso com perguntas abertas, pistas incompletas e potencial para narrativa documental."

    if "IDENTIDADE DESCONHECIDA" in tipo:
        angulo = (
            "Mistério de identidade: quem era a vítima, por que ninguém conseguiu identificá-la "
            "e quais pistas ainda podem revelar seu nome."
        )
        thumbnail = "Rosto parcialmente oculto + texto: 'SEM NOME HÁ ANOS'"
    elif "DESAPARECIMENTO" in tipo:
        angulo = (
            "Desaparecimento sem resposta: reconstruir as últimas horas, o último contato "
            "e as lacunas que impedem o fechamento do caso."
        )
        thumbnail = "Estrada/floresta vazia + texto: 'ELE SUMIU AQUI?'"
    elif "HOMICÍDIO" in tipo:
        angulo = (
            "Morte suspeita com perguntas abertas: analisar cenário, falhas investigativas "
            "e hipóteses ainda não resolvidas."
        )
        thumbnail = "Cena escura + fita policial + texto: 'O DETALHE IGNORADO'"
    elif "FAMOSO" in tipo:
        angulo = (
            "Caso conhecido, mas só vale se houver ângulo novo: focar em detalhe pouco explorado, "
            "contradição ou última janela temporal."
        )
        thumbnail = "Imagem de arquivo estilizada + texto: 'O QUE NÃO CONTARAM'"
    else:
        angulo = "Pauta de apoio: usar para pesquisa complementar, short documental ou bloco dentro de episódio maior."
        thumbnail = "Mapa + documento antigo + texto: 'ARQUIVO ABERTO'"

    return f"""
## {indice}. {caso}

**Score:** {score}  
**Tipo:** {tipo}  
**Uso recomendado:** {uso}  
**Link:** {link}

### Promessa do vídeo
{promessa}

### Ângulo narrativo
{angulo}

### Estrutura sugerida de roteiro
1. **Abertura fria:** comece pelo detalhe mais inquietante do caso, sem explicar tudo de imediato.
2. **Quem era a pessoa/vítima:** apresente identidade, rotina, vínculos familiares e contexto humano.
3. **Linha do tempo:** reconstrua as últimas horas ou o momento da descoberta.
4. **Pistas materiais:** destaque último registro, local, objeto encontrado, câmera, ligação, testemunha ou ausência de evidência.
5. **Hipóteses:** apresente teorias sem afirmar culpa sem prova.
6. **O que ainda falta:** mostre lacunas, documentos, perguntas abertas e caminhos de apuração.
7. **Fechamento:** finalize com uma pergunta forte para comentário e retenção.

### Pesquisa obrigatória antes de gravar
- Confirmar dados em fontes primárias: polícia, NamUs, Doe Network, Charley Project, jornais locais ou registros oficiais.
- Verificar se o caso está aberto, resolvido ou parcialmente atualizado.
- Procurar fotos, mapas, datas exatas, locais e nomes citados.
- Separar o que é fato, hipótese e especulação da comunidade.

### B-roll e direção visual
- Mapas com zoom lento no local do caso.
- Estradas vazias, rios, florestas, pontes, aeroportos, hotéis ou áreas urbanas conforme o caso.
- Documentos, recortes de jornal, tela de busca, arquivos antigos e fotografias com leve desfoque.
- Trilha discreta, clima investigativo, sem sensacionalismo visual.

### Sugestão de thumbnail
{thumbnail}

### Motivo editorial
{motivo}

### Elementos detectados
{elementos}
""".strip()


def gerar_briefings(df):
    os.makedirs(PASTA_RESULTADOS, exist_ok=True)
    styles = getSampleStyleSheet()

    if df.empty:
        md = "# Briefings Sem Rastros\n\nNenhum caso aprovado para briefing nesta execução.\n"

        with open(BRIEFING_MD_SAIDA, "w", encoding="utf-8") as arquivo:
            arquivo.write(md)

        pdf = SimpleDocTemplate(BRIEFING_PDF_SAIDA)
        pdf.build([
            Paragraph("<b>Briefings Sem Rastros</b>", styles["Title"]),
            Spacer(1, 20),
            Paragraph("Nenhum caso aprovado para briefing nesta execução.", styles["BodyText"]),
        ])
        return

    df_brief = df[df["Decisão Editorial"].isin([
        "PRIORIDADE DE ROTEIRO",
        "ENTRA NA LISTA CURTA",
        "USAR COMO ATUALIZAÇÃO/SHORT",
        "USAR COMO NOTA CURTA",
        "APENAS COM GANCHO DIFERENCIADO",
        "GUARDAR PARA PESQUISA",
    ])].copy()

    if df_brief.empty:
        df_brief = df.copy()

    df_brief = df_brief.sort_values(by="Score", ascending=False).head(12)

    blocos = ["# BRIEFINGS EDITORIAIS — SEM RASTROS\n"]

    for indice, (_, row) in enumerate(df_brief.iterrows(), start=1):
        blocos.append(briefing_para_linha(row, indice))
        blocos.append("\n---\n")

    md = "\n\n".join(blocos)

    with open(BRIEFING_MD_SAIDA, "w", encoding="utf-8") as arquivo:
        arquivo.write(md)

    conteudo = [
        Paragraph("<b>BRIEFINGS EDITORIAIS — SEM RASTROS</b>", styles["Title"]),
        Spacer(1, 20),
    ]

    for indice, (_, row) in enumerate(df_brief.iterrows(), start=1):
        titulo = f"{indice}. {row['Caso']}"
        conteudo.append(Paragraph(f"<b>{seguro_pdf(titulo)}</b>", styles["Heading2"]))

        campos = [
            ("Score", row.get("Score", "")),
            ("Tipo", row.get("Tipo de Caso", "")),
            ("Uso recomendado", row.get("Uso Recomendado", "")),
            ("Promessa", row.get("Hook", "")),
            ("Motivo editorial", row.get("Motivo Editorial", "")),
            ("Elementos", row.get("Elementos Detectados", "")),
            ("Link", row.get("Link", "")),
        ]

        for rotulo, valor in campos:
            conteudo.append(
                Paragraph(
                    f"<b>{seguro_pdf(rotulo)}:</b> {seguro_pdf(valor)}",
                    styles["BodyText"]
                )
            )
            conteudo.append(Spacer(1, 6))

        estrutura = """
        <b>Estrutura sugerida:</b><br/>
        1. Abertura fria com o detalhe mais inquietante.<br/>
        2. Quem era a pessoa/vítima e qual era o contexto humano.<br/>
        3. Linha do tempo das últimas horas ou da descoberta.<br/>
        4. Pistas materiais: local, último registro, câmera, objeto, testemunha ou ausência de evidência.<br/>
        5. Hipóteses separando fato de especulação.<br/>
        6. Perguntas abertas e fechamento com chamada para comentários.<br/>
        """

        conteudo.append(Paragraph(estrutura, styles["BodyText"]))
        conteudo.append(Spacer(1, 14))
        conteudo.append(PageBreak())

    pdf = SimpleDocTemplate(BRIEFING_PDF_SAIDA)
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
    gerar_briefings(df)

    print("\nRADAR CINEMATOGRÁFICO PROFISSIONAL FINALIZADO")
    print(f"TOTAL DE POSTS COLETADOS: {len(posts)}")
    print(f"TOTAL DE CASOS APROVADOS: {len(df)}")
    print(f"CSV SALVO EM: {CSV_SAIDA}")
    print(f"PDF SALVO EM: {PDF_SAIDA}")
    print(f"BRIEFING MD SALVO EM: {BRIEFING_MD_SAIDA}")
    print(f"BRIEFING PDF SALVO EM: {BRIEFING_PDF_SAIDA}")


if __name__ == "__main__":
    main()
