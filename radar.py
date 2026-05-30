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
    texto = texto.replace("&lt;", "<")
    texto = texto.replace("&gt;", ">")
    return texto.strip()


def texto_inutil(resumo):
    resumo = str(resumo).lower().strip()

    if not resumo:
        return True

    termos_lixo = ["submitted by", "[link]", "[comments]"]

    return all(termo in resumo for termo in termos_lixo)


def score_cinematografico_v2(titulo, resumo):
    texto = f"{titulo} {resumo}".lower()
    score = 0
    elementos = []

    regras = {
        "missing": 20,
        "disappearance": 20,
        "disappeared": 20,
        "vanished": 25,
        "without trace": 30,
        "unsolved": 25,
        "cold case": 25,
        "last seen": 25,
        "never found": 25,
        "still missing": 25,
        "cctv": 20,
        "camera": 15,
        "surveillance": 20,
        "forest": 15,
        "woods": 15,
        "park": 15,
        "national park": 25,
        "mountain": 15,
        "highway": 15,
        "road": 10,
        "night": 10,
        "phone call": 15,
        "strange": 15,
        "disturbing": 15,
        "creepy": 15,
        "mysterious": 15,
        "theory": 10,
        "theories": 15,
        "child": 25,
        "teen": 15,
        "teenager": 15,
        "girl": 10,
        "boy": 10,
        "woman": 10,
        "man": 10,
        "family": 10,
        "police": 10,
        "investigation": 15,
        "case": 10
    }

    for termo, pontos in regras.items():
        if termo in texto:
            score += pontos
            elementos.append(termo)

    return min(score, 100), elementos


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
        return "Caso com forte potencial documental, atmosfera de mistério e elementos narrativos relevantes para vídeo longo."
    elif score >= 60:
        return "Caso promissor para investigação, com bons elementos para construção de roteiro."
    elif score >= 35:
        return "Caso deve ser observado. Pode render pauta se houver fontes complementares."
    return "Caso fraco no momento, exige mais apuração antes de virar roteiro."


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


dados = []

for entry in todos_posts:
    titulo_original = getattr(entry, "title", "")
    resumo_original = limpar_html(getattr(entry, "summary", ""))
    link = getattr(entry, "link", "")

    if not titulo_original:
        continue

    score, elementos_detectados = score_cinematografico_v2(titulo_original, resumo_original)

    # Não descarta automaticamente resumo ruim se o título for forte
    if texto_inutil(resumo_original) and score < 35:
        continue

    # Só descarta se realmente não tiver nenhum sinal editorial
    if score < 20:
        continue

    if not resumo_original or texto_inutil(resumo_original):
        resumo_original = "Resumo não disponível no RSS. Avaliar o caso pelo título e abrir o link para apuração completa."

    hook = random.choice([
        "A última vez que alguém o viu... tudo parecia normal.",
        "As autoridades nunca conseguiram explicar o que aconteceu naquela noite.",
        "A última imagem registrada ainda causa arrepios.",
        "Ele saiu normalmente... e nunca mais voltou.",
        "O caso parecia simples, até os detalhes começarem a não fazer sentido."
    ])

    dados.append({
        "Caso": titulo_original,
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


os.makedirs("resultados", exist_ok=True)

colunas = [
    "Caso",
    "Resumo Original",
    "Score",
    "Potencial Documental",
    "Relevância para Sem Rastros",
    "Classificação",
    "Atmosfera",
    "Motivo Editorial",
    "Hook",
    "Link"
]

if not dados:
    df = pd.DataFrame(columns=colunas)
    print("⚠️ Nenhum caso encontrado. O radar rodou, mas os feeds não trouxeram material suficiente.")
else:
    df = pd.DataFrame(dados, columns=colunas)
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
    O radar rodou corretamente, mas os feeds não retornaram casos com pontuação mínima.
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
        <b>Motivo Editorial:</b> {row['Motivo Editorial']}<br/>
        <b>Hook:</b> {row['Hook']}<br/>
        <b>Link:</b> {row['Link']}<br/><br/>
        """

        conteudo.append(Paragraph(texto, styles["BodyText"]))
        conteudo.append(Spacer(1, 20))

pdf.build(conteudo)

print("✅ PDF SALVO EM resultados/dossie_cinematografico.pdf")
