# Straffskyttare och fasta situationer per lag i Allsvenskan 2026
# Uppdatera manuellt när det ändras
# Format: lista i prioritetsordning — första spelaren är primär, övriga är alternativ

STRAFF_SKYTTARE = {
    "AIK": {
        "straff": ["Hove"],
        "hornor": ["Csongvai", "Bergquist"],
        "frisparkar": ["Csongvai"],
    },
    "BK Häcken": {
        "straff": ["Layouni"],
        "hornor": ["Rygaard", "Lindberg"],
        "frisparkar": ["Rygaard", "Lindberg"],
    },
    "IF Brommapojkarna": {
        "straff": ["Berg"],
        "hornor": ["Berg", "Hansen"],
        "frisparkar": ["Berg"],
    },
    "Degerfors IF": {
        "straff": ["Sundgren"],
        "hornor": ["Netabay"],
        "frisparkar": ["Netabay"],
    },
    "Djurgården": {
        "straff": ["Lien"],
        "hornor": ["Hegland", "Larsson"],
        "frisparkar": ["Hegland"],
    },
    "GAIS": {
        "straff": ["Fagerjord", "Salter"],
        "hornor": ["Frosti Thorkelsson", "de Brienne"],
        "frisparkar": ["Frosti Thorkelsson"],
    },
    "Halmstads BK": {
        "straff": ["Okänd"],
        "hornor": ["Allansson", "Ascone"],
        "frisparkar": ["Ascone"],
    },
    "Hammarby IF": {
        "straff": ["Besara", "Abraham"],
        "hornor": ["Besara", "Madjed", "Persson"],
        "frisparkar": ["Besara"],
    },
    "IF Elfsborg": {
        "straff": ["Zeneli", "Ihler"],
        "hornor": ["Magnusson", "Zeneli"],
        "frisparkar": ["Zeneli", "Magnusson"],
    },
    "IFK Göteborg": {
        "straff": ["Heintz"],
        "hornor": ["Heintz"],
        "frisparkar": ["Heintz"],
    },
    "IK Sirius": {
        "straff": ["Bjerkebo", "Ure"],
        "hornor": ["Bjerkebo", "Krusnell", "Jönsson"],
        "frisparkar": ["Bjerkebo", "Krusnell"],
    },
    "Kalmar FF": {
        "straff": ["Rosenquist"],
        "hornor": ["Chourak", "Gojani", "Gustafsson", "Hallberg"],
        "frisparkar": ["Hallberg", "Rosenquist"],
    },
    "Malmö FF": {
        "straff": ["Botheim"],
        "hornor": ["Rosengren", "Haksabanovic", "Busanello"],
        "frisparkar": ["Haksabanovic", "Busanello"],
    },
    "Mjällby AIF": {
        "straff": ["Bergström"],
        "hornor": ["Stroud", "Malachowski Thorell"],
        "frisparkar": ["Malachowski Thorell", "Stroud"],
    },
    "Västerås SK": {
        "straff": ["Ladefoged"],
        "hornor": ["Baggesen", "Lushaku"],
        "frisparkar": ["Lushaku", "Ring"],
    },
    "Örgryte IS": {
        "straff": ["Sana"],
        "hornor": ["Hofvander", "Sana", "Andreasson"],
        "frisparkar": ["Hofvander", "Sana"],
    },
}

def formatera_situationer(lag):
    """Returnerar en läsbar sträng med fasta situationer för ett lag."""
    if lag not in STRAFF_SKYTTARE:
        return ""
    info = STRAFF_SKYTTARE[lag]
    delar = []
    if info["straff"] and info["straff"][0] != "Okänd":
        skyttare = " / ".join(info["straff"])
        delar.append(f"Straff: {skyttare}")
    if info["hornor"] and info["hornor"][0] != "Okänd":
        hornor = " / ".join(info["hornor"])
        delar.append(f"Hörnor: {hornor}")
    if info["frisparkar"] and info["frisparkar"][0] != "Okänd":
        frisparkar = " / ".join(info["frisparkar"])
        if frisparkar != " / ".join(info["hornor"]):
            delar.append(f"Frisparkar: {frisparkar}")
    return " | ".join(delar) if delar else ""

if __name__ == "__main__":
    print("Straffskyttare och fasta situationer Allsvenskan 2026:")
    print(f"{'Lag':<22} {'Straff':<20} {'Hörnor':<20} {'Frisparkar'}")
    print("-" * 80)
    for lag, info in sorted(STRAFF_SKYTTARE.items()):
        straff    = " / ".join(info["straff"])
        hornor    = " / ".join(info["hornor"])
        frisparkar = " / ".join(info["frisparkar"])
        print(f"{lag:<22} {straff:<20} {hornor:<20} {frisparkar}")