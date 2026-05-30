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


def resumo_inutil(resumo):
    resumo = str(resumo).lower().strip()

    if not resumo:
        return True

    termos_lixo = [
        "submitted by",
        "[link]",
        "[comments]"
    ]

    return all(termo in resumo for termo in termos_lixo)


def calcular_score_profissional(titulo, resumo):
    texto = f"{titulo} {resumo}".lower()

    score_total = 0
    elementos = []

    categorias = {
        "Mistério Central": {
            "missing": 18,
            "disappearance": 18,
            "disappeared": 18,
            "vanished": 22,
            "without trace": 25,
            "unsolved": 18,
            "cold case": 20,
            "never found": 22,
            "still missing": 22
        },
        "Tempo Sem Solução": {
            "1970": 18,
            "1980": 18,
            "1990": 15,
            "2000": 12,
            "50 years": 20,
            "40 years": 20,
            "30 years": 18,
            "20 years": 15,
            "10 years": 12,
            "decades": 20,
            "years later": 12
        },
        "Ambiente Cinematográfico": {
            "forest": 12,
            "woods": 12,
            "national park": 18,
            "park": 8,
            "mountain": 12,
            "highway": 10,
            "road": 8,
            "airport": 12,
            "hotel": 8,
            "motel": 8,
            "night": 10,
            "snow": 10,
            "island": 12,
            "canal": 10,
            "train": 10
        },
        "Prova Visual ou Último Registro": {
            "cctv": 18,
            "camera": 12,
            "surveillance": 18,
            "last seen": 20,
            "last image": 18,
            "footage": 15,
            "photo": 10
        },
        "Complexidade Investigativa": {
            "murder": 12,
            "identified": 8,
            "unidentified": 15,
            "jane doe": 18,
            "john doe": 18,
            "arrest": 8,
            "police": 8,
            "investigation": 12,
            "theory": 8,
            "theories": 10,
            "false trails": 15,
            "missing files": 15,
            "no trace": 20,
            "foul play": 10
        },
        "Impacto Humano": {
            "child": 15,
            "teen": 12,
            "teenager": 12,
            "15 year old": 15,
            "family": 8,
            "mother": 10,
            "father": 10,
            "daughter": 10,
            "woman": 6,
            "man": 5
        }
    }

    limites_categoria = {
        "Mistério Central": 30,
        "Tempo Sem Solução": 20,
        "Ambiente Cinematográfico": 18,
        "Prova Visual ou Último Registro": 22,
        "Complexidade Investigativa": 25,
        "Impacto Humano": 15
    }

    for categoria, regras in categorias.items():
        score_categoria = 0

        for termo, pontos in regras.items():
            if termo in texto:
                score_categoria += pontos
                elementos.append(f"{termo} ({categoria})")

        score_total += min(score_categoria, limites_categoria[categoria])

    return min(score_total, 100), elementos


def potencial_documental(score):
    if score >= 85:
        return "Muito Alto"
    elif score >= 65:
        return "Alto"
    elif score >= 40:
        return "Médio"
    return "Baixo"


def relevancia_sem_rastros(score):
    if score >= 85:
        return "ALTÍSSIMA"
    elif score >= 65:
        return "ALTA"
    elif score >= 40:
        return "MÉDIA"
    return "BAIXA"


def classificacao_caso(score):
    if score >= 85:
        return "🔥 CASO NETFLIX"
    elif score >= 65:
        return "⚠️ MUITO FORTE"
    elif score >= 40:
        return "🟡 OBSERVAR"
    return "⚪ BAIXO"


def motivo_editorial(score, elementos):
    texto = " ".join(elementos).lower()

    motivos = []

    if "mistério central" in texto:
        motivos.append("possui desaparecimento ou mistério central claro")

    if "tempo sem solução" in texto:
        motivos.append("tem peso histórico ou longa duração sem resposta")

    if "prova visual" in texto or "último registro" in texto:
        motivos.append("apresenta elemento forte de último registro, imagem, câmera ou CCTV")

    if "ambiente cinematográfico" in texto:
        motivos.append("tem cenário visual com potencial cinematográfico")

    if "complexidade investigativa" in texto:
        motivos.append("envolve investigação, identidade desconhecida, suspeitas ou linhas narrativas complexas")

    if "impacto humano" in texto:
        motivos.append("carrega impacto humano relevante para conexão emocional com o espectador")

    if motivos:
        return "Caso relevante porque " + "; ".join(motivos[:4]) + "."

    if score >= 40:
        return "Caso com algum potencial editorial, mas exige apuração complementar antes de virar roteiro."

    return "Caso fraco para produção principal no momento."


def gerar_hook(titulo, elementos):
    texto = f"{titulo} {' '.join(elementos)}".lower()

    if "cctv" in texto or "camera" in texto or "surveillance" in texto or "footage" in texto:
        return "A última imagem registrada parecia comum... até virar a peça mais perturbadora do caso."

    if "jane doe" in texto or "john doe" in texto or "unidentified" in texto:
        return "Por anos, ninguém sabia quem era a vítima. Mas os detalhes encontrados levantaram perguntas ainda maiores."

    if "vanished" in texto or "without trace" in texto or "no trace" in texto:
        return "A pessoa desapareceu sem deixar rastro — e cada pista parecia abrir uma nova pergunta."

    if "cold case" in texto or "decades" in texto or "years later" in texto:
        return "Décadas se passaram, mas uma pergunta continuou incomodando investigadores e familiares."

    return random.choice([
        "O caso parecia simples, até os detalhes começarem a não fazer sentido.",
        "A última vez que alguém o viu... tudo parecia normal.",
        "As autoridades tinham pistas, mas nenhuma resposta definitiva.",
        "O desaparecimento começou como uma ocorrência comum — e virou um mistério inquietante."
    ])


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
    titulo = getattr(entry, "title", "")
    resumo_original = limpar_html(getattr(entry, "summary", ""))
    link = getattr(entry, "link", "")

    if not titulo:
        continue

    score, elementos_detectados = calcular_score_profissional(titulo, resumo_original)

    # Aqui está a correção principal:
    # resumo ruim não elimina automaticamente caso com título forte.
    if resumo_inutil(resumo_original) and score < 40:
        continue

    if score < 35:
        continue

    if not resumo_original or resumo_inutil(resumo_original):
        resumo_original = "Resumo não disponível no RSS. Caso selecionado pelo potencial do título; abrir o link para apuração completa antes da produção."

    hook = gerar_hook(titulo, elementos_detectados)

    dados.append({
        "Caso": titulo,
        "Resumo Original": resumo_original[:1500],
        "Score": score,
        "Potencial Documental": potencial_documental(score),
        "Relevância para Sem Rastros": relevancia_sem_rastros(score),
        "Classificação": classificacao_caso(score),
        "Elementos Detectados": ", ".join(elementos_detectados),
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
    "Elementos Detectados",
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

df.to_csv("resultados/casos_cinematicos.csv", index=False)

print("\n✅ RADAR CINEMATOGRÁFICO PROFISSIONAL FINALIZADO")
print("✅ CSV SALVO EM resultados/casos_cinematicos.csv")


pdf = SimpleDocTemplate("resultados/dossie_cinematografico.pdf")
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
    O radar rodou corretamente, mas os feeds não retornaram casos com pontuação mínima.
    """
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
        <b>Elementos Detectados:</b> {row['Elementos Detectados']}<br/>
        <b>Motivo Editorial:</b> {row['Motivo Editorial']}<br/>
        <b>Hook:</b> {row['Hook']}<br/>
        <b>Link:</b> {row['Link']}<br/><br/>
        """

        conteudo.append(Paragraph(texto, styles["BodyText"]))
        conteudo.append(Spacer(1, 20))

pdf.build(conteudo)

print("✅ PDF SALVO EM resultados/dossie_cinematografico.pdf")
