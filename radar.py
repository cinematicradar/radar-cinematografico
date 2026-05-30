from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import feedparser
import pandas as pd
import random
import re
import os
import html
from datetime import datetime


# =========================
# CONFIGURAÇÕES GERAIS
# =========================

ANO_ATUAL = datetime.now().year

PASTA_RESULTADOS = "resultados"
CSV_SAIDA = f"{PASTA_RESULTADOS}/casos_cinematicos.csv"
PDF_SAIDA = f"{PASTA_RESULTADOS}/dossie_cinematografico.pdf"

rss_feeds = [
    "https://www.reddit.com/r/UnresolvedMysteries/.rss",
    "https://www.reddit.com/r/MissingPersons/.rss",
    "https://www.reddit.com/r/TrueCrime/.rss",
    "https://www.reddit.com/r/UnsolvedMysteries/.rss"
]


# =========================
# LIMPEZA E SEGURANÇA
# =========================

def limpar_html(texto):
    texto = str(texto)
    texto = re.sub(r"<[^>]+>", " ", texto)
    texto = texto.replace("&amp;", "&")
    texto = texto.replace("&#39;", "'")
    texto = texto.replace("&quot;", '"')
    texto = texto.replace("&lt;", "<")
    texto = texto.replace("&gt;", ">")
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def seguro_pdf(texto):
    return html.escape(str(texto))


def contem(texto, termo):
    """
    Busca termo com fronteira de palavra.
    Evita falso positivo tipo 'man' dentro de 'woman'.
    """
    termo = termo.lower().strip()
    texto = texto.lower()

    padrao = r"(?<!\w)" + re.escape(termo).replace(r"\ ", r"\s+") + r"(?!\w)"
    return re.search(padrao, texto) is not None


def resumo_inutil(resumo):
    resumo = limpar_html(resumo).lower()

    if not resumo:
        return True

    lixo = resumo
    for termo in ["submitted by", "[link]", "[comments]", "comments", "link"]:
        lixo = lixo.replace(termo, "")

    lixo = re.sub(r"[^a-zA-Z0-9À-ÿ]+", " ", lixo).strip()

    return len(lixo) < 80


def titulo_meta_ou_inutil(titulo):
    titulo = titulo.lower()

    termos_bloqueio = [
        "megathread",
        "podcast",
        "for a video",
        "researching",
        "recommendations",
        "looking for cases",
        "what are your thoughts",
        "does anyone remember",
        "help me find",
        "discussion thread",
        "weekly thread"
    ]

    return any(termo in titulo for termo in termos_bloqueio)


def extrair_anos(texto):
    anos = re.findall(r"\b(19[0-9]{2}|20[0-2][0-9])\b", texto)
    return [int(a) for a in anos]


# =========================
# SCORE PROFISSIONAL V4
# =========================

def calcular_score_profissional(titulo, resumo):
    resumo_util = not resumo_inutil(resumo)

    if resumo_util:
        texto = f"{titulo} {resumo}".lower()
    else:
        texto = titulo.lower()

    elementos = []
    categorias = {}

    # 1. Mistério central — obrigatório para entrar forte
    misterio = 0
    termos_misterio = {
        "missing": 18,
        "disappearance": 18,
        "disappeared": 18,
        "vanished": 22,
        "without trace": 25,
        "no trace": 22,
        "never found": 22,
        "still missing": 22,
        "unsolved": 18,
        "cold case": 20,
        "jane doe": 20,
        "john doe": 20,
        "unidentified": 18,
        "body found": 14,
        "remains": 14,
        "murdered": 12,
        "murder": 10
    }

    for termo, pontos in termos_misterio.items():
        if contem(texto, termo):
            misterio = max(misterio, pontos)
            elementos.append(f"{termo} / mistério central")

    categorias["Mistério Central"] = min(misterio, 25)

    # 2. Tempo sem solução
    tempo = 0

    anos = extrair_anos(texto)
    if anos:
        ano_mais_antigo = min(anos)
        idade_caso = ANO_ATUAL - ano_mais_antigo

        if idade_caso >= 40:
            tempo += 20
            elementos.append(f"{idade_caso} anos sem resposta / tempo histórico")
        elif idade_caso >= 25:
            tempo += 16
            elementos.append(f"{idade_caso} anos sem resposta / tempo relevante")
        elif idade_caso >= 10:
            tempo += 11
            elementos.append(f"{idade_caso} anos sem resposta / caso antigo")
        elif idade_caso >= 3:
            tempo += 6
            elementos.append(f"{idade_caso} anos sem resposta / caso recente")

    for termo, pontos in {
        "decades": 18,
        "50 years": 20,
        "40 years": 18,
        "30 years": 16,
        "20 years": 14,
        "10 years": 10,
        "years later": 8
    }.items():
        if contem(texto, termo):
            tempo = max(tempo, pontos)
            elementos.append(f"{termo} / tempo sem solução")

    categorias["Tempo Sem Solução"] = min(tempo, 20)

    # 3. Último registro / prova visual
    prova = 0
    for termo, pontos in {
        "last seen": 18,
        "last image": 18,
        "cctv": 20,
        "surveillance": 18,
        "footage": 16,
        "camera": 12,
        "photo": 8,
        "photograph": 8,
        "phone call": 10
    }.items():
        if contem(texto, termo):
            prova += pontos
            elementos.append(f"{termo} / último registro ou prova visual")

    categorias["Prova Visual ou Último Registro"] = min(prova, 20)

    # 4. Ambiente cinematográfico
    ambiente = 0
    for termo, pontos in {
        "national park": 14,
        "forest": 12,
        "woods": 12,
        "mountain": 12,
        "airport": 12,
        "island": 12,
        "highway": 10,
        "road": 8,
        "river": 10,
        "canal": 10,
        "train": 10,
        "hotel": 8,
        "motel": 8,
        "night": 8,
        "snow": 8,
        "desert": 8
    }.items():
        if contem(texto, termo):
            ambiente += pontos
            elementos.append(f"{termo} / cenário cinematográfico")

    categorias["Ambiente Cinematográfico"] = min(ambiente, 15)

    # 5. Complexidade investigativa
    investigacao = 0
    for termo, pontos in {
        "false trails": 14,
        "missing files": 14,
        "foul play": 12,
        "arrest": 8,
        "identified": 8,
        "investigation": 10,
        "police": 6,
        "theory": 6,
        "theories": 8,
        "inheritance dispute": 10,
        "unknown": 8
    }.items():
        if contem(texto, termo):
            investigacao += pontos
            elementos.append(f"{termo} / complexidade investigativa")

    categorias["Complexidade Investigativa"] = min(investigacao, 18)

    # 6. Impacto humano — pontuação pequena, para não inflar
    impacto = 0
    for termo, pontos in {
        "child": 10,
        "teen": 8,
        "teenager": 8,
        "15 year old": 10,
        "daughter": 7,
        "mother": 6,
        "father": 6,
        "family": 5
    }.items():
        if contem(texto, termo):
            impacto += pontos
            elementos.append(f"{termo} / impacto humano")

    categorias["Impacto Humano"] = min(impacto, 10)

    score = sum(categorias.values())

    # Penalidade se o resumo do RSS não trouxer conteúdo real
    if not resumo_util:
        score -= 7
        elementos.append("resumo RSS ausente ou pobre / exige apuração manual")

    # Penalidade para título sem nome próprio ou sem especificidade
    if len(titulo.split()) < 6:
        score -= 8
        elementos.append("título curto ou pouco específico / baixa segurança editorial")

    # Caso sem mistério central claro não deve ser supervalorizado
    if categorias["Mistério Central"] < 10:
        score -= 15
        elementos.append("mistério central fraco / risco de pauta genérica")

    score = max(0, min(score, 100))

    return score, elementos, categorias, resumo_util


# =========================
# CLASSIFICAÇÕES
# =========================

def potencial_documental(score):
    if score >= 88:
        return "Muito Alto"
    elif score >= 72:
        return "Alto"
    elif score >= 52:
        return "Médio"
    return "Baixo"


def relevancia_sem_rastros(score):
    if score >= 88:
        return "ALTÍSSIMA"
    elif score >= 72:
        return "ALTA"
    elif score >= 52:
        return "MÉDIA"
    return "BAIXA"


def classificacao_caso(score):
    if score >= 88:
        return "CASO PRINCIPAL"
    elif score >= 72:
        return "MUITO FORTE"
    elif score >= 52:
        return "OBSERVAR"
    return "BAIXO"


def decisao_editorial(score, resumo_util):
    if score >= 88 and resumo_util:
        return "PRIORIDADE DE ROTEIRO"
    elif score >= 88 and not resumo_util:
        return "PRIORIDADE APOS APURACAO"
    elif score >= 72:
        return "ENTRA NA LISTA CURTA"
    elif score >= 52:
        return "GUARDAR PARA PESQUISA"
    return "DESCARTAR POR ENQUANTO"


def motivo_editorial(categorias, elementos, resumo_util):
    motivos = []

    if categorias.get("Mistério Central", 0) >= 18:
        motivos.append("tem mistério central claro")

    if categorias.get("Tempo Sem Solução", 0) >= 12:
        motivos.append("possui peso histórico ou longa duração sem resposta")

    if categorias.get("Prova Visual ou Último Registro", 0) >= 12:
        motivos.append("oferece elemento forte de último registro, imagem, câmera ou pista visual")

    if categorias.get("Ambiente Cinematográfico", 0) >= 10:
        motivos.append("possui cenário com potencial visual para documentário")

    if categorias.get("Complexidade Investigativa", 0) >= 10:
        motivos.append("tem linhas investigativas, suspeitas ou perguntas abertas")

    if categorias.get("Impacto Humano", 0) >= 6:
        motivos.append("carrega conexão emocional com vítima ou família")

    if not resumo_util:
        motivos.append("mas exige apuração manual porque o RSS não trouxe resumo confiável")

    if motivos:
        return "Caso selecionado porque " + "; ".join(motivos) + "."

    return "Caso com potencial limitado; precisa de pesquisa complementar antes de virar pauta."


def gerar_hook(titulo, elementos):
    texto = f"{titulo} {' '.join(elementos)}".lower()

    if "jane doe" in texto or "john doe" in texto or "unidentified" in texto:
        return "Por anos, ninguém sabia quem era a vítima — e a identidade pode ser só o começo do mistério."

    if "cctv" in texto or "camera" in texto or "footage" in texto:
        return "A última imagem parecia comum, mas se tornou uma das pistas mais inquietantes do caso."

    if "vanished" in texto or "without trace" in texto or "no trace" in texto:
        return "A pessoa desapareceu sem deixar rastro, e cada detalhe parece abrir uma nova pergunta."

    if "50 years" in texto or "40 years" in texto or "30 years" in texto or "decades" in texto:
        return "Décadas se passaram, mas uma pergunta continuou sem resposta."

    return random.choice([
        "O caso parecia simples, até os detalhes começarem a não fazer sentido.",
        "A última vez que alguém o viu, tudo parecia normal.",
        "As autoridades tinham pistas, mas nenhuma resposta definitiva.",
        "O desaparecimento começou como uma ocorrência comum e virou um mistério inquietante."
    ])


# =========================
# COLETA
# =========================

todos_posts = []

for url in rss_feeds:
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            todos_posts.append(entry)
    except Exception as erro:
        print(f"Erro ao ler feed {url}: {erro}")


# =========================
# PROCESSAMENTO
# =========================

dados = []
links_vistos = set()
titulos_vistos = set()

for entry in todos_posts:
    titulo = getattr(entry, "title", "").strip()
    resumo_original = limpar_html(getattr(entry, "summary", ""))
    link = getattr(entry, "link", "").strip()

    if not titulo:
        continue

    if titulo_meta_ou_inutil(titulo):
        continue

    chave_titulo = titulo.lower()
    chave_link = link.lower()

    if chave_link in links_vistos or chave_titulo in titulos_vistos:
        continue

    links_vistos.add(chave_link)
    titulos_vistos.add(chave_titulo)

    score, elementos, categorias, resumo_util = calcular_score_profissional(titulo, resumo_original)

    # Corte editorial realista
    if score < 45:
        continue

    if not resumo_util:
        resumo_exibido = (
            "Resumo não disponível no RSS. Caso selecionado pelo potencial do título; "
            "abrir o link para apuração completa antes da produção."
        )
    else:
        resumo_exibido = resumo_original[:1500]

    dados.append({
        "Caso": titulo,
        "Resumo Original": resumo_exibido,
        "Score": score,
        "Potencial Documental": potencial_documental(score),
        "Relevância para Sem Rastros": relevancia_sem_rastros(score),
        "Classificação": classificacao_caso(score),
        "Decisão Editorial": decisao_editorial(score, resumo_util),
        "Atmosfera": ", ".join(elementos[:18]),
        "Motivo Editorial": motivo_editorial(categorias, elementos, resumo_util),
        "Hook": gerar_hook(titulo, elementos),
        "Link": link
    })


# =========================
# DATAFRAME E CSV
# =========================

os.makedirs(PASTA_RESULTADOS, exist_ok=True)

colunas = [
    "Caso",
    "Resumo Original",
    "Score",
    "Potencial Documental",
    "Relevância para Sem Rastros",
    "Classificação",
    "Decisão Editorial",
    "Atmosfera",
    "Motivo Editorial",
    "Hook",
    "Link"
]

if dados:
    df = pd.DataFrame(dados, columns=colunas)
    df = df.sort_values(by="Score", ascending=False)
else:
    df = pd.DataFrame(columns=colunas)

print(df.head(20))

df.to_csv(CSV_SAIDA, index=False)

print("\nRADAR CINEMATOGRÁFICO PROFISSIONAL FINALIZADO")
print(f"CSV SALVO EM {CSV_SAIDA}")


# =========================
# PDF
# =========================

pdf = SimpleDocTemplate(PDF_SAIDA)
styles = getSampleStyleSheet()
conteudo = []

titulo_pdf = Paragraph(
    "<b>RADAR CINEMATOGRÁFICO PROFISSIONAL SEM RASTROS</b>",
    styles["Title"]
)

conteudo.append(titulo_pdf)
conteudo.append(Spacer(1, 20))

if df.empty:
    texto = """
    <b>Nenhum caso válido encontrado nesta execução.</b><br/>
    O radar rodou corretamente, mas os feeds não retornaram casos acima do corte editorial mínimo.
    """
    conteudo.append(Paragraph(texto, styles["BodyText"]))
else:
    for index, row in df.head(20).iterrows():
        texto = f"""
        <b>Caso:</b> {seguro_pdf(row['Caso'])}<br/>
        <b>Resumo:</b> {seguro_pdf(row['Resumo Original'])}<br/>
        <b>Score:</b> {seguro_pdf(row['Score'])}<br/>
        <b>Potencial:</b> {seguro_pdf(row['Potencial Documental'])}<br/>
        <b>Relevância Sem Rastros:</b> {seguro_pdf(row['Relevância para Sem Rastros'])}<br/>
        <b>Classificação:</b> {seguro_pdf(row['Classificação'])}<br/>
        <b>Decisão Editorial:</b> {seguro_pdf(row['Decisão Editorial'])}<br/>
        <b>Elementos Detectados:</b> {seguro_pdf(row['Atmosfera'])}<br/>
        <b>Motivo Editorial:</b> {seguro_pdf(row['Motivo Editorial'])}<br/>
        <b>Hook:</b> {seguro_pdf(row['Hook'])}<br/>
        <b>Link:</b> {seguro_pdf(row['Link'])}<br/><br/>
        """

        conteudo.append(Paragraph(texto, styles["BodyText"]))
        conteudo.append(Spacer(1, 20))

pdf.build(conteudo)

print(f"PDF SALVO EM {PDF_SAIDA}")
