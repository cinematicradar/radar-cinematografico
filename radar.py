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
# RADAR CINEMATOGRÁFICO PROFISSIONAL SEM RASTROS - V5.0
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

USER_AGENT = "SemRastrosRadar/5.0"

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


def fora_escopo_sem_rastros(titulo, resumo, link=""):
    """
    Remove posts de true crime comum que até podem ser interessantes,
    mas não são bons para o posicionamento do Sem Rastros: desaparecimentos,
    identidades desconhecidas, mistérios abertos e investigações documentais.
    """
    texto = normalizar(f"{titulo} {resumo}")
    titulo_norm = normalizar(titulo)
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
    ]

    tem_nucleo = any(t in texto for t in nucleo_sem_rastros)

    # Condenações/crimes comuns com autor conhecido costumam gerar pauta fraca
    # para o canal, salvo quando há mistério, identidade desconhecida ou caso aberto.
    truecrime_comum = [
        "sentenced to death",
        "death row",
        "serial rapist",
        "fatally shot a police officer",
        "patrolman",
        "was indicted",
        "parole violation",
    ]

    if any(t in texto for t in truecrime_comum) and not tem_nucleo:
        return True

    # Filtro extra para r/TrueCrime: evita casos apenas criminais/condenatórios.
    if "r/truecrime" in link_norm and any(t in titulo_norm for t in truecrime_comum):
        return True

    return False


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
    Classifica o status do caso com prioridade editorial.

    Regras principais:
    - Título claramente resolvido/atualização vence.
    - Sinais fortes de caso aberto no título/resumo vencem menções secundárias.
    - Termos como "identified", "recovered" e "DNA" no corpo só viram atualização
      quando aparecem ligados a solução real, prisão, identificação formal ou recuperação de restos.
    """
    titulo_norm = normalizar(titulo)
    texto = normalizar(f"{titulo} {resumo}")

    resolvido_no_titulo = [
        "[arrest]",
        "arrest after",
        "killer identified",
        "has been identified",
        "has been named",
        "arrested",
        "case solved",
        "solved",
        "remains have been recovered",
        "body has been recovered",
        "have been recovered",
        "recovered in",
        "recovered from",
    ]

    if any(t in titulo_norm for t in resolvido_no_titulo):
        return "RESOLVIDO/ATUALIZAÇÃO"

    aberto_forte = [
        "still missing",
        "has been missing",
        "been missing",
        "listed as missing",
        "listed as a missing person",
        "is listed as a missing person",
        "missing from",
        "missing since",
        "went missing",
        "reported missing",
        "never came home",
        "never found",
        "never seen again",
        "never seen him again",
        "never seen her again",
        "loved ones have never seen",
        "no trace",
        "no confirmed sightings",
        "case is still open",
        "remains unsolved",
        "unresolved",
        "not been solved",
        "unsolved",
        "no arrests",
        "no arrest",
        "no one has been arrested",
        "no one has been charged",
        "no suspect",
        "no known suspect",
        "nobody officially knows",
        "no definitive answer",
        "no definitive answers",
        "no closer to finding",
        "where is",
        "what happened to",
        "what became of",
        "who was",
        "who is",
    ]

    if any(t in texto for t in aberto_forte):
        return "ABERTO"

    resolvido_no_resumo = [
        "officially arrested",
        "has been arrested",
        "was arrested",
        "has been named",
        "identified the killer",
        "killer has been identified",
        "case was solved",
        "case has been solved",
        "genetic genealogy breakthrough",
        "recovered the remains",
        "confirmed her identity",
        "confirmed his identity",
        "provided investigators a location",
    ]

    if any(t in texto for t in resolvido_no_resumo):
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
    titulo_norm = normalizar(titulo)

    if caso_famoso_ou_saturado(titulo):
        return "CASO FAMOSO/SATURADO"

    # Identidade desconhecida é um eixo próprio, mesmo quando há homicídio.
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

    if status == "RESOLVIDO/ATUALIZAÇÃO":
        return "CASO RESOLVIDO/ATUALIZAÇÃO"

    # Quando o núcleo do título é homicídio/morte suspeita, não deixar menções genéricas
    # a "missing cases" no resumo transformarem tudo em desaparecimento.
    homicidio_no_titulo = any(t in titulo_norm for t in [
        "murder",
        "murdered",
        "homicide",
        "found dead",
        "body found",
        "shot to death",
        "stabbed",
        "killed",
        "drownings",
        "deaths",
    ])

    desaparecimento_no_titulo = any(t in titulo_norm for t in [
        "missing",
        "went missing",
        "reported missing",
        "disappeared",
        "vanished",
        "never found",
        "no trace",
        "what happened to",
        "what became of",
    ])

    if desaparecimento_no_titulo and not homicidio_no_titulo:
        return "DESAPARECIMENTO ABERTO"

    if homicidio_no_titulo:
        return "HOMICÍDIO/MORTE SUSPEITA"

    if any(t in texto for t in [
        "unsolved homicide",
        "cold homicide",
        "murder",
        "murdered",
        "homicide",
        "found dead",
        "body found",
        "shot to death",
        "stabbed",
        "killed",
        "death was listed as undetermined",
        "suspicious death",
    ]):
        return "HOMICÍDIO/MORTE SUSPEITA"

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
        "what became of",
    ]):
        return "DESAPARECIMENTO ABERTO"

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
# BRIEFING EDITORIAL ESTRATÉGICO
# =========================================================

def texto_curto(texto, limite=180):
    texto = limpar_html(texto)
    if len(texto) <= limite:
        return texto
    corte = texto[:limite].rsplit(" ", 1)[0]
    return corte + "..."


def titulo_provisorio(row):
    caso = str(row.get("Caso", "")).strip()
    tipo = str(row.get("Tipo de Caso", "")).strip()
    ano = str(row.get("Ano do Caso", "")).strip()

    if tipo == "IDENTIDADE DESCONHECIDA":
        return f"Quem era a vítima sem nome? O mistério por trás de {texto_curto(caso, 90)}"

    if tipo == "DESAPARECIMENTO ABERTO":
        return f"A pessoa desapareceu e as pistas não fecham: {texto_curto(caso, 95)}"

    if tipo == "CASO RESOLVIDO/ATUALIZAÇÃO":
        return f"A reviravolta depois de anos sem resposta: {texto_curto(caso, 95)}"

    if tipo == "CASO FAMOSO/SATURADO":
        return f"O detalhe menos discutido de um caso famoso: {texto_curto(caso, 95)}"

    if ano and ano != "Não identificado":
        return f"O caso de {ano} que ainda deixa perguntas abertas"

    return f"O mistério que ainda precisa de resposta: {texto_curto(caso, 100)}"


def angulo_narrativo(row):
    tipo = str(row.get("Tipo de Caso", ""))
    status = str(row.get("Status Detectado", ""))
    elementos = normalizar(row.get("Elementos Detectados", ""))

    if tipo == "IDENTIDADE DESCONHECIDA":
        return "Identidade apagada: construir a narrativa em torno de quem era a vítima, quais pistas físicas existem e por que o nome dela ainda importa."

    if tipo == "DESAPARECIMENTO ABERTO":
        return "Última janela conhecida: reconstruir as últimas horas, o último contato, o deslocamento e os pontos cegos da investigação."

    if tipo == "HOMICÍDIO/MORTE SUSPEITA":
        return "Morte sem resposta clara: focar na cena, nas inconsistências, nos vestígios e nas perguntas que continuam abertas."

    if tipo == "CASO RESOLVIDO/ATUALIZAÇÃO" or status == "RESOLVIDO/ATUALIZAÇÃO":
        return "Virada investigativa: mostrar como o caso mudou com DNA, identificação, prisão ou recuperação de restos, sem tratar como mistério principal."

    if tipo == "CASO FAMOSO/SATURADO":
        return "Ângulo novo obrigatório: evitar repetir o resumo conhecido e escolher um detalhe pouco explorado, uma falha de investigação ou uma linha temporal específica."

    if "cctv" in elementos or "footage" in elementos:
        return "Última imagem: usar o registro visual como ponto de tensão narrativa e voltar no tempo para explicar como o caso chegou ali."

    return "Investigação aberta: organizar o caso como uma sequência de perguntas, pistas e lacunas documentais."


def promessa_do_video(row):
    tipo = str(row.get("Tipo de Caso", ""))
    score = row.get("Score", "")
    ano = row.get("Ano do Caso", "Não identificado")

    if tipo == "IDENTIDADE DESCONHECIDA":
        return f"Mostrar como uma pessoa pode desaparecer até da própria identidade, e por que o caso ainda merece atenção. Score editorial: {score}."

    if tipo == "DESAPARECIMENTO ABERTO":
        return f"Reconstruir o desaparecimento com foco nas últimas pistas confiáveis e nas perguntas que continuam sem resposta desde {ano}."

    if tipo == "CASO RESOLVIDO/ATUALIZAÇÃO":
        return "Explicar a atualização de forma compacta, destacando o que mudou, o que foi confirmado e o que ainda permanece nebuloso."

    if tipo == "CASO FAMOSO/SATURADO":
        return "Entregar valor pelo recorte: não contar tudo de novo, mas encontrar uma pergunta específica que o público ainda não viu bem explicada."

    return "Transformar uma pauta bruta em investigação documental clara, respeitosa e visualmente forte."


def estrutura_roteiro(row):
    hook = str(row.get("Hook", ""))
    tipo = str(row.get("Tipo de Caso", ""))
    ano = str(row.get("Ano do Caso", "Não identificado"))

    blocos = [
        f"1. Abertura fria: {hook}",
        "2. Identificação do caso: quem é a vítima, onde aconteceu e qual é a pergunta central.",
        "3. Linha do tempo: últimas horas, último contato, deslocamento e descoberta inicial.",
        "4. Pistas materiais: objetos, câmera, ligação, veículo, local, testemunhas ou documentos.",
        "5. Lacunas: o que não fecha, o que foi mal explicado e o que ainda precisa ser comprovado.",
        "6. Hipóteses com cuidado: apresentar possibilidades sem acusar pessoas sem prova.",
        "7. Fechamento: estado atual do caso, fontes oficiais e convite para comentário responsável."
    ]

    if tipo == "IDENTIDADE DESCONHECIDA":
        blocos[2] = "3. Perfil físico e vestígios: roupas, objetos, local onde foi encontrada e tentativas de identificação."
        blocos[5] = "6. Hipóteses de identidade: comparar pistas sem transformar especulação em afirmação."

    if tipo == "CASO RESOLVIDO/ATUALIZAÇÃO":
        blocos[0] = "1. Abertura fria: depois de anos sem resposta, uma informação mudou o caso."
        blocos[6] = "7. Fechamento: explicar o que foi resolvido, o que ainda falta e por que isso funciona melhor como short ou atualização."

    if ano and ano != "Não identificado":
        blocos[1] += f" Ano base detectado: {ano}."

    return blocos


def pesquisa_necessaria(row):
    tipo = str(row.get("Tipo de Caso", ""))
    link = str(row.get("Link", ""))

    itens = [
        "Tratar o Reddit apenas como ponto de partida, nunca como fonte final.",
        "Confirmar dados em fontes primárias: polícia local, NamUs, Charley Project, Doe Network, FBI ou registros oficiais.",
        "Montar linha do tempo com datas confirmadas e separar fato, hipótese e opinião de usuário.",
        "Buscar mapa do local, distância entre pontos principais e imagens públicas/licenciáveis.",
        "Checar se houve atualização recente antes de gravar.",
    ]

    if tipo == "IDENTIDADE DESCONHECIDA":
        itens.append("Pesquisar reconstruções faciais, perfil odontológico, roupas, objetos e exclusões oficiais de possíveis identidades.")

    if tipo == "DESAPARECIMENTO ABERTO":
        itens.append("Verificar boletim de desaparecimento, último contato confirmado, veículo, celular, câmeras e movimentação bancária quando disponível.")

    if tipo == "CASO RESOLVIDO/ATUALIZAÇÃO":
        itens.append("Confirmar a atualização em fonte oficial antes de publicar: prisão, identificação, DNA, recuperação de restos ou decisão judicial.")

    if link:
        itens.append(f"Link de partida: {link}")

    return itens


def sugestao_visual(row):
    tipo = str(row.get("Tipo de Caso", ""))
    elementos = normalizar(row.get("Elementos Detectados", ""))

    broll = [
        "Mapa animado com rota e pontos principais.",
        "Recortes de documentos e manchetes com zoom lento.",
        "Fotos de localidade em clima documental, sem gore e sem sensacionalismo.",
        "Timeline visual com datas confirmadas."
    ]

    if "cctv" in elementos or "footage" in elementos or "camera" in elementos:
        broll.append("Recriação visual de câmera de segurança sem simular prova falsa.")

    if "forest" in elementos or "wilderness" in elementos or "trailhead" in elementos:
        broll.append("Estradas, trilhas, placas, mata fechada e paisagens de isolamento.")

    if "river" in elementos or "canal" in elementos:
        broll.append("Água escura, ponte, margem, correnteza e plano aberto do local. Evitar imagens explícitas.")

    if tipo == "IDENTIDADE DESCONHECIDA":
        broll.append("Silhueta, ficha de identificação, objetos pessoais e close em detalhes não gráficos.")

    return broll


def sugestao_thumbnail(row):
    tipo = str(row.get("Tipo de Caso", ""))
    ano = str(row.get("Ano do Caso", ""))

    if tipo == "IDENTIDADE DESCONHECIDA":
        return f"Silhueta sem rosto + etiqueta 'SEM NOME' + ano {ano}. Paleta escura, documento antigo e mapa ao fundo."

    if tipo == "DESAPARECIMENTO ABERTO":
        return f"Mapa/local isolado + marcador vermelho + texto curto: 'SUMIU EM {ano}' ou 'ÚLTIMO RASTRO'."

    if tipo == "CASO RESOLVIDO/ATUALIZAÇÃO":
        return "Antes/depois editorial: '50 ANOS DEPOIS' / 'DNA REVELOU?' com visual de arquivo policial."

    if tipo == "CASO FAMOSO/SATURADO":
        return "Evitar rosto/foto conhecida como centro. Usar detalhe novo: mapa, horário, objeto ou última câmera."

    return "Imagem de local + documento desfocado + pergunta curta e forte, sem exagero visual."


def gerar_markdown_briefing(df):
    if df.empty:
        return "# Briefings Sem Rastros\n\nNenhum caso aprovado para briefing nesta execução.\n"

    df_brief = df[df["Decisão Editorial"].isin([
        "PRIORIDADE DE ROTEIRO",
        "ENTRA NA LISTA CURTA",
        "USAR COMO ATUALIZAÇÃO/SHORT",
        "USAR COMO NOTA CURTA",
        "APENAS COM GANCHO DIFERENCIADO",
    ])].copy()

    if df_brief.empty:
        df_brief = df.head(10).copy()

    linhas = [
        "# Briefings Editoriais — Sem Rastros",
        "",
        "Documento gerado automaticamente pelo Radar Cinematográfico Profissional.",
        "Use estes briefings como base de apuração, não como roteiro final sem checagem.",
        "",
    ]

    for i, (_, row) in enumerate(df_brief.head(12).iterrows(), start=1):
        linhas.extend([
            f"## {i}. {row['Caso']}",
            "",
            f"**Score:** {row['Score']}  ",
            f"**Classificação:** {row['Classificação']}  ",
            f"**Tipo de Caso:** {row['Tipo de Caso']}  ",
            f"**Uso recomendado:** {row['Uso Recomendado']}  ",
            f"**Decisão editorial:** {row['Decisão Editorial']}  ",
            f"**Segurança da pauta:** {row['Segurança da Pauta']}  ",
            f"**Ano do caso:** {row['Ano do Caso']}  ",
            "",
            f"### Título provisório\n{titulo_provisorio(row)}",
            "",
            f"### Promessa do vídeo\n{promessa_do_video(row)}",
            "",
            f"### Ângulo narrativo\n{angulo_narrativo(row)}",
            "",
            f"### Hook\n{row['Hook']}",
            "",
            "### Estrutura sugerida",
        ])

        for bloco in estrutura_roteiro(row):
            linhas.append(f"- {bloco}")

        linhas.extend(["", "### Pesquisa obrigatória"])
        for item in pesquisa_necessaria(row):
            linhas.append(f"- {item}")

        linhas.extend(["", "### B-roll e visual"])
        for item in sugestao_visual(row):
            linhas.append(f"- {item}")

        linhas.extend([
            "",
            f"### Thumbnail\n{sugestao_thumbnail(row)}",
            "",
            f"### Motivo editorial\n{row['Motivo Editorial']}",
            "",
            "---",
            "",
        ])

    return "\n".join(linhas).strip() + "\n"


def salvar_briefing_markdown(df):
    os.makedirs(PASTA_RESULTADOS, exist_ok=True)
    conteudo = gerar_markdown_briefing(df)
    with open(BRIEFING_MD_SAIDA, "w", encoding="utf-8") as arquivo:
        arquivo.write(conteudo)


def gerar_briefing_pdf(df):
    os.makedirs(PASTA_RESULTADOS, exist_ok=True)

    pdf = SimpleDocTemplate(BRIEFING_PDF_SAIDA)
    styles = getSampleStyleSheet()
    conteudo = []

    conteudo.append(Paragraph("<b>BRIEFINGS EDITORIAIS — SEM RASTROS</b>", styles["Title"]))
    conteudo.append(Spacer(1, 18))

    if df.empty:
        conteudo.append(Paragraph("Nenhum caso aprovado para briefing nesta execução.", styles["BodyText"]))
        pdf.build(conteudo)
        return

    df_brief = df[df["Decisão Editorial"].isin([
        "PRIORIDADE DE ROTEIRO",
        "ENTRA NA LISTA CURTA",
        "USAR COMO ATUALIZAÇÃO/SHORT",
        "USAR COMO NOTA CURTA",
        "APENAS COM GANCHO DIFERENCIADO",
    ])].copy()

    if df_brief.empty:
        df_brief = df.head(10).copy()

    for i, (_, row) in enumerate(df_brief.head(12).iterrows(), start=1):
        estrutura_html = "<br/>".join(seguro_pdf(item) for item in estrutura_roteiro(row))
        pesquisa_html = "<br/>".join(seguro_pdf(item) for item in pesquisa_necessaria(row)[:6])
        visual_html = "<br/>".join(seguro_pdf(item) for item in sugestao_visual(row)[:6])

        texto = f"""
        <b>{i}. Caso:</b> {seguro_pdf(row['Caso'])}<br/>
        <b>Score:</b> {seguro_pdf(row['Score'])}<br/>
        <b>Tipo:</b> {seguro_pdf(row['Tipo de Caso'])}<br/>
        <b>Uso recomendado:</b> {seguro_pdf(row['Uso Recomendado'])}<br/>
        <b>Decisão editorial:</b> {seguro_pdf(row['Decisão Editorial'])}<br/>
        <b>Título provisório:</b> {seguro_pdf(titulo_provisorio(row))}<br/>
        <b>Promessa:</b> {seguro_pdf(promessa_do_video(row))}<br/>
        <b>Ângulo narrativo:</b> {seguro_pdf(angulo_narrativo(row))}<br/>
        <b>Hook:</b> {seguro_pdf(row['Hook'])}<br/>
        <b>Estrutura sugerida:</b><br/>{estrutura_html}<br/>
        <b>Pesquisa obrigatória:</b><br/>{pesquisa_html}<br/>
        <b>B-roll e visual:</b><br/>{visual_html}<br/>
        <b>Thumbnail:</b> {seguro_pdf(sugestao_thumbnail(row))}<br/><br/>
        """
        conteudo.append(Paragraph(texto, styles["BodyText"]))
        conteudo.append(Spacer(1, 20))

    pdf.build(conteudo)


def gerar_briefings(df):
    salvar_briefing_markdown(df)
    gerar_briefing_pdf(df)


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
        df_pdf = df[df["Decisão Editorial"] != "DESCARTAR POR ENQUANTO"].copy()
        if df_pdf.empty:
            df_pdf = df.copy()

        for _, row in df_pdf.head(20).iterrows():
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
    print(f"BRIEFING MD SALVO EM: {BRIEFING_MD_SAIDA}")
    print(f"BRIEFING PDF SALVO EM: {BRIEFING_PDF_SAIDA}")


if __name__ == "__main__":
    main()
