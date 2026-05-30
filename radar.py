from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import feedparser
import pandas as pd
import random
import re
import os

# =========================
# FUNÇÕES AUXILIARES
# =========================

def limpar_html(texto):
    texto = re.sub(r'<[^>]+>', '', str(texto))
    texto = texto.replace("&amp;", "&")
    texto = texto.replace("&#39;", "'")
    texto = texto.replace("&quot;", '"')
    return texto.strip()

def post_vazio(resumo):
    resumo = str(resumo).lower().strip()
    termos_lixo = ["submitted by", "[link]", "[comments]"]
    if not resumo or len(resumo) < 40:
        return True
    return all(termo in resumo for termo in termos_lixo)

def calcular_score(titulo, resumo):
    texto = f"{titulo} {resumo}".lower()

    # Categorias ponderadas
    categorias = {
        "mistério central": {"missing": 20, "disappearance": 20, "vanished": 25, "without trace": 25, "unsolved": 20, "cold case": 20},
        "impacto humano": {"child": 25, "teen": 15, "teenager": 15, "woman": 15, "man": 10, "family": 15},
        "ambiente cinematográfico": {"forest": 15, "woods": 15, "park": 15, "national park": 20, "mountain": 15, "night": 10},
        "prova visual": {"cctv": 20, "camera": 15, "surveillance": 20},
        "tempo sem solução": {"last seen": 20, "never found": 20, "still missing": 20}
    }

    score_total = 0
    elementos_detectados = []

    for categoria, termos in categorias.items():
        score_cat = 0
        for termo, pontos in termos.items():
            if termo in texto:
                score_cat += pontos
                elementos_detectados.append(f"{termo} ({categoria})")
        # Limitar score de cada categoria para não inflar demais
        score_total += min(score_cat, 30)

    # Normaliza o score para 0-100
    score_total = min(score_total, 100)
    return score_total, elementos_detectados

def potencial_documental(score):
    if score >= 80:
        return "Muito Alto"
    elif score >= 60:
        return "Alto"
    elif score >= 35:
        return "Médio"
    return "Baixo"

def relevancia_sem_rastros(score):
    if score >= 80:
        return "ALTÍSSIMA"
    elif score >= 60:
        return "ALTA"
    elif score >= 35:
        return "MÉDIA"
    return "BAIXA"

def classificacao_caso(score):
    if score >= 80:
        return "🔥 CASO NETFLIX"
    elif score >= 60:
        return "⚠️ MUITO FORTE"
    elif score >= 35:
        return "🟡 OBSERVAR"
    return "⚪ BAIXO"

def motivo_editorial(score, elementos):
    if score >= 80:
        return "Caso com forte potencial documental, atmosfera de mistério e narrativa cinematográfica completa."
    elif score >= 60:
        return "Caso relevante para roteiro investigativo, com bons elementos narrativos."
    elif score >= 35:
        return "Caso interessante, precisa de apuração adicional para gerar conteúdo de qualidade."
    return "Caso pouco relevante, deve ser usado apenas como referência."

# =========================
# FEEDS E CONFIGURAÇÕES
# =========================

rss_feeds = [
    "https://www.reddit.com/r/UnresolvedMysteries/.rss",
    "https://www.reddit.com/r/MissingPersons/.rss",
    "https://www.reddit.com/r/TrueCrime/.rss",
    "https://www.reddit.com/r/UnsolvedMysteries/.rss"
]

todos_posts = []

for url in rss_feeds:
    feed = feedparser.parse(url)
    for entry in feed.entries:
        todos_posts.append(entry)

# =========================
# PROCESSAMENTO DOS POSTS
# =========================

dados = []

for entry in todos_posts:
    titulo = getattr(entry, "title", "")
    resumo_original = limpar_html(getattr(entry, "summary", ""))
    link = getattr(entry, "link", "")

    if not titulo:
        continue
    if post_vazio(resumo_original):
        continue

    score, elementos_detectados = calcular_score(titulo, resumo_original)

    # Se score baixo, ignora
    if score < 20:
        continue

    # Preenchimento automático de resumo se vazio
    if not resumo_original:
        resumo_original = "Resumo não disponível no RSS. Avaliar o caso pelo título e abrir o link para apuração completa."

    hook = random.choice([
        "A última vez que alguém o viu... tudo parecia normal.",
        "As autoridades nunca conseguiram explicar o que aconteceu naquela noite.",
        "A última imagem registrada ainda causa arrepios.",
        "Ele saiu normalmente... e nunca mais voltou.",
        "O caso parecia simples, até os detalhes começarem a não fazer sentido."
    ])

    dados.append({
        "Caso": titulo,
        "Resumo Original": resumo_original[:1500],
        "Score": score,
        "Potencial Documental": potencial_documental(score),
        "Relevância para Sem Rastros": relevancia_sem_rastros(score),
        "Classificação": classificacao_caso(score),
        "Atmosfera": ", ".join(elementos_detectados),
        "Motivo Editorial": motivo_editorial(score, elementos_detectados),
        "Hook": hook,
        "Link": link
    })

# =========================
# SALVAR CSV
# =========================

os.makedirs("resultados", exist_ok=True)

colunas = [
    "Caso", "Resumo Original", "Score", "Potencial Documental",
    "Relevância para Sem Rastros", "Classificação", "Atmosfera",
    "Motivo Editorial", "Hook", "Link"
]

df = pd.DataFrame(dados, columns=colunas)
df = df.sort_values(by="Score", ascending=False)
df.to_csv("resultados/casos_cinematicos.csv", index=False)
print("✅ CSV gerado em resultados/casos_cinematicos.csv")

# =========================
# GERAR PDF DOCUMENTAL
# =========================

pdf = SimpleDocTemplate("resultados/dossie_cinematografico.pdf")
styles = getSampleStyleSheet()
conteudo = []

titulo_pdf = Paragraph("<b>RADAR CINEMATOGRÁFICO PROFISSIONAL SEM RASTROS</b>", styles["Title"])
conteudo.append(titulo_pdf)
conteudo.append(Spacer(1, 20))

if df.empty:
    texto = "<b>Nenhum caso válido encontrado nesta execução.</b>"
    conteudo.append(Paragraph(texto, styles["BodyText"]))
else:
    for index, row in df.head(20).iterrows():
        texto = f"""
        <b>Caso:</b> {row['Caso']}<br/>
        <b>Resumo:</b> {row['Resumo Original']}<br/>
        <b>Score:</b> {row['Score']}<br/>
        <b>Potencial:</b> {row['Potencial Documental']}<br/>
        <b>Relevância Sem Rastros:</b> {row['Relevância para Sem Rastros']}<br/>
        <b>Classificação:</b> {row['Classificação']}<br/>
        <b>Atmosfera:</b> {row['Atmosfera']}<br/>
        <b>Motivo Editorial:</b> {row['Motivo Editorial']}<br/>
        <b>Hook:</b> {row['Hook']}<br/>
        <b>Link:</b> {row['Link']}<br/><br/>
        """
        conteudo.append(Paragraph(texto, styles["BodyText"]))
        conteudo.append(Spacer(1, 20))

pdf.build(conteudo)
print("✅ PDF gerado em resultados/dossie_cinematografico.pdf")
