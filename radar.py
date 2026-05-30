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
    if not resumo or len(resumo) < 80:
        return True
    return all(termo in resumo for termo in termos_lixo)

def score_cinematografico_v2(titulo, resumo):
    texto = f"{titulo} {resumo}".lower()
    score = 0

    regras = {
        "desaparecido há mais de 10 anos": 20,
        "missing for over 10 years": 20,
        "unsolved": 20,
        "sem solução": 20,
        "last seen": 15,
        "última vez visto": 15,
        "forest": 15,
        "woods": 15,
        "park": 15,
        "parque": 15,
        "floresta": 15,
        "teen": 15,
        "teenager": 15,
        "adolescente": 15,
        "child": 25,
        "criança": 25,
        "cctv": 20,
        "camera": 20,
        "surveillance": 20,
        "multiple theories": 20,
        "theories": 20,
        "caso famoso": 25,
        "famous case": 25,
        "still searching": 15,
        "busca ativa": 15
    }

    for termo, pontos in regras.items():
        if termo in texto:
            score += pontos

    return min(score, 100)

def relevancia_sem_rastros(score):
    if score >= 80:
        return "ALTÍSSIMA"
    elif score >= 60:
        return "ALTA"
    elif score >= 40:
        return "MÉDIA"
    return "BAIXA"

# =========================
# CONFIGURAÇÕES DO RADAR
# =========================

rss_feeds = [
    "https://www.reddit.com/r/UnresolvedMysteries/.rss",
    "https://www.reddit.com/r/MissingPersons/.rss",
    "https://www.reddit.com/r/TrueCrime/.rss",
    "https://www.reddit.com/r/UnsolvedMysteries/.rss"
]

palavras_chave = ["missing", "disappearance", "vanished", "gone", "without trace"]

elementos_netflix = {
    "cctv": 25,
    "camera": 20,
    "last seen": 30,
    "forest": 25,
    "woods": 25,
    "hotel": 20,
    "motel": 20,
    "highway": 20,
    "road": 15,
    "night": 15,
    "snow": 20,
    "mountain": 20,
    "park": 15,
    "national park": 30,
    "trip": 15,
    "phone call": 25,
    "strange": 15,
    "disturbing": 20,
    "creepy": 20,
    "vanished": 30,
    "without trace": 40
}

# =========================
# COLETA DOS POSTS
# =========================

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
    titulo = entry.title.lower()
    resumo_original = limpar_html(getattr(entry, "summary", ""))

    # FILTRO DE POSTS VAZIOS
    if post_vazio(resumo_original):
        continue

    if not any(p in titulo for p in palavras_chave):
        continue

    score = 0
    elementos_detectados = []

    for elemento, pontos in elementos_netflix.items():
        if elemento in titulo:
            score += pontos
            elementos_detectados.append(elemento)

    if score > 100:
        score = 100

    if score >= 80:
        nivel = "🔥 CASO NETFLIX"
    elif score >= 60:
        nivel = "⚠️ MUITO FORTE"
    else:
        nivel = "🟡 MÉDIO"

    # SCORE CINEMATOGRÁFICO V2
    score = score_cinematografico_v2(entry.title, resumo_original)
    relevancia = relevancia_sem_rastros(score)

    hook = random.choice([
        "A última vez que alguém o viu... tudo parecia normal.",
        "As autoridades nunca conseguiram explicar o que aconteceu naquela noite.",
        "A última imagem registrada ainda causa arrepios.",
        "Ele saiu normalmente... e nunca mais voltou."
    ])

    dados.append({
        "Caso": entry.title,
        "Resumo Original": resumo_original[:1500],
        "Score": score,
        "Potencial Documental": "Muito Alto" if score >= 80 else "Alto" if score >= 60 else "Médio" if score >= 40 else "Baixo",
        "Relevância para Sem Rastros": relevancia,
        "Classificação": nivel,
        "Atmosfera": ", ".join(elementos_detectados),
        "Hook": hook,
        "Link": entry.link
    })

# =========================
# CRIAR DATAFRAME
# =========================

df = pd.DataFrame(dados)
df = df.sort_values(by="Score", ascending=False)
print(df.head(20))
print("\n✅ RADAR CINEMATOGRÁFICO FINALIZADO")

# =========================
# SALVAR RESULTADOS CSV
# =========================

os.makedirs("resultados", exist_ok=True)
df.to_csv("resultados/casos_cinematicos.csv", index=False)
print("\n✅ RESULTADOS SALVOS")

# =========================
# GERAR PDF
# =========================

pdf = SimpleDocTemplate("resultados/dossie_cinematografico.pdf")
styles = getSampleStyleSheet()
conteudo = []

titulo = Paragraph("<b>RADAR CINEMATOGRÁFICO DE DESAPARECIMENTOS</b>", styles['Title'])
conteudo.append(titulo)
conteudo.append(Spacer(1, 20))

for index, row in df.head(15).iterrows():
    texto = f"""
    <b>Caso:</b> {row['Caso']}<br/>
    <b>Resumo:</b> {row['Resumo Original']}<br/>
    <b>Potencial:</b> {row['Potencial Documental']}<br/>
    <b>Score:</b> {row['Score']}<br/>
    <b>Relevância:</b> {row['Relevância para Sem Rastros']}<br/>
    <b>Classificação:</b> {row['Classificação']}<br/>
    <b>Atmosfera:</b> {row['Atmosfera']}<br/>
    <b>Hook:</b> {row['Hook']}<br/>
    <b>Link:</b> {row['Link']}<br/><br/>
"""
    paragrafo = Paragraph(texto, styles['BodyText'])
    conteudo.append(paragrafo)
    conteudo.append(Spacer(1, 20))

pdf.build(conteudo)
print("\n✅ PDF DOCUMENTAL GERADO")
