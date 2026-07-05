# Straffskyttare och fasta situationer per lag i Allsvenskan 2026
# Uppdatera manuellt när det ändras
# Format: lista i prioritetsordning — första spelaren är primär, övriga är alternativ

STRAFF_SKYTTARE = {
    "AIK": {
        "straff": ["Hove", "Csongvai"],
        "hornor": ["Csongvai"],
        "frisparkar": ["Csongvai"],
    },
    "BK Häcken": {
        "straff": ["Lindgren"],
        "hornor": ["Rygaard", "Lindgren"],
        "frisparkar": ["Rygaard", "Lindgren"],
    },
    "IF Brommapojkarna": {
        "straff": ["Berg"],
        "hornor": ["Berg", "Hansen"],
        "frisparkar": ["Hansen"],
    },
    "Degerfors IF": {
        "straff": ["Sundgren"],
        "hornor": ["Netabay"],
        "frisparkar": ["Okänd"],
    },
    "Djurgården": {
        "straff": ["Lien"],
        "hornor": ["Hegland", "Larsson"],
        "frisparkar": ["Hegland"],
    },
    "GAIS": {
        "straff": ["Salter"],
        "hornor": ["Frosti Thorkelsson", "de Brienne"],
        "frisparkar": ["Frosti Thorkelsson"],
    },
    "Halmstads BK": {
        "straff": ["Okänd"],
        "hornor": ["Allansson", "Ascone"],
        "frisparkar": ["Okänd"],
    },
    "Hammarby IF": {
        "straff": ["Besara"],
        "hornor": ["Besara", "Madjed", "Persson"],
        "frisparkar": ["Besara"],
    },
    "IF Elfsborg": {
        "straff": ["Östman"],
        "hornor": ["Magnusson", "Zeneli"],
        "frisparkar": ["Östman"],
    },
    "IFK Göteborg": {
        "straff": ["Heintz"],
        "hornor": ["Heintz"],
        "frisparkar": ["Heintz"],
    },
    "IK Sirius": {
        "straff": ["Ure", "Bjerkebo"],
        "hornor": ["Bjerkebo", "Krusnell", "Jönsson"],
        "frisparkar": ["Bjerkebo"],
    },
    "Kalmar FF": {
        "straff": ["Rosenquist"],
        "hornor": ["Chourak", "Gojani", "Gustafsson", "Hallberg"],
        "frisparkar": ["Rosenquist"],
    },
    "Malmö FF": {
        "straff": ["Botheim"],
        "hornor": ["Rosengren", "Haksabanovic", "Busanello"],
        "frisparkar": ["Haksabanovic"],
    },
    "Mjällby AIF": {
        "straff": ["Bergström"],
        "hornor": ["Stroud", "Malachowski Thorell"],
        "frisparkar": ["Stroud"],
    },
    "Västerås SK": {
        "straff": ["Ladefoged"],
        "hornor": ["Baggesen", "Lushaku"],
        "frisparkar": ["Ladefoged"],
    },
    "Örgryte IS": {
        "straff": ["Sana"],
        "hornor": ["Hofvander", "Sana", "Andreasson"],
        "frisparkar": ["Sana"],
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