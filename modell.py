import gurobipy as gp
from gurobipy import GRB
import math


# 1: Konstanten

### Zeitrahmen ###
SLOT_DAUER = 5  # Minuten pro Slot
BETRIEBSSTUNDEN = 16  # 06:00-22:00 (Flugbetrieb)
GESAMT_STUNDEN = 30   # 06:00-12:00 nächster Tag (für Batterieladung)

ANZAHL_SLOTS_BETRIEB = BETRIEBSSTUNDEN * 12  # 192 Slots
ANZAHL_SLOTS_GESAMT = GESAMT_STUNDEN * 12    # 360 Slots

# Betriebstage pro Jahr (für Umrechnung)
BETRIEBSTAGE = 365

# Zinssatz und CRF-Funktion (Capital Recovery Factor)
ZINSSATZ = 0.06  # 6% Zinsen
NUTZUNGSDAUER = 20  # Jahre (für alle Komponenten)

# Gewichtung für Multi-Objective (Sensitivitätsanalyse)
# w = 0.0: Nur Airline-Kosten minimieren
# w = 0.5: Beide gleich gewichten (Standard)
# w = 1.0: Nur Flughafen-Kosten minimieren
GEWICHT_FLUGHAFEN = 0.5

def crf(zinssatz, jahre):
    """Annuitätenfaktor: verteilt Investition auf jährliche Zahlungen mit Verzinsung"""
    r = zinssatz
    y = jahre
    return (r * (1 + r)**y) / ((1 + r)**y - 1)

# Plug-in
PLUGIN_PORTS = 3
PLUGIN_KOSTEN_PRO_PORT = 120000
PLUGIN_KOSTEN = PLUGIN_KOSTEN_PRO_PORT * PLUGIN_PORTS  # 360.000 EUR
PLUGIN_KOSTEN_TAG = PLUGIN_KOSTEN * crf(ZINSSATZ, NUTZUNGSDAUER) / BETRIEBSTAGE

# Daten für CC-CV Ladezeit
PLUGIN_SPANNUNG_MAX = 1000  # V
PLUGIN_STROM_GESAMT = 350 * PLUGIN_PORTS  # 1050A

# Swap-Angaben
SWAP_KOSTEN = 180000
SWAP_KOSTEN_TAG = SWAP_KOSTEN * crf(ZINSSATZ, NUTZUNGSDAUER) / BETRIEBSTAGE
SWAPBAT_KOSTEN = 295000
SWAP_WECHSEL = 10  # min
SWAP_STROM_MAX = 500  # A

# Halle für Swap (300 m² × 925 €/m²)
HALLE_FLAECHE = 300  # m²
HALLE_PREIS_M2 = 925  # €/m² (Durchschnitt 800-1050)
HALLE_KOSTEN = HALLE_FLAECHE * HALLE_PREIS_M2  # 277.500 EUR
HALLE_KOSTEN_TAG = HALLE_KOSTEN * crf(ZINSSATZ, NUTZUNGSDAUER) / BETRIEBSTAGE

# Batterien
BAT_KAPAZIT = 2950  # kWh (nominal)
BAT_SPANNUNG_MAX = 1000  # V
SOC_START = 0.10
SOC_ENDE = 0.95
SOC_CC_ENDE = 0.80
SWAPBAT_LEBENSZYKLEN = 2000
SWAPBAT_ABSCHREIBUNGSKOSTEN = SWAPBAT_KOSTEN / SWAPBAT_LEBENSZYKLEN

# Ladeeffizienz
LADEEFFIZIENZ = 0.93

# Strompreis (gleich für Tag und Nacht)
STROMPREIS = 0.30  # EUR/kWh

# Turnaround
TURNAROUND_SWAP = 25  # min

# Flugzeug-Parameter
FZG_GESCHW = 489      # km/h (Reisegeschwindigkeit)
FZG_MASSE = 26000     # kg (MTOW)
GLEITZAHL = 16.35     # L/D (Lift-to-Drag Ratio)
ETA_TOTAL = 0.70      # Gesamtwirkungsgrad (Antrieb)
E_STERN = 360         # Wh/kg (spezifische Energiedichte Batterie)
G = 9.81              # m/s² (Erdbeschleunigung)

# Airline-Kosten
DELAY_KOSTEN = 20  # EUR pro Minute Wartezeit
MTOW = 26000
MTOW_EINHEITEN = math.ceil(MTOW / 1000)
ABSTELLENTGELT_24H = 3.30
ABSTELLKOSTEN_PRO_FZG = MTOW_EINHEITEN * ABSTELLENTGELT_24H

# Personalkosten
PERSONAL_PLUGIN = 15
PERSONAL_SWAP = 50

# Kapazitätsgrenzen
MAX_LADESTATIONEN = 15  # Originale Grenze
MAX_BATTERIEN = 100
MAX_WARTEZEIT_MIN = 1000

# Netzanschluss-Limit (Leistung)
NETZ_MAX_KW = 3500  # Test: 3,5 MW
PLUGIN_LEISTUNG_KW = 1050  # kW pro Plugin (3 x 350 kW)
SWAP_LEISTUNG_KW = 500     # kW pro Swap-Batterieladung

# PV-Anlage (Deutschland-Durchschnitt: 22 m²/kWp)
PV_FLAECHE_GESAMT = 295899  # m² (verfügbare Gesamtfläche)
PV_M2_PRO_KWP = 22  # m²/kWp (Deutschland-Durchschnitt, inkl. Abstände, Wege, etc.)
PV_LEISTUNG_KWP = PV_FLAECHE_GESAMT / PV_M2_PRO_KWP  # 13.450 kWp
PV_PR = 0.86  # PR = Performance Ratio

# Stündliche Einstrahlung [J/cm²] - Sommer, beginnend bei 4:00 Uhr
# Index 0 = 4:00-5:00, Index 1 = 5:00-6:00, etc.
STRAHLUNG_SOMMER_J = [17, 63, 121, 173, 210, 262, 297, 319, 315, 296, 266, 216, 174, 99, 53, 8, 0, 0]
# Umrechnung J/cm² → kWh/m²: dividiere durch 360
STRAHLUNG_SOMMER_KWH = [s / 360 for s in STRAHLUNG_SOMMER_J]  # kWh/m²

# PV-Kosten
PV_KOSTEN_PRO_KW = 522  # EUR/kWp
PV_WARTUNG_PRO_KW = 7.16  # EUR/kWp pro Jahr (fixed O&M)
PV_KOSTEN = PV_LEISTUNG_KWP * PV_KOSTEN_PRO_KW  # 7.020.900 EUR
PV_WARTUNG_JAHR = PV_LEISTUNG_KWP * PV_WARTUNG_PRO_KW  # 96.303 EUR/Jahr
PV_ABSCHREIBUNG = 25  # Jahre
PV_KOSTEN_TAG = (PV_KOSTEN / PV_ABSCHREIBUNG + PV_WARTUNG_JAHR) / BETRIEBSTAGE

# Energiespeicher (fix)
SPEICHER_KAPAZITAET = 5000  # kWh
SPEICHER_EFFIZIENZ = 0.90  # 90% Effizienz
SPEICHER_KOSTEN_PRO_KWH = 87.82  # EUR/kWh
SPEICHER_WARTUNG_PRO_KWH = 4.39  # EUR/kWh pro Jahr
SPEICHER_KOSTEN = SPEICHER_KAPAZITAET * SPEICHER_KOSTEN_PRO_KWH  # 439.100 EUR
SPEICHER_WARTUNG_JAHR = SPEICHER_KAPAZITAET * SPEICHER_WARTUNG_PRO_KWH  # 21.950 EUR/Jahr
SPEICHER_ABSCHREIBUNG = 10  # Jahre
SPEICHER_KOSTEN_TAG = (SPEICHER_KOSTEN / SPEICHER_ABSCHREIBUNG + SPEICHER_WARTUNG_JAHR) / BETRIEBSTAGE

# Slot-Startzeiten (Minute ab 06:00)
slot_startzeit = {}
for t in range(ANZAHL_SLOTS_GESAMT):
    slot_startzeit[t] = t * SLOT_DAUER

# Nachtladung: Swap-Batterien werden erst ab 20:00 geladen
# 20:00 = 14 Stunden nach 06:00 = Slot 168
NACHT_LADESTART_SLOT = 14 * 12  # Slot 168 = 20:00 Uhr

# Speicher-Startwert: PV-Ertrag von 4:00-6:00 (vorberechnet)
# STRAHLUNG_SOMMER_KWH[0] = 4:00-5:00, [1] = 5:00-6:00
PV_VORLAUF_KWH = (STRAHLUNG_SOMMER_KWH[0] + STRAHLUNG_SOMMER_KWH[1]) * PV_LEISTUNG_KWP * PV_PR
SPEICHER_START = PV_VORLAUF_KWH * SPEICHER_EFFIZIENZ  # Nach Effizienz-Verlust

# Flugplan mit 20 Flugzeugen (Test 3,5 MW)
flugplan = [
    1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0,  # 06:00-07:00: 3 Flugzeuge
    1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0,  # 07:00-08:00: 3 Flugzeuge
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,  # 08:00-09:00: 0
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,  # 09:00-10:00: 0
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,  # 10:00-11:00: 0
    1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0,  # 11:00-12:00: 2 Flugzeuge
    0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0,  # 12:00-13:00: 1 Flugzeug
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,  # 13:00-14:00: 0
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,  # 14:00-15:00: 0
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,  # 15:00-16:00: 0
    1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0,  # 16:00-17:00: 2 Flugzeuge
    1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0,  # 17:00-18:00: 3 Flugzeuge
    1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0,  # 18:00-19:00: 3 Flugzeuge
    1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0,  # 19:00-20:00: 3 Flugzeuge
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,  # 20:00-21:00: 0
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,  # 21:00-22:00: 0
]  # Summe: 20 Flugzeuge 

def flugzeuge_aus_flugplan(flugplan):
    flugzeuge = []
    flugzeug_id = 0
    for slot in range(len(flugplan)):
        for _ in range(flugplan[slot]):
            flugzeuge.append({"id": flugzeug_id, "ankunft": slot})
            flugzeug_id += 1
    return flugzeuge

flugzeuge = flugzeuge_aus_flugplan(flugplan)
anzahl_flugzeuge = len(flugzeuge)

# Ladezeit-Berechnung
def berechne_ladezeit_cc_cv(kapazitaet_kwh, spannung_v, strom_a, soc_start, soc_ende):
    delta_soc = soc_ende - soc_start
    energie_zu_laden = kapazitaet_kwh * delta_soc / LADEEFFIZIENZ
    leistung_kw = spannung_v * strom_a / 1000
    FAKTOR_C = 1.3
    t_gesamt_std = energie_zu_laden / leistung_kw * FAKTOR_C
    return t_gesamt_std * 60  # Minuten

plugin_ladezeit = berechne_ladezeit_cc_cv(BAT_KAPAZIT, PLUGIN_SPANNUNG_MAX, PLUGIN_STROM_GESAMT, SOC_START, SOC_ENDE) + 2
swap_ladezeit = berechne_ladezeit_cc_cv(BAT_KAPAZIT, BAT_SPANNUNG_MAX, SWAP_STROM_MAX, SOC_START, SOC_ENDE)

# Flugzeit-Berechnung mit physikalischen Formeln:
# 1. P_battery = (m * g * v) / (L/D * eta)  [Watt]
# 2. E_nutzbar = Kapazität * (SOC_Ende - SOC_Start)  [kWh]
# 3. t = E_nutzbar / P_battery  [Stunden]

v_ms = FZG_GESCHW * 1000 / 3600  # km/h -> m/s
P_battery = (FZG_MASSE * G * v_ms) / (GLEITZAHL * ETA_TOTAL)  # Watt

# Nur 85% der Batteriekapazität nutzbar (SOC 10% -> 95%)
delta_soc_flug = SOC_ENDE - SOC_START  # 0.85
E_nutzbar = BAT_KAPAZIT * delta_soc_flug  # kWh
m_battery = BAT_KAPAZIT * 1000 / E_STERN  # kg (Gesamtmasse der Batterie)
FLUGZEIT = math.ceil(E_nutzbar / (P_battery / 1000) * 60)  # kWh / kW = h -> min (aufgerundet)

# Reichweite ergibt sich aus Flugzeit * Geschwindigkeit
FZG_REICHWEITE = FLUGZEIT / 60 * FZG_GESCHW  # km

# Batterie-Blockzeit (vollständiger Zyklus):
# 1. Swap Heimat (raus)      = SWAP_WECHSEL
# 2. Flug zum Ziel           = FLUGZEIT
# 3. Swap Ziel (zur Station) = SWAP_WECHSEL
# 4. Laden am Ziel           = swap_ladezeit
# 5. Swap Ziel (ins Flugzeug)= SWAP_WECHSEL
# 6. Rückflug                = FLUGZEIT
# 7. Swap Heimat (zur Station)= SWAP_WECHSEL
# 8. Laden Heimat            = swap_ladezeit
bat_blockzeit = 4 * SWAP_WECHSEL + 2 * FLUGZEIT + 2 * swap_ladezeit

# Energie pro Ladung
delta_soc = SOC_ENDE - SOC_START
energie_benoetigt = BAT_KAPAZIT * delta_soc / LADEEFFIZIENZ

print("=" * 50)
print("MODELL MIT 30-STUNDEN-ZEITRAHMEN")
print("=" * 50)
print(f"Flugzeuge: {anzahl_flugzeuge}")
print(f"\nFlugzeit-Berechnung (physikalisch):")
print(f"  P_battery = (m*g*v) / (L/D * eta)")
print(f"            = ({FZG_MASSE} kg * {G} m/s² * {v_ms:.1f} m/s) / ({GLEITZAHL} * {ETA_TOTAL})")
print(f"            = {P_battery/1000:.0f} kW")
print(f"  E_nutzbar = {BAT_KAPAZIT} kWh * {delta_soc_flug:.0%} = {E_nutzbar:.0f} kWh")
print(f"  m_battery = {BAT_KAPAZIT} kWh / {E_STERN} Wh/kg = {m_battery:.0f} kg")
print(f"  Flugzeit  = {E_nutzbar:.0f} kWh / {P_battery/1000:.0f} kW = {FLUGZEIT} min (aufgerundet)")
print(f"  Reichweite= {FZG_REICHWEITE:.0f} km")
print(f"\nLadezeiten:")
print(f"  Plugin-Ladezeit: {plugin_ladezeit:.0f} min, Leistung: {PLUGIN_LEISTUNG_KW} kW")
print(f"  Swap-Batterieladezeit: {swap_ladezeit:.0f} min, Leistung: {SWAP_LEISTUNG_KW} kW")
print(f"  Batterie-Blockzeit: {bat_blockzeit:.0f} min")
print(f"Netzanschluss max: {NETZ_MAX_KW} kW")
print()

# 2: Modell erstellen
model = gp.Model("Kostenoptimierung_30h")
model.setParam('OutputFlag', 0)

# 3: Entscheidungsvariablen

# Infrastruktur
anzahl_plugin = model.addVar(vtype=GRB.INTEGER, lb=0, name="Anzahl_Plugin")
anzahl_swap = model.addVar(vtype=GRB.INTEGER, lb=0, name="Anzahl_Swap")
anzahl_bat = model.addVar(vtype=GRB.INTEGER, lb=0, name="Anzahl_Batterien")
nutzt_swap = model.addVar(vtype=GRB.BINARY, name="Nutzt_Swap")

# Pro Slot (nur Betriebsstunden für Flugzeuge)
plugin_start = {}
swap_start = {}
for t in range(ANZAHL_SLOTS_BETRIEB):
    plugin_start[t] = model.addVar(vtype=GRB.INTEGER, lb=0, name=f"Plugin_Start_{t}")
    swap_start[t] = model.addVar(vtype=GRB.INTEGER, lb=0, name=f"Swap_Start_{t}")

# Hinweis: Batterieladung startet ab 20:00 Uhr (Nachtladung)
# Alle Swaps des Tages werden gesammelt und nachts geladen.

# Pro Flugzeug
ist_plugin = {}
ist_swap = {}
start_slot = {}
wartezeit = {}
braucht_abstell = {}

for f in range(anzahl_flugzeuge):
    ist_plugin[f] = model.addVar(vtype=GRB.BINARY, name=f"Plugin_Flugzeug_{f}")
    ist_swap[f] = model.addVar(vtype=GRB.BINARY, name=f"Swap_Flugzeug_{f}")
    ankunft = flugzeuge[f]["ankunft"]
    start_slot[f] = model.addVar(vtype=GRB.INTEGER, lb=ankunft, ub=ANZAHL_SLOTS_BETRIEB-1, name=f"Start_Slot_{f}")
    wartezeit[f] = model.addVar(vtype=GRB.INTEGER, lb=0, name=f"Wartezeit_{f}")
    braucht_abstell[f] = model.addVar(vtype=GRB.BINARY, name=f"Braucht_Abstell_{f}")

# Hilfsvariable: startet_in_slot[f, t]
startet_in_slot = {}
for f in range(anzahl_flugzeuge):
    for t in range(ANZAHL_SLOTS_BETRIEB):
        startet_in_slot[f, t] = model.addVar(vtype=GRB.BINARY, name=f"Startet_{f}_{t}")

# Hilfsfunktion
def belegte_stationen(aktueller_slot, ladezeit_minuten, max_slot=None):
    if max_slot is None:
        max_slot = aktueller_slot
    aktuelle_zeit = slot_startzeit[aktueller_slot]
    belegte = []
    for i in range(min(aktueller_slot + 1, max_slot + 1)):
        start_zeit_i = slot_startzeit[i]
        ende_zeit_i = start_zeit_i + ladezeit_minuten
        if ende_zeit_i > aktuelle_zeit:
            belegte.append(i)
    return belegte

# PV-Leistung pro Stunde: E = kWp × Einstrahlung × PR
def pv_leistung_stunde(stunde):
    # stunde 0 = 6:00, stunde 16 = 22:00, etc.
    # Umrechnung auf Uhrzeit (0-23)
    if stunde < 16:  # 06:00-22:00
        uhrzeit = 6 + stunde
    elif stunde < 24:  # 22:00-06:00 (Nacht)
        uhrzeit = 22 + (stunde - 16)
        if uhrzeit >= 24:
            uhrzeit -= 24
    else:  # 06:00-12:00 nächster Tag
        uhrzeit = 6 + (stunde - 24)

    # Einstrahlung aus echten Daten [kWh/m²]
    # STRAHLUNG_SOMMER_KWH: Index 0 = 4:00, Index 1 = 5:00, etc.
    strahlung_index = uhrzeit - 4  # Uhrzeit 6 -> Index 2
    if 0 <= strahlung_index < len(STRAHLUNG_SOMMER_KWH):
        einstrahlung = STRAHLUNG_SOMMER_KWH[strahlung_index]
    else:
        einstrahlung = 0  # Nacht

    return PV_LEISTUNG_KWP * einstrahlung * PV_PR

# Speicher-Variablen (pro Stunde, für 30h ab 6:00)
stromnetz = {}
speicher_stand = {}
speicher_ein = {}
speicher_aus = {}
speicher_ladet = {}  # Binär: 1 = lädt (PV > Bedarf), 0 = entlädt

for h in range(GESAMT_STUNDEN):
    stromnetz[h] = model.addVar(vtype=GRB.CONTINUOUS, lb=0, name=f"Netz_{h}")
    speicher_stand[h] = model.addVar(vtype=GRB.CONTINUOUS, lb=0, ub=SPEICHER_KAPAZITAET, name=f"Speicher_Stand_{h}")
    speicher_ein[h] = model.addVar(vtype=GRB.CONTINUOUS, lb=0, name=f"Speicher_Ein_{h}")
    speicher_aus[h] = model.addVar(vtype=GRB.CONTINUOUS, lb=0, name=f"Speicher_Aus_{h}")
    speicher_ladet[h] = model.addVar(vtype=GRB.BINARY, name=f"Speicher_Ladet_{h}")

# 4: Zielfunktion (alle Kosten PRO TAG)

# CAPEX pro Tag (inkl. PV und Speicher als Fixkosten)
capex_plugin = PLUGIN_KOSTEN_TAG * anzahl_plugin
capex_swap = SWAP_KOSTEN_TAG * anzahl_swap
capex_halle = HALLE_KOSTEN_TAG * nutzt_swap
capex_pv = PV_KOSTEN_TAG  # Fix
capex_speicher = SPEICHER_KOSTEN_TAG  # Fix
capex_bat = 0.01 * anzahl_bat  # Tiebreaker

capex_gesamt = capex_plugin + capex_swap + capex_halle + capex_pv + capex_speicher + capex_bat

# OPEX Wartung pro Tag (Flughafen)
opex_wartung = 0.10 * (PLUGIN_KOSTEN_TAG * anzahl_plugin + SWAP_KOSTEN_TAG * anzahl_swap)

# Netzstromkosten (tatsächlicher Verbrauch)
# PV-Strom ist gratis (CAPEX oben), nur Netzstrom kostet
kosten_netzstrom = STROMPREIS * gp.quicksum(stromnetz[h] for h in range(GESAMT_STUNDEN))

# Bonus für Speicherung: Anreiz, PV-Überschuss zu speichern statt abzuregeln
# Kleiner Wert (0.001 EUR/kWh) = 1 EUR pro 1000 kWh gespeichert
bonus_speichern = 0.001 * gp.quicksum(speicher_ein[h] for h in range(GESAMT_STUNDEN))

# Flughafen-Kosten pro Tag (CAPEX + Wartung + Netzstrom - Speicher-Bonus)
kosten_flughafen = capex_gesamt + opex_wartung + kosten_netzstrom - bonus_speichern

# Ladevorgänge zählen
plugin_vorgaenge = gp.quicksum(plugin_start[t] for t in range(ANZAHL_SLOTS_BETRIEB))
swap_vorgaenge = gp.quicksum(swap_start[t] for t in range(ANZAHL_SLOTS_BETRIEB))

# Airline-Kosten pro Tag
kosten_delay = DELAY_KOSTEN * SLOT_DAUER * gp.quicksum(wartezeit[f] for f in range(anzahl_flugzeuge))
kosten_abstell = ABSTELLKOSTEN_PRO_FZG * gp.quicksum(braucht_abstell[f] for f in range(anzahl_flugzeuge))
kosten_batterie = SWAPBAT_ABSCHREIBUNGSKOSTEN * swap_vorgaenge
kosten_personal = PERSONAL_PLUGIN * plugin_vorgaenge + PERSONAL_SWAP * swap_vorgaenge  # Handling-Gebühr

# Energiekosten: Jetzt beim Flughafen (tatsächlicher Netzstrom), nicht mehr pauschal bei Airline
# Die pauschale Berechnung (STROMPREIS * energie_benoetigt * alle_ladevorgaenge) ist entfernt,
# weil sie für alle Lademethoden gleich war und die Entscheidung nicht beeinflusst hat.

kosten_airline = kosten_delay + kosten_abstell + kosten_batterie + kosten_personal

# Gesamtkosten pro Tag (gewichtete Summe)
# Zielfunktion: w * Flughafen + (1-w) * Airline
zielfunktion = GEWICHT_FLUGHAFEN * kosten_flughafen + (1 - GEWICHT_FLUGHAFEN) * kosten_airline
model.setObjective(zielfunktion, GRB.MINIMIZE)

# 5: Nebenbedingungen

# NB 1: Entweder Plugin ODER Swap
for f in range(anzahl_flugzeuge):
    model.addConstr(ist_plugin[f] + ist_swap[f] == 1, name=f"NB1_Entweder_{f}")

# NB 2: Slot-Verbindung
for f in range(anzahl_flugzeuge):
    model.addConstr(gp.quicksum(startet_in_slot[f, t] for t in range(ANZAHL_SLOTS_BETRIEB)) == 1, name=f"NB2a_EinSlot_{f}")
    model.addConstr(start_slot[f] == gp.quicksum(t * startet_in_slot[f, t] for t in range(ANZAHL_SLOTS_BETRIEB)), name=f"NB2b_StartSlot_{f}")

for t in range(ANZAHL_SLOTS_BETRIEB):
    model.addConstr(
        plugin_start[t] == gp.quicksum(ist_plugin[f] * startet_in_slot[f, t] for f in range(anzahl_flugzeuge)),
        name=f"NB2c_Plugin_{t}")
    model.addConstr(
        swap_start[t] == gp.quicksum(ist_swap[f] * startet_in_slot[f, t] for f in range(anzahl_flugzeuge)),
        name=f"NB2d_Swap_{t}")

# NB 3: Kapazitätsgrenzen
model.addConstr(anzahl_plugin + anzahl_swap <= MAX_LADESTATIONEN, name="NB3a_Max_Stationen")
model.addConstr(anzahl_bat <= MAX_BATTERIEN, name="NB3b_Max_Batterien")
model.addConstr(anzahl_swap <= MAX_LADESTATIONEN * nutzt_swap, name="NB3c_Halle")

for f in range(anzahl_flugzeuge):
    model.addConstr(anzahl_swap >= ist_swap[f], name=f"NB3d_Swap_noetig_{f}")

# NB 4: Plugin-Station Kapazität
for t in range(ANZAHL_SLOTS_BETRIEB):
    belegte_plugin_slots = belegte_stationen(t, plugin_ladezeit, ANZAHL_SLOTS_BETRIEB - 1)
    plugin_belegt = gp.quicksum(plugin_start[i] for i in belegte_plugin_slots)
    model.addConstr(plugin_belegt <= anzahl_plugin, name=f"NB4_Plugin_{t}")

# NB 5: Swap-Station Kapazität
# NEU: Batterieladung startet erst ab NACHT_LADESTART_SLOT (20:00)
# Alle Swaps des Tages werden gesammelt und ab 20:00 nacheinander geladen

swap_ladezeit_slots = math.ceil(swap_ladezeit / SLOT_DAUER)

for check_slot in range(ANZAHL_SLOTS_GESAMT):
    # Welche Swaps belegen in diesem Slot eine Station?
    # Ladestart ist max(swap_slot, NACHT_LADESTART_SLOT)
    # Station belegt wenn: ladestart <= check_slot < ladestart + swap_ladezeit_slots
    belegte_swaps = []
    for t in range(ANZAHL_SLOTS_BETRIEB):
        ladestart = max(t, NACHT_LADESTART_SLOT)
        ladeende = ladestart + swap_ladezeit_slots
        if ladestart <= check_slot < ladeende:
            belegte_swaps.append(t)

    if belegte_swaps:
        station_belegt = gp.quicksum(swap_start[i] for i in belegte_swaps)
        model.addConstr(station_belegt <= anzahl_swap, name=f"NB5_SwapKap_{check_slot}")

# NB 6: Batterie-Verfügbarkeit (auf 30h erweitert)
# Prüfe für jeden Slot im 30h-Fenster, wie viele Batterien blockiert sind
# Eine Batterie ist blockiert von Swap-Start bis Swap-Start + bat_blockzeit
bat_blockzeit_slots = math.ceil(bat_blockzeit / SLOT_DAUER)

for check_slot in range(ANZAHL_SLOTS_GESAMT):
    # Welche Swaps blockieren in diesem Slot eine Batterie?
    # Ein Swap aus Slot t blockiert wenn: t <= check_slot < t + bat_blockzeit_slots
    belegte_swaps = []
    for t in range(ANZAHL_SLOTS_BETRIEB):
        # Prüfe ob Swap aus Slot t noch aktiv ist
        if t <= check_slot < t + bat_blockzeit_slots:
            belegte_swaps.append(t)

    if belegte_swaps:  # Nur wenn es relevante Slots gibt
        bat_blockiert = gp.quicksum(swap_start[i] for i in belegte_swaps)
        model.addConstr(anzahl_bat >= bat_blockiert, name=f"NB6_Bat_{check_slot}")

# NB 7: Netzanschluss-Leistungslimit
# Gleichzeitige Leistung darf NETZ_MAX_KW nicht überschreiten
# Plugin: PLUGIN_LEISTUNG_KW (1050 kW) während gesamter Ladezeit
# Swap-Batterie: SWAP_LEISTUNG_KW (500 kW) - Ladung startet erst ab 20:00

for check_slot in range(ANZAHL_SLOTS_GESAMT):
    # Plugin-Leistung: Aktive Plugin-Ladungen × 1050 kW
    aktive_plugin_slots = belegte_stationen(check_slot, plugin_ladezeit, ANZAHL_SLOTS_BETRIEB - 1)
    plugin_leistung = PLUGIN_LEISTUNG_KW * gp.quicksum(plugin_start[i] for i in aktive_plugin_slots)

    # Swap-Batterie-Leistung: Ladung startet ab NACHT_LADESTART_SLOT
    aktive_swap_slots = []
    for t in range(ANZAHL_SLOTS_BETRIEB):
        ladestart = max(t, NACHT_LADESTART_SLOT)
        ladeende = ladestart + swap_ladezeit_slots
        if ladestart <= check_slot < ladeende:
            aktive_swap_slots.append(t)

    swap_leistung = SWAP_LEISTUNG_KW * gp.quicksum(swap_start[i] for i in aktive_swap_slots) if aktive_swap_slots else 0

    # Gesamtleistung <= Netzlimit
    model.addConstr(plugin_leistung + swap_leistung <= NETZ_MAX_KW, name=f"NB7_Leistung_{check_slot}")

# NB 8: Flugzeug-Nebenbedingungen
for f in range(anzahl_flugzeuge):
    ankunft = flugzeuge[f]["ankunft"]

    # Wartezeit
    model.addConstr(wartezeit[f] == start_slot[f] - ankunft, name=f"NB8a_Wartezeit_{f}")

    # Max Wartezeit
    max_wartezeit_slots = MAX_WARTEZEIT_MIN // SLOT_DAUER
    model.addConstr(wartezeit[f] <= max_wartezeit_slots, name=f"NB8b_MaxWarte_{f}")

    # Abstellgebühr
    bodenzeit_min = wartezeit[f] * SLOT_DAUER + ist_plugin[f] * plugin_ladezeit + ist_swap[f] * TURNAROUND_SWAP
    M_bod = 500
    model.addConstr(bodenzeit_min >= 60 - M_bod * (1 - braucht_abstell[f]), name=f"NB8c_Abstell1_{f}")
    model.addConstr(bodenzeit_min <= 59 + M_bod * braucht_abstell[f], name=f"NB8c_Abstell2_{f}")

    # Betriebsende
    plugin_slots = math.ceil(plugin_ladezeit / SLOT_DAUER)
    swap_turnaround_slots = math.ceil(TURNAROUND_SWAP / SLOT_DAUER)
    M = ANZAHL_SLOTS_BETRIEB
    model.addConstr(start_slot[f] + plugin_slots <= ANZAHL_SLOTS_BETRIEB + M * (1 - ist_plugin[f]), name=f"NB8d_Ende_Plugin_{f}")
    model.addConstr(start_slot[f] + swap_turnaround_slots <= ANZAHL_SLOTS_BETRIEB + M * (1 - ist_swap[f]), name=f"NB8d_Ende_Swap_{f}")

# NB 9: Energiebilanz (pro Stunde)
# PV + Netz + Speicher_aus >= Bedarf + Speicher_ein

# Ladebedarf pro Stunde berechnen
plugin_ladezeit_slots = math.ceil(plugin_ladezeit / SLOT_DAUER)
swap_ladezeit_slots = math.ceil(swap_ladezeit / SLOT_DAUER)

for h in range(GESAMT_STUNDEN):
    # Mittlerer Slot dieser Stunde
    mitte_slot = h * 12 + 6

    # Aktive Plugin-Ladungen
    aktive_plugin = []
    for t in range(ANZAHL_SLOTS_BETRIEB):
        start = t
        ende = t + plugin_ladezeit_slots
        if start <= mitte_slot < ende:
            aktive_plugin.append(t)

    # Aktive Swap-Batterieladungen (ab 20:00 Uhr)
    aktive_swap = []
    for t in range(ANZAHL_SLOTS_BETRIEB):
        ladestart = max(t, NACHT_LADESTART_SLOT)
        ende = ladestart + swap_ladezeit_slots
        if ladestart <= mitte_slot < ende:
            aktive_swap.append(t)

    # Leistungsbedarf in dieser Stunde (kW -> kWh, da 1 Stunde)
    bedarf_plugin = PLUGIN_LEISTUNG_KW * gp.quicksum(plugin_start[t] for t in aktive_plugin) if aktive_plugin else 0
    bedarf_swap = SWAP_LEISTUNG_KW * gp.quicksum(swap_start[t] for t in aktive_swap) if aktive_swap else 0
    bedarf_gesamt = bedarf_plugin + bedarf_swap

    # PV-Erzeugung in dieser Stunde
    pv_erzeugung = pv_leistung_stunde(h)

    # Energiebilanz: PV + Netz + Speicher_aus >= Bedarf + Speicher_ein
    model.addConstr(
        pv_erzeugung + stromnetz[h] + speicher_aus[h] >= bedarf_gesamt + speicher_ein[h],
        name=f"NB9a_Energiebilanz_{h}"
    )

    # Speicher kann nur laden ODER entladen (nicht beides gleichzeitig)
    M_sp = 100000
    model.addConstr(speicher_ein[h] <= M_sp * speicher_ladet[h], name=f"NB9c_Nur_Laden_{h}")
    model.addConstr(speicher_aus[h] <= M_sp * (1 - speicher_ladet[h]), name=f"NB9c_Nur_Entladen_{h}")

    # Priorität: Wenn Bedarf > PV, dann MUSS Speicher entladen werden (nicht laden)
    model.addConstr(
        bedarf_gesamt - pv_erzeugung <= M_sp * (1 - speicher_ladet[h]),
        name=f"NB9d_Entladen_Wenn_Bedarf_{h}"
    )

    # Wenn entladen wird (speicher_ladet=0), dann Speicher komplett nutzen
    if h > 0:
        model.addConstr(
            speicher_aus[h] >= speicher_stand[h-1] - M_sp * speicher_ladet[h],
            name=f"NB9e_Komplett_Entladen_{h}"
        )

    # Speicherstand-Entwicklung
    if h == 0:
        # Startzustand: Speicher mit PV-Vorlauf von 4:00-6:00 vorgeladen
        model.addConstr(
            speicher_stand[h] == SPEICHER_START + speicher_ein[h] * SPEICHER_EFFIZIENZ - speicher_aus[h],
            name=f"NB9b_Speicher_Start"
        )
    else:
        model.addConstr(
            speicher_stand[h] == speicher_stand[h-1] + speicher_ein[h] * SPEICHER_EFFIZIENZ - speicher_aus[h],
            name=f"NB9b_Speicher_{h}"
        )

# 6: Optimierung
print("Starte Optimierung...")
model.optimize()


# 7: Ergebnis

def ergebnis_ausgeben():
    """Gibt alle Optimierungsergebnisse aus."""

    # Ergebnisse auslesen
    n_plugin = int(anzahl_plugin.X)
    n_swap = int(anzahl_swap.X)
    n_bat = int(anzahl_bat.X)
    n_plugin_total = sum(plugin_start[t].X for t in range(ANZAHL_SLOTS))
    n_swap_total = sum(swap_start[t].X for t in range(ANZAHL_SLOTS))

    # Delay-Kosten berechnen
    total_wartezeit_slots = sum(wartezeit[f].X for f in range(anzahl_flugzeuge))
    total_wartezeit_min = total_wartezeit_slots * SLOT_DAUER
    total_delay_kosten = total_wartezeit_min * DELAY_KOSTEN

    # Speicher-Nutzung berechnen
    speicher_ein_total = sum(speicher_ein[h].X for h in range(BETRIEBSSTUNDEN))
    speicher_aus_total = sum(speicher_aus[h].X for h in range(BETRIEBSSTUNDEN))
    speicher_end = speicher_stand[9].X

    print("Loesung gefunden!")
    print("\nErgebnis:")
    print(f"Plugin: {n_plugin} ; Swap: {n_swap} ; Batterien: {n_bat}")
    print(f"Speicher: {SPEICHER_KAPAZITAET:.0f} kWh ; Start: 0 kWh ; Ende: {speicher_end:.0f} kWh")
    print(f"Ladevorgaenge: {n_plugin_total:.0f} Plugin, {n_swap_total:.0f} Swap")
    print(f"Netzstrom: {strom_pro_tag.getValue():.1f} kWh ; Speicher Ein: {speicher_ein_total:.1f} kWh ; Speicher Aus: {speicher_aus_total:.1f} kWh")
    print(f"Wartezeit: {total_wartezeit_min:.0f} min -> Delay-Kosten: {total_delay_kosten:.0f} EUR")
    print(f"\nGesamtkosten (optimiert): {model.ObjVal:,.2f} EUR")

    # Energiebilanz pro Stunde
    print("\nEnergiebilanz pro Stunde:")
    print(f"  {'Stunde':<12} {'PV':>8} {'Bedarf':>8} {'Netz':>8} {'Sp.Ein':>8} {'Sp.Aus':>8} {'Sp.Stand':>8}")
    for h in range(BETRIEBSSTUNDEN):
        pv_h = PV_FLAECHE * strahlung_stunde[h] * umrechnung_pv * PV_WIRKUNGSGRAD
        slot_start_h = h * 12
        slot_ende_h = (h + 1) * 12
        bedarf_h = sum(
            startet_in_slot[f, t].X * energie_benoetigt
            for f in range(anzahl_flugzeuge)
            for t in range(slot_start_h, slot_ende_h)
        )
        netz_h = stromnetz[h].X
        ein_h = speicher_ein[h].X
        aus_h = speicher_aus[h].X
        stand_h = speicher_stand[h].X
        uhrzeit = f"{6+h}:00-{7+h}:00"
        print(f"  {uhrzeit:<12} {pv_h:>8.0f} {bedarf_h:>8.0f} {netz_h:>8.0f} {ein_h:>8.0f} {aus_h:>8.0f} {stand_h:>8.0f}")

    # Details pro Flugzeug
    print("\nDetails pro Flugzeug:")
    for f in range(anzahl_flugzeuge):
        ankunft = flugzeuge[f]["ankunft"]
        start = int(start_slot[f].X)
        warte = int(wartezeit[f].X)
        typ = "Plugin" if ist_plugin[f].X > 0.5 else "Swap"
        print(f"  Flugzeug {f}: Ankunft Slot {ankunft}, Start Slot {start}, Wartezeit {warte} Slots ({warte*SLOT_DAUER} min), {typ}")


# Ergebnis ausgeben
if model.status == GRB.OPTIMAL:
    ergebnis_ausgeben()
else:
    print("Keine Loesung gefunden!")

