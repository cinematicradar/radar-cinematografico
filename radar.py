from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import feedparser
import pandas as pd
import random
import re
import os


def limpar_html(texto):
    texto = re.sub(r'<[^>]+>', '', str(texto))
    texto = texto.replace("&amp;", "&")
    texto = texto.replace("&#39;", "'")
    texto = texto.replace("&quot;", '"')
    return texto.strip()


def post_vazio(resumo):
    resumo = str(resumo).lower().strip()

    termos_lixo = [
        "submitted by",
        "[link]",
        "[comments]"
    ]

    if not resumo or len(resumo) < 40:
        return True

    return all(termo in resumo for termo in termos_lixo)


def score_cinematografico_v2(titulo, resumo):
    texto = f"{titulo} {resumo}".lower()
    score = 0

    regras = {
        "missing": 15,
        "disappearance": 15,
        "vanished": 20,
        "without trace": 25,
        "gone": 10,
        "unsolved": 20,
        "cold case": 20,
        "last seen": 20,
        "cctv": 20,
        "camera": 15,
        "surveillance": 20,
        "forest": 15,
        "woods": 15,
        "park": 15,
        "national park": 25,
        "mountain": 15,
        "snow": 15,
        "night": 10,
        "hotel": 10,
        "motel": 10,
        "highway": 10,
        "road": 10,
        "phone call": 15,
        "strange": 10,
        "disturbing": 15,
        "creepy": 15,
        "theories": 15,
        "multiple theories": 20,
        "child": 25,
        "teen": 15,
        "teenager": 15,
        "still searching": 15,
        "famous case": 20
    }

    elementos_detectados = []

    for termo, pontos in regras.items():
        if termo in texto:
            score += pontos
            elementos_detectados.append(termo)

    return min(score, 100), elementos_detectados


def potencial_documental(score):
    if score >= 80:
        return "Muito Alto"
    elif score >= 60:
        return "Alto"
    elif score >= 40:
        return "Médio"
    return "Baixo"


def relevancia_sem_rastros(score):
    if score >= 80:
        return "ALTÍSSIMA"
    elif score >= 60:
        return "ALTA"
    elif score >= 40:
        return "MÉDIA"
    return "BAIXA"


def classificacao_caso(score):
    if score >= 80:
        return "🔥 CASO NETFLIX"
    elif score >= 60:
        return "⚠️ MUITO FORTE"
    elif score >= 40:
        return "🟡 MÉDIO"
    return "⚪ BAIXO"


rss_feeds = [
    "https://www.reddit.com/r/UnresolvedMysteries/.rss",
    "https://www.reddit.com/r/MissingPersons/.rss",
    "https://www.reddit.com/r/TrueCrime/.rss",
    "https://www.reddit.com/r/UnsolvedMysteries/.rss"
]


palavras_chave = [
    "missing",
    "disappearance",
    "vanished",
    "gone",
    "without trace",
    "unsolved",
    "last seen",
    "cold case"
]


todos_posts = []

for url in rss_feeds:
    feed = feedparser.parse(url)

    for entry in feed.entries:
        todos_posts.append(entry)


dados = []

for entry in todos_posts:
    titulo_original = getattr(entry, "title", "")
    titulo = titulo_original.lower()
    resumo_original = limpar_html(getattr(entry, "summary", ""))

    if post_vazio(resumo_original):
        continue

    texto_busca = f"{titulo} {resumo_original.lower()}"

    if not any(p in texto_busca for p in palavras_chave):
        continue

    score, elementos_detectados = score_cinematografico_v2(titulo_original, resumo_original)

    hook = random.choice([
        "A última vez que alguém o viu... tudo parecia normal.",
        "As autoridades nunca conseguiram explicar o que aconteceu naquela noite.",
        "A última imagem registrada ainda causa arrepios.",
        "Ele saiu normalmente... e nunca mais voltou."
    ])

    dados.append({
        "Caso": titulo_original,
        "Resumo Original": resumo_original[:1500],
        "Score": score,
        "Potencial Documental": potencial_documental(score),
        "Relevância para Sem Rastros": relevancia_sem_rastros(score),
        "Classificação": classificacao_caso(score),
        "Atmosfera": ", ".join(elementos_detectados),
        "Hook": hook,
        "Link": getattr(entry, "link", "")
    })


os.makedirs("resultados", exist_ok=True)

if not dados:
    print("⚠️ Nenhum caso válido encontrado nesta execução.")
    print("✅ O script não quebrou. Apenas não houve posts compatíveis com os filtros.")

    df = pd.DataFrame(columns=[
        "Caso",
        "Resumo Original",
        "Score",
        "Potencial Documental",
        "Relevância para Sem Rastros",
        "Classificação",
        "Atmosfera",
        "Hook",
        "Link"
    ])
else:
    df = pd.DataFrame(dados)
    df = df.sort_values(by="Score", ascending=False)

print(df.head(20))

df.to_csv("resultados/casos_cinematicos.csv", index=False)

print("\n✅ RADAR CINEMATOGRÁFICO FINALIZADO")
print("✅ CSV SALVO EM resultados/casos_cinematicos.csv")


pdf = SimpleDocTemplate("resultados/dossie_cinematografico.pdf")
styles = getSampleStyleSheet()
conteudo = []

titulo_pdf = Paragraph(
    "<b>RADAR CINEMATOGRÁFICO DE DESAPARECIMENTOS</b>",
    styles["Title"]
)

conteudo.append(titulo_pdf)
conteudo.append(Spacer(1, 20))

if df.empty:
    texto = """
    <b>Nenhum caso válido encontrado nesta execução.</b><br/>
    O radar rodou corretamente, mas os feeds não retornaram posts compatíveis com os filtros atuais.
    """
    conteudo.append(Paragraph(texto, styles["BodyText"]))
else:
    for index, row in df.head(15).iterrows():
        texto = f"""
        <b>Caso:</b> {row['Caso']}<br/>
        <b>Resumo:</b> {row['Resumo Original']}<br/>
        <b>Score:</b> {row['Score']}<br/>
        <b>Potencial:</b> {row['Potencial Documental']}<br/>
        <b>Relevância Sem Rastros:</b> {row['Relevância para Sem Rastros']}<br/>
        <b>Classificação:</b> {row['Classificação']}<br/>
        <b>Atmosfera:</b> {row['Atmosfera']}<br/>
        <b>Hook:</b> {row['Hook']}<br/>
        <b>Link:</b> {row['Link']}<br/><br/>
        """

        conteudo.append(Paragraph(texto, styles["BodyText"]))
        conteudo.append(Spacer(1, 20))

pdf.build(conteudo)

print("✅ PDF SALVO EM resultados/dossie_cinematografico.pdf")
