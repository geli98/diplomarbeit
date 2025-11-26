"""
GANZ EINFACHES Flugzeug-Lade-Modell für ANFÄNGER
=================================================

Was macht dieses Programm?
- Berechnet wie viele Ladestationen (Plugin oder Swap) wir brauchen
- Findet die günstigste Kombination
- Nutzt Gurobi zur Optimierung
"""

import gurobipy as gp
from gurobipy import GRB
import math


# 1: DATEN FESTLEGEN

# Wie viele Flugzeuge müssen pro Stunde geladen werden?
flugplan = [2, 6, 5, 8, 10, 8]  # 6 Stunden: z.B. 5-11 Uhr
anzahl_stunden = len(flugplan)

###### ALLE ANGABEN
# Plug-in
plugin_kosten = 50000  # € pro Plugin-Station
plugin_abschreibung = 10 # [Jahre]
plugin_kosten_jahr = plugin_kosten/plugin_abschreibung
#plugin_wirkungsgrad = 0.95

#Daten für Ladeverfahren CC-CV - Ladezeit
plugin_spannung_max = 800 #V
plugin_spannung_min = 600 #V
plugin_strom_max = 125 #A
plugin_strom_min = 10 #A
plugin_cc_anteil = 0.80 # 80% CC, 20% CV ---- eig. wird die CV verlängert?

#Swap-Angaben
swap_kosten = 50000   # € pro Swap-Station
swapbat_kosten = 15000
swap_wechsel = 10 #min ---- später genauer
#swap_wirkungsgrad = 0.95

#Batterien
bat_kapazit = 2900 #kWh
bat_spannung_max = 800 # V
bat_strom_max = 125 #A
soc_start = 0.10
soc_ende = 0.95
swapbat_lebenszyklen = 2000
swapbat_abschreibungskosten = swapbat_kosten/swapbat_lebenszyklen

# Ladeeffizienz
ladeeffizienz = 0.93  # 93% Effizienz = 7% Verluste

strompreis_kwh = 0.30  # €/kWh
netz_max_kw = 2000 #kW

#PV-Anlagen
pv_flaeche = 2000 #verfügbare Fläche m^2 
pv_kosten_pro_m2 = 200 #€/m^2
pv_wirkungsgrad = 0.80
globalstrahlung = 1100 # kWh/m²/Jahr
pv_abschreibung = 25 # [Jahren] Lebensdauer der PV-Anlage

#Sonnenstrahlung
globalstrahlung_winter = 40  # kWh/m²/Monat (Dezember - Worst Case)
globalstrahlung_sommer = 200  # kWh/m²/Monat (Juli - Best Case)

# opex: energiekosten

# opex: Personalkosten
#von der Zeitvorgängen abhängig

# Ladezeiten - Annahmen: !! später anhand Ladeverfahren
plugin_zeit = 75  # Minuten
swap_zeit = 8     # Minuten
swaplade_zeit = 75

# Flugzeug-Parameter
fzg_reichweite = 463 # km
fzg_geschw = 489 #km/h

# Wie viele Flugzeuge kann eine Station pro Stunde bedienen?
plugin_kapazitaet = 60 / plugin_zeit  # 60 min / 45 min = 1.33 Flugzeuge/h
swap_kapazitaet = 60 / swap_zeit      # 60 min / 8 min = 7.5 Flugzeuge/h


# 2: MODELL ERSTELLEN 

print(f"Flugplan: {flugplan}")
print()

# Gurobi-Modell erstellen
model = gp.Model("Einfach")

# WICHTIG für die Ausgabe: 0-nur Endergebnis wird gezeigt; 1 - kann man sehen wie Gurobi optimiert
model.setParam('OutputFlag', 0) 


# 3: VARIABLEN 

# Variable 1: Wie viele Plugin-Stationen brauchen wir?
anzahl_plugin = model.addVar(
    vtype=GRB.INTEGER,  # Muss eine Ganzzahl sein
    lb=0,               # Minimum: 0 Stationen
    name="Plugin"
)

# Variable 2: Wie viele Swap-Stationen und Batterien für Batteriwechsel?
anzahl_swap = model.addVar(vtype=GRB.INTEGER,lb=0,name="Swap")
anzahl_swapbat = model.addVar(vtype=GRB.INTEGER,lb=0,name="Batterie Swap")

#Strom vom Netz pro Stunde (falls PV+ESS nicht reicht)
stromnetz = {}
for t in range(anzahl_stunden):
    # wird für jede Std eigene Variable erzeugt
    stromnetz[t] = model.addVar(
        vtype=GRB.CONTINUOUS,
        lb=0,
        name=f"Netz_Strom_kWh_{t}"
        )



#  -----HILFSFUNKTIONEN-----
# Zusatzformeln für die Zielfunktion

plugin_pro_stunde = {}
swap_pro_stunde = {}

for t in range(anzahl_stunden):
    #schaut wie viel ladesäulen werden jede stunden benutzt
    plugin_pro_stunde[t] = model.addVar(
    vtype=GRB.INTEGER,
    lb=0,
    name=f"Plugin_Stunde_{t}"
    )
    swap_pro_stunde[t] = model.addVar(
    vtype=GRB.INTEGER,
    lb=0,
    name=f"Swap_Stunde_{t}")

#cc-cv Ladung
delta_soc = soc_ende - soc_start
energie_zu_laden = bat_kapazit * delta_soc #kWh


# Energie mit Verlusten
energie_benoetigt = energie_zu_laden / ladeeffizienz  #--- oder einzeln für plugin/swap?

# PV-Produktion (SOMMER - Best Case)
pv_monat_pro_m2 = globalstrahlung_sommer * pv_wirkungsgrad  # kWh/m²/Monat
pv_tag_pro_m2 = pv_monat_pro_m2 / 31  # kWh/m²/Tag (31 Tage im Juli)

# Tagesprofil: Prozent der Tagesproduktion pro Stunde (6h: 5-11 Uhr)
sonne_profil = [0.02, 0.05, 0.08, 0.12, 0.15, 0.18]

# Belegung Batterie

bat_belegzeit = (swaplade_zeit*2) + fzg_reichweite/fzg_geschw*60 # [min]

# capex
capex_plugin = plugin_kosten * anzahl_plugin
capex_swap = swap_kosten * anzahl_swap
capex_swapbat = swapbat_kosten * anzahl_swapbat
capex_pv = pv_flaeche * pv_kosten_pro_m2
capex = capex_plugin + capex_swap + capex_swapbat + capex_pv

# opex - Energiekosten
# summiert Stromwerte über allen Stunden
strom_pro_tag = gp.quicksum(stromnetz[t] for t in range(anzahl_stunden))
opex_energie = strom_pro_tag * strompreis_kwh #* 365 * planungsjahre

# opex - Wartung: 10% der Anschaffung × Anzahl Stationen
plugin_wartung = 0.10 * plugin_kosten * anzahl_plugin  # 10% der Anschaffungskosten
swap_wartung = 0.10 * swap_kosten * anzahl_swap

opex_wartung = plugin_wartung + swap_wartung


opex = opex_energie + opex_wartung #+ opex_personal



#  4: ZIELFUNKTION 
# Was wollen wir minimieren? → Die Kosten!
zielfkt = capex + opex

model.setObjective(zielfkt, GRB.MINIMIZE)


# 5: NEBENBEDINGUNGEN 
# Was muss erfüllt sein?
#NB 1 - Bedarf decken + Kapazitäten beachten

for t in range(anzahl_stunden):
    # Alle Flugzeuge müssen geladen werden
    model.addConstr(
        plugin_pro_stunde[t] + swap_pro_stunde[t] >= flugplan[t],
        name=f"Bedarf_{t}"
    )

    # Plugin-Kapazität: Ein Ladegerät kann bspw. 1.33 Flugzeuge/h bedienen
    model.addConstr(
        plugin_pro_stunde[t] <= anzahl_plugin * plugin_kapazitaet,
        name=f"Plugin_Kap_{t}"
    )
    model.addConstr(
        swap_pro_stunde[t] <= anzahl_swap * swap_kapazitaet,
        name=f"Swap_Kap_{t}"
    )

#NB 2 - Verfügbarkeit der Batterien für swap
# Wie lange ist eine Batterie blockiert? (in Stunden, aufgerundet)
bat_belegzeit_stunden = math.ceil(bat_belegzeit / 60)

for t in range(anzahl_stunden):
    # Von welcher Stunde an sind Batterien noch blockiert?
    start = max(0, t - bat_belegzeit_stunden + 1) 

    # Summe aller Swaps der letzten N Stunden (die noch blockiert sind)
    batterien_blockiert = gp.quicksum(
        swap_pro_stunde[i] for i in range(start, t + 1)
    )

    # Genug Batterien müssen vorhanden sein!
    model.addConstr(
        anzahl_swapbat >= batterien_blockiert,
        name=f"Batterien_{t}"
    )

#NB 3 - Energiebilanz (Bedarf <= verfügbare Strom (PV-Strom + Netzstrom))
for t in range(anzahl_stunden):
    # PV-Produktion dieser Stunde
    pv_prod_kwh = pv_flaeche * pv_tag_pro_m2 * sonne_profil[t]

    # Bedarf dieser Stunde (vereinfacht: Anzahl Flugzeuge × Energie pro Flugzeug)
    # Pro Flugzeug: energie_benoetigt kWh
    bedarf_kwh = flugplan[t] * energie_benoetigt

    # Energie-Bilanz: PV + Netzstrom >= Bedarf
    model.addConstr(
        pv_prod_kwh + stromnetz[t] >= bedarf_kwh,
        name=f"Energie_{t}"
    )

#NB 4 - Spannung/Leistung darf nicht Netzstromwerte überschreiten?
#NB 5


# 6: OPTIMIEREN

model.optimize()

# 7: ERGEBNIS

if model.status == GRB.OPTIMAL:
    
    print("Lösung gefunden!")

    # Ergebnisse auslesen
    plugin_anzahl = int(anzahl_plugin.X)
    swap_anzahl = int(anzahl_swap.X)
    batterien_anzahl = int(anzahl_swapbat.X)

    print(f"\nOptimale Lösung:")
    print(f"  Plugin-Stationen: {plugin_anzahl}")
    print(f"  Swap-Stationen:   {swap_anzahl}")
    print(f"  Swap-Batterien:   {batterien_anzahl}")

    print(f"\nGesamtkosten (optimiert): €{model.ObjVal:,.2f}")

    # Batterie-Lebensdauer-Analyse
    swaps_pro_tag = sum(swap_pro_stunde[t].X for t in range(anzahl_stunden))

    if swaps_pro_tag > 0 and batterien_anzahl > 0:
        # Gesamte verfügbare Zyklen aller Batterien
        gesamt_zyklen = batterien_anzahl * swapbat_lebenszyklen

        # Wie viele Tage bis alle verbraucht sind?
        tage_haltbarkeit = gesamt_zyklen / swaps_pro_tag
        jahre_haltbarkeit = tage_haltbarkeit / 365

        print(f"\n--- Batterie-Lebensdauer ---")
        print(f"  Swaps pro Tag: {swaps_pro_tag:.1f}")
        print(f"  Verfügbare Zyklen: {gesamt_zyklen:,}")
        print(f"  Haltbarkeit: {jahre_haltbarkeit:.2f} Jahre")
    elif batterien_anzahl == 0:
        print(f"\n--- Keine Swap-Batterien benötigt ---")

else:
    print("FEHLER: Keine Lösung gefunden!")


# ========== ERWEITERUNGEN FÜR SPÄTER ==========
"""
Modell erweitern mit:
 
1. BATTERIEN hinzufügen: +
   - Neue Variable: anzahl_batterien
   - Neue Kosten: batterie_kosten
   - Neue Constraint: Batterien müssen verfügbar sein

2. PHOTOVOLTAIK hinzufügen: +
   - Variable: pv_flaeche
   - Energie-Bilanz: PV + Netz = Bedarf

3. ZEITABHÄNGIGE VARIABLEN: +
   - plugin_pro_stunde[t] statt nur anzahl_plugin

4. BETRIEBSKOSTEN hinzufügen:
   - Stromkosten
   - Personalkosten
   - Wartungskosten

5. CC-CV LADUNG:
   - Realistische Ladezeiten berechnen
   - Leistung über Zeit modellieren

"""
