import feedparser
import pandas as pd
import random

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
    "without trace"
]

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

todos_posts = []

for url in rss_feeds:

    feed = feedparser.parse(url)

    for entry in feed.entries:

        todos_posts.append(entry)

dados = []

for entry in todos_posts:

    titulo = entry.title.lower()

    if any(p in titulo for p in palavras_chave):

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

        hook = random.choice([

            "A última vez que alguém o viu... tudo parecia normal.",

            "As autoridades nunca conseguiram explicar o que aconteceu naquela noite.",

            "A última imagem registrada ainda causa arrepios.",

            "Ele saiu normalmente... e nunca mais voltou."
        ])

        dados.append({

            "Caso": entry.title,
            "Score": score,
            "Classificação": nivel,
            "Atmosfera": ", ".join(elementos_detectados),
            "Hook": hook,
            "Link": entry.link
        })

df = pd.DataFrame(dados)

df = df.sort_values(by="Score", ascending=False)

print(df.head(20))

df.to_csv("casos_cinematicos.csv", index=False)

print("\n✅ RADAR CINEMATOGRÁFICO FINALIZADO")
import os

# Criar pasta de resultados
os.makedirs("resultados", exist_ok=True)

# Salvar CSV dentro da pasta
df.to_csv("resultados/casos_cinematicos.csv", index=False)

print("\n✅ RESULTADOS SALVOS")
