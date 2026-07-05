import httpx
import json
import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, "scripts")
from straff_data import STRAFF_SKYTTARE

load_dotenv()
API_KEY = os.getenv("ANTHROPIC_API_KEY")

def fraga_claude(prompt, max_tokens=3000):
    svar = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}]
        },
        timeout=120
    )
    data = svar.json()
    if "error" in data:
        print(f"API-fel: {data['error']}")
        raise Exception(data["error"])
    if "content" not in data:
        print(f"Oväntat svar från API: {data}")
        raise Exception("Inget content i svaret")
    return "\n".join(
        block["text"] for block in data["content"]
        if block["type"] == "text"
    )

# Beräkna blankomgångar per lag
def hitta_blanks():
    try:
        with open("fdr_data.json", encoding="utf-8") as f:
            fdr = json.load(f)
        alla_gw = set()
        for lag, matcher in fdr.items():
            for m in matcher:
                alla_gw.add(m["gw"])
        min_gw = min(alla_gw)
        max_gw = max(alla_gw)
        blanks = {}
        for lag, matcher in fdr.items():
            lag_gw = set(m["gw"] for m in matcher)
            lag_blanks = [gw for gw in range(min_gw, max_gw + 1) if gw not in lag_gw]
            if lag_blanks:
                blanks[lag] = lag_blanks
        return blanks
    except:
        return {}

BLANKS = hitta_blanks()

# Ladda data
with open("dashboard_data.json", encoding="utf-8") as f:
    spelare = json.load(f)

with open("fdr_data.json", encoding="utf-8") as f:
    fdr = json.load(f)

# Hitta aktuell och nästa omgång
bootstrap = httpx.get("https://fantasy.allsvenskan.se/api/bootstrap-static/").json()
aktuell_gw = next(e["id"] for e in bootstrap["events"] if e.get("is_current"))
nasta_gw = aktuell_gw + 1

print(f"Analyserar omgång {nasta_gw}...")
if BLANKS:
    print("Blankomgångar:")
    for lag, gw_lista in BLANKS.items():
        print(f"  {lag}: GW {gw_lista}")

# Filtrera tillgängliga spelare
# Inkludera landslagsuttagna med hög spelchans
tillgangliga = [
    s for s in spelare
    if (s["status"] in ("a", "d") or (s["status"] == "n" and s["chans"] >= 75))
    and s["chans"] >= 75
    and s["minuter"] > 90
]

# Antal spelade matcher per spelare (för sample-size)
def antal_matcher(s):
    return len(s.get("historik", []))

def spelare_sammanfattning(s, max_fdr=3):
    fdr_lista = s.get("fdr", [])[:max_fdr]
    fdr_text = ", ".join(
        f"GW{m['gw']}:{m['fdr']}({'H' if m['hemma'] else 'B'})"
        for m in fdr_lista
    )
    fullnamn = s.get("fullnamn") or s["namn"]
    efternamn = s["namn"]

    # Fasta situationer
    lag_info = STRAFF_SKYTTARE.get(s["lag"], {})
    fasta = []
    if efternamn in lag_info.get("straff", []):
        pos = lag_info["straff"].index(efternamn)
        fasta.append("Straffskyttare" if pos == 0 else "Reservstraffskyttare")
    if efternamn in lag_info.get("hornor", []):
        pos = lag_info["hornor"].index(efternamn)
        fasta.append("Hörnor (primär)" if pos == 0 else "Hörnor (reserv)")
    if efternamn in lag_info.get("frisparkar", []):
        pos = lag_info["frisparkar"].index(efternamn)
        if pos == 0:
            fasta.append("Frisparkar (primär)")
    fasta_text = f" | Fasta: {', '.join(fasta)}" if fasta else ""

    # Blankomgångar
    lag_blanks = BLANKS.get(s["lag"], [])
    blank_text = f" | ⚠ BLANK GW{lag_blanks}" if lag_blanks else ""

    # Sample-size
    n_matcher = antal_matcher(s)
    sample_text = f" | Underlag: {n_matcher} matcher"

    return (
        f"{fullnamn} ({s['lag']}, {s['position']}, {s['pris']}M) | "
        f"Poäng/match:{s['ppg']} Form:{s['form3']} "
        f"xG:{s.get('xg') or '-'} xA:{s.get('xa') or '-'} "
        f"Äg:{s['agarskap']}%{fasta_text}{blank_text}{sample_text} FDR: {fdr_text}"
    )

# Blank-sammanfattning
blank_sammanfattning = "\n".join(
    f"  {lag}: spelar INTE GW {gw_lista}"
    for lag, gw_lista in BLANKS.items()
) if BLANKS else "  Inga blankomgångar hittade"

# Stacking-analys — identifiera om rekommendationer är från samma lag
def kolla_stacking(spelare_lista):
    lag_count = {}
    for s in spelare_lista:
        lag_count[s["lag"]] = lag_count.get(s["lag"], 0) + 1
    return {lag: count for lag, count in lag_count.items() if count > 1}

# === KAPTENSTIPS ===
print("Genererar kaptenstips...")

anfallare_mf = [s for s in tillgangliga if s["position"] in ("Anfallare", "Mittfältare")]
anfallare_mf.sort(key=lambda x: float(x["ppg"]), reverse=True)
topp_kapten = anfallare_mf[:20]

kapten_prompt = f"""Du är en kvantitativ analytiker för Allsvenskan Fantasy inför omgång {nasta_gw}.
Ditt uppdrag är att ge präcisa kaptensrekommendationer med explicit osäkerhet och motargument.

KONFIDENSNIVÅER — använd konsekvent:
- Stark rekommendation: bekräftad roll, stort dataunderlag (8+ matcher), samstämmiga signaler
- Rimlig rekommendation: god data men någon osäkerhetsfaktor (minutrisk, oklar form)
- Spekulativ/Bevaka: litet underlag, hög varians eller motstridiga signaler

KAPTENSKLASSIFICERING:
- Säkert kap: hög "golv" — säker start, säker payoff, låg varians
- Risk-kap: hög uppsida men osäker leverans
- Differential-kap: lågt ägarskap, kan ge stort övertag om det slår in

BLANKOMGÅNGAR — 0 poäng dessa omgångar:
{blank_sammanfattning}
⚠ Rekommendera ALDRIG kapten från blankande lag den omgången!

Spelare att analysera (topp 20 på poäng/match, med antal spelade matcher som underlag):
{chr(10).join(spelare_sammanfattning(s) for s in topp_kapten)}

Ge dina topp 3 kaptensrekommendationer på svenska. För varje spelare:
1. Klassificera som Säkert kap / Risk-kap / Differential-kap
2. Ange konfidensnivå (Stark/Rimlig/Spekulativ)
3. Ge motivering (max 2 meningar) — inkludera fasta situationer om relevanta
4. Ange ETT konkret motargument — vad skulle göra detta till ett dåligt val?
5. Nämn om spelaren är del av ett "stacking"-mönster (flera från samma lag)

Format:
1. [Namn] — [Klassificering] | Konfidens: [nivå]
   Motivering: [text]
   Motargument: [text]

2. [Namn] — [Klassificering] | Konfidens: [nivå]
   Motivering: [text]
   Motargument: [text]

3. [Namn] — [Klassificering] | Konfidens: [nivå]
   Motivering: [text]
   Motargument: [text]"""

kaptenstips = fraga_claude(kapten_prompt)
print("\n=== KAPTENSTIPS ===")
print(kaptenstips)

# === DIFFERENTIALS ===
print("\nGenererar differentials...")

differentials = [
    s for s in tillgangliga
    if float(s["agarskap"]) < 15
    and s.get("xg")
    and float(s.get("xg") or 0) > 1.5
]
differentials.sort(key=lambda x: float(x.get("xg") or 0), reverse=True)

# Kolla ägarskaps-trend (approximation via transfers)
def agarskaps_trend(s):
    netto = s["trans_in"] - s["trans_ut"]
    if netto > 100:
        return "↑ Stigande (köps aktivt)"
    elif netto < -100:
        return "↓ Sjunkande (säljs aktivt)"
    else:
        return "→ Stabil"

# Kolla stacking bland differentials
diff_stacking = kolla_stacking(differentials[:10])

diff_prompt = f"""Du är en kvantitativ analytiker för Allsvenskan Fantasy inför omgång {nasta_gw}.
Hitta de bästa differentials — spelare som kan ge ett avgörande övertag mot motståndare.

KONFIDENSNIVÅER:
- Stark rekommendation: tydlig statistisk fördel, stort underlag, bra fixtures
- Rimlig rekommendation: god potential men någon osäkerhetsfaktor
- Spekulativ/Bevaka: litet underlag eller hög varians — nämns för bevakning

ÄGARSKAPS-TREND är viktigt:
- En spelare med 8% ägarskap som stiger snabbt "closar" snart — agera nu
- En spelare med 8% som legat stilla hela säsongen är annorlunda

KORRELATIONSRISK — dessa lag har flera differentials i listan:
{chr(10).join(f"  ⚠ {lag}: {count} differentials — korrelerade, slår mot alla om laget underpresterar" for lag, count in diff_stacking.items()) if diff_stacking else "  Ingen uppenbar korrelationsrisk"}

BLANKOMGÅNGAR:
{blank_sammanfattning}

Kandidater (med ägarskaps-trend och underlagets storlek):
{chr(10).join(spelare_sammanfattning(s) + f" | Trend: {agarskaps_trend(s)}" for s in differentials[:15])}

Ge dina topp 3 differentials på svenska. För varje spelare:
1. Ange konfidensnivå (Stark/Rimlig/Spekulativ)
2. Ange ägarskaps-trend och om spelaren bör köpas nu eller bevakas
3. Ge motivering (max 2 meningar)
4. Ange ETT konkret motargument
5. Klassificera: "Köp nu" / "Bevaka" / "Spekulativt kort"

Format:
1. [Namn] ([Äg%], trend: [↑/↓/→]) | Konfidens: [nivå] | [Köp nu/Bevaka/Spekulativt]
   Motivering: [text]
   Motargument: [text]"""

diff_tips = fraga_claude(diff_prompt)
print("\n=== DIFFERENTIALS ===")
print(diff_tips)

# === PRISRÖRELSER ===
print("\nAnalyserar prisrörelser...")

TOTAL_MANAGERS = 57383
pris_kandidater = []
for s in spelare:
    if s["status"] not in ("a", "d"):
        continue
    netto = s["trans_in"] - s["trans_ut"]
    agare = float(s["agarskap"]) / 100 * TOTAL_MANAGERS
    if agare > 0:
        kvot = netto / agare * 100
        pris_kandidater.append({
            "namn":     s["namn"],
            "lag":      s["lag"],
            "position": s["position"],
            "pris":     s["pris"],
            "agarskap": s["agarskap"],
            "netto":    netto,
            "kvot":     round(kvot, 1),
            "prisand":  s["prisand"],
            "status":   s["status"],
        })

stigande  = sorted([p for p in pris_kandidater if p["kvot"] > 3],  key=lambda x: -x["kvot"])[:8]
sjunkande = sorted([p for p in pris_kandidater if p["kvot"] < -4], key=lambda x:  x["kvot"])[:8]

pris_prompt = f"""Du är en kvantitativ analytiker för Allsvenskan Fantasy — prisrörelsespecialist.

Totalt {TOTAL_MANAGERS} managers spelar.
Prisstegrings-tröskel: ~3-5% nettoinflöde av ägarskapsbasen
Prissänknings-tröskel: ~-4-5% nettoutflöde av ägarskapsbasen

TRÖSKELKÄNSLIGHET — viktigt att kommunicera:
- En spelare på 8% kvot är långt över tröskeln (nästan säker stegring)
- En spelare på 3.5% kvot är precis på tröskeln (känslig för daglig volym)
- Ange hur nära/långt från tröskeln varje spelare är

FALSK SIGNAL-VARNING:
- Nettotransfers direkt efter en enskild stormatsch kan vara en övergångsreaktion
- Flagga om en spelares inflöde verkar vara en "spike" snarare än en stabil trend
- En stabil trend över 3+ dagar är mer tillförlitlig än en dagssiffra

BLANKOMGÅNGAR — spelare från blankande lag kan sjunka:
{blank_sammanfattning}

SPELARE SOM KAN STIGA I PRIS:
{chr(10).join(f"{p['namn']} ({p['lag']}, {p['pris']}M, äg:{p['agarskap']}%) | Netto: +{p['netto']} ({p['kvot']}% av ägarbas)" for p in stigande)}

SPELARE SOM KAN SJUNKA I PRIS:
{chr(10).join(f"{p['namn']} ({p['lag']}, {p['pris']}M, äg:{p['agarskap']}%) | Netto: {p['netto']} ({p['kvot']}% av ägarbas)" for p in sjunkande)}

Ge en strukturerad prisanalys på svenska:

## Köp INNAN prisstegring (max 3 spelare)
För varje spelare: namnge, ange hur långt över tröskeln, om det är stabil trend eller spike, och en mening motivering.

## Sälj INNAN prissänkning (max 3 spelare)
För varje spelare: namnge, ange hur långt under tröskeln, och en mening motivering.

## Varningar
Finns det falska signaler eller spelare nära tröskeln som kräver bevakning?"""

pris_tips = fraga_claude(pris_prompt)
print("\n=== PRISRÖRELSER ===")
print(pris_tips)

# === TRANSFERANALYS ===
print("\nGenererar transferanalys...")

salj_kandidater = [
    s for s in tillgangliga
    if float(s["agarskap"]) > 10
    and float(s["form3"]) < 4
    and s.get("fdr") and s["fdr"][0]["fdr"] >= 4
]
salj_kandidater.sort(key=lambda x: float(x["form3"]))

kop_kandidater = [
    s for s in tillgangliga
    if float(s["form3"]) > 5
    and s.get("fdr") and s["fdr"][0]["fdr"] <= 3
]
kop_kandidater.sort(key=lambda x: float(x["form3"]), reverse=True)

print(f"  Säljkandidater: {len(salj_kandidater)}")
print(f"  Köpkandidater: {len(kop_kandidater)}")

transfer_prompt = f"""Du är en kvantitativ analytiker för Allsvenskan Fantasy och transferstrategi inför omgång {nasta_gw}.

Tänk i ett 5-omgångsperspektiv. En transfer ska ge mätbart nettoövertag — inte bara "kännas rätt".

VIKTIGA PRINCIPER:
- Räkna alltid in blankomgångar i 5-omgångsperspektivet (en blank = -1 match av 5)
- Straffskyttare och fasta situationer ökar värdet markant
- Timing-rekommendation: gör bytet nu, eller vänta en omgång?
- Alternativkostnad: varför valdes inte näst bästa köp-alternativet?

BLANKOMGÅNGAR:
{blank_sammanfattning}

SPELARE ATT ÖVERVÄGA SÄLJA:
{chr(10).join(spelare_sammanfattning(s, max_fdr=5) for s in salj_kandidater[:8]) if salj_kandidater else "Inga uppenbara säljkandidater."}

SPELARE ATT ÖVERVÄGA KÖPA:
{chr(10).join(spelare_sammanfattning(s, max_fdr=5) for s in kop_kandidater[:8]) if kop_kandidater else "Inga uppenbara köpkandidater."}

Ge dina topp 3 transferrekommendationer på svenska. För varje transfer:
1. SÄLJ [Namn] → KÖP [Namn]
2. Nettoövertag: beräkna förväntad poängskillnad över 5 omgångar (ta hänsyn till blankar)
3. Timing: gör bytet nu eller vänta? Motivera.
4. Alternativkostnad: vad var näst bästa KÖP-alternativet och varför valdes det bort?
5. Motargument: vad skulle göra detta till ett dåligt byte?
6. Konfidens: Stark/Rimlig/Spekulativ

Format:
## Transfer 1: SÄLJ [Namn] → KÖP [Namn] | Konfidens: [nivå]
**Nettoövertag:** [beräkning]
**Timing:** [nu/vänta + motivering]
**Alternativkostnad:** [näst bästa alternativ och varför det valdes bort]
**Motargument:** [text]"""

transfer_tips = fraga_claude(transfer_prompt, max_tokens=4000)
print("\n=== TRANSFERANALYS ===")
print(transfer_tips)

# Spara alla insikter
insikter = {
    "omgang":         nasta_gw,
    "kaptenstips":    kaptenstips,
    "differentials":  diff_tips,
    "prisrorelser":   pris_tips,
    "transferanalys": transfer_tips,
}

with open("ai_insikter.json", "w", encoding="utf-8") as f:
    json.dump(insikter, f, ensure_ascii=False, indent=2)

print(f"\nKlart! Sparade insikter till ai_insikter.json")