
import gurobipy as gp
from gurobipy import GRB
import math


# 1: DATEN FESTLEGEN

### Slots
slot_dauer = 5  # Jeder Slot ist 5 Minuten lang
anzahl_slots = 120  # 10 Stunden = 600 min / 5 min = 120 Slots


slot_startzeit = {}
for t in range(anzahl_slots):
    slot_startzeit[t] = t * slot_dauer # bsp. slot_startzeit[2] = 2*5 = 10 (bspw. 06:10)

# Wie viele Flugzeuge müssen pro Stunde geladen werden?
# Als Bsp. 10 Stunden
flugplan = [1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 0, 0,  # Stunde 1 (6:00-7:00): 5 Flugzeuge
            1, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0,  # Stunde 2 (7:00-8:00): 3 Flugzeuge
            1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0,  # Stunde 3 (8:00-9:00): 2 Flugzeuge
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,  # Stunde 4 (9:00-10:00): 0 Flugzeuge
            1, 0, 1, 0, 1, 0, 1, 0, 0, 0, 0, 0,  # Stunde 5 (10:00-11:00): 4 Flugzeuge
            1, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0,  # Stunde 6 (11:00-12:00): 3 Flugzeuge
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,  # Stunde 7 (12:00-13:00): 0 Flugzeuge
            1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0,  # Stunde 8 (13:00-14:00): 2 Flugzeuge
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,  # Stunde 9 (14:00-15:00): 0 Flugzeuge
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]  # Stunde 10 (15:00-16:00): 0 Flugzeuge

# Jedes Flugzeug wird einzeln mit Ankunftsslot betrachtet und es wird für jedes Flugzeug id vergeben
flugzeuge = []
flugzeug_id = 0

# Gehe durch alle Slots im Flugplan
for slot in range(len(flugplan)):
    anzahl_in_slot = flugplan[slot]  # Wie viele Flugzeuge kommen in diesem Slot

    for i in range(anzahl_in_slot):  # Für jedes Flugzeug in diesem Slot
        flugzeuge.append({"id": flugzeug_id, "ankunft": slot})
        flugzeug_id = flugzeug_id + 1

anzahl_flugzeuge = len(flugzeuge)

###### Alle angaben
# Plug-in
plugin_kosten = 50000      # € pro Plugin-Station
plugin_abschreibung = 10   # [Jahre]
plugin_kosten_jahr = plugin_kosten/plugin_abschreibung
#plugin_wirkungsgrad = 0.95

#Daten für Ladeverfahren CC-CV - Ladezeit
plugin_spannung_max = 800 #V
plugin_spannung_min = 600 #V
plugin_strom_max = 125 #A
plugin_strom_min = 10 #A
plugin_cc_anteil = 0.80 # 80% CC, 20% CV ?

#Swap-Angaben
swap_kosten = 50000    # € pro Swap-Station
swapbat_kosten = 15000
swap_wechsel = 10      #min ---- später genauer
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
ladeeffizienz = 0.93  # 93% Effizienz

strompreis_kwh = 0.30  # €/kWh
netz_max_kw = 2000 #kW

#PV-Anlagen
pv_flaeche = 2000 #verfügbare Fläche m^2 
pv_kosten_pro_m2 = 200 #€/m^2
pv_wirkungsgrad = 0.80
globalstrahlung = 1100 # kWh/m²/Jahr
pv_abschreibung = 25 # [Jahren] Lebensdauer der PV-Anlage

#Sonnenstrahlung
globalstrahlung_winter = 40  # kWh/m²/Monat (vllt. Dezember als Worst Case)
globalstrahlung_sommer = 200  # kWh/m²/Monat (Juli - Best Case)

# opex: energiekosten

# opex: Personalkosten
#von der Zeitvorgängen abhängig

# Ladezeiten - Annahmen: !! später anhand Ladeverfahren
plugin_ladezeit = 75  # min
swap_zeit = 8     # min
swap_ladezeit = 75

# Flugzeug-Parameter
fzg_reichweite = 463    # km
fzg_geschw = 489       # km/h
pax = 44
flugzeit = fzg_reichweite/fzg_geschw * 60   # min
flugzeit_gesamt = flugzeit * 2              # hin und zurück

bat_blockzeit = (swap_ladezeit * 2) + flugzeit + swap_zeit   # min

# Turnaround

turnaround_swap = 25  # min (Annahme für Turnaround mit battery swap) - später kann aufgeschlüsselt werden
batterie_leihgebuehr = 300  # EUR pro Swap

# Delay-Kosten

delay_kosten = 50    # EUR pro Minute Wartezeit

# Opportunitätskosten (Kosten, die nicht verdient werden bspw. durch Delay - entgangener Gewinn)

opportunitaet_kosten = 60   # EUR/min
#opportunitaet_plugin = plugin_ladezeit - turnaround_swap ---

# Begrenzungen in Kapazität
max_plugin_stationen = 10
max_swap_stationen = 10    
max_batterien = 20



# 2: Modell erstellen

# Gurobi-Modell erstellen
model = gp.Model("Kostenoptimierung")

# WICHTIG für die Ausgabe: 0-nur Endergebnis wird gezeigt; 1 - kann man sehen wie Gurobi optimiert
model.setParam('OutputFlag', 0) 




# 3: Entscheidungsvariablen

# Variable 1: Wie viele Plugin-Stationen brauchen wir?
anzahl_plugin = model.addVar(
    vtype=GRB.INTEGER,  # Muss eine Ganzzahl sein
    lb=0,               # Minimum: 0 Stationen
    name="Anzahl_Plugin")

# Variable 2: Wie viele Swap-Stationen und Batterien für Batteriwechsel?
anzahl_swap = model.addVar(vtype=GRB.INTEGER,lb=0,name="Anzahl_Swap")
anzahl_bat = model.addVar(vtype=GRB.INTEGER,lb=0,name="Anzahl_Batterien")

# Strom vom Netz pro Stunde (falls PV+ESS nicht reicht)
stromnetz = {}
for t in range(anzahl_slots):
    # wird für jedes Slot eigene Variable erzeugt
    stromnetz[t] = model.addVar(vtype=GRB.CONTINUOUS, lb=0, name=f"Netz_Strom_{t}")

# Pro Slot

plugin_start = {} # plugin_start[t] = Anzahl Plug-in
swap_start = {}

for t in range(anzahl_slots):
    # wie viel ladesäulen werden jede stunden benutzt
    plugin_start[t] = model.addVar(vtype=GRB.INTEGER, lb=0, name=f"Plugin_Start_{t}")
    swap_start[t] = model.addVar(vtype=GRB.INTEGER, lb=0, name=f"Swap_Start_{t}")

# Variablen für einzelne Flugzeuge

ist_plugin = {}  # ist_plugin[f] = 1 wenn Flugzeug f Plugin nutzt, sonst 0
ist_swap = {}    # ist_swap[f] = 1 wenn Flugzeug f Swap nutzt
start_slot = {}  # start_slot[f] = In welchem Slot startet die Ladung?
wartezeit = {}   # wartezeit[f] = Wartezeit in Slots (nicht Min)

for f in range(anzahl_flugzeuge):
    ist_plugin[f] = model.addVar(vtype=GRB.BINARY, name=f"Plugin_Flugzeug_{f}")
    ist_swap[f] = model.addVar(vtype=GRB.BINARY, name=f"Plugin_Flugzeug_{f}")

    #Anfang von Ladung (Slot) soll später (>=) als der Ankunft sein
    ankunft = flugzeuge[f]["ankunft"]
    start_slot[f] = model.addVar(vtype=GRB.INTEGER, lb=ankunft, ub=anzahl_slots-1, name=f"Start_Slot_{f}")

    # Start-Slot - Ankunft-Slot
    wartezeit[f] = model.addVar(vtype=GRB.INTEGER, lb=0, name=f"Wartezeit_{f}")
    
# CC-CV Ladung (für später)
delta_soc = soc_ende - soc_start
energie_zu_laden = bat_kapazit * delta_soc #kWh


# Energie mit Verlusten
energie_benoetigt = energie_zu_laden / ladeeffizienz  #--- oder einzeln für plugin/swap?

# PV-Produktion (Sommerzeit)
pv_monat_pro_m2 = globalstrahlung_sommer * pv_wirkungsgrad  # kWh/m²/Monat
pv_tag_pro_m2 = pv_monat_pro_m2 / 31  # kWh/m²/Tag (31 Tage im Juli)

# Tagesprofil (oder gesamt am Tag)
sonne_profil = [0.02, 0.05, 0.08, 0.12, 0.15, 0.18]


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



#  4: Zielfunktion

zielfkt = capex + opex

model.setObjective(zielfkt, GRB.MINIMIZE)


# 5: Nebenbedingungen

#NB 1 - Bedarf decken + Kap. beachten

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

    # Bedarf dieser Stunde (vereinfacht: Anzahl Flugzeuge * Energie pro Flugzeug)
    # pro Flugzeug: energie_benoetigt kWh
    bedarf_kwh = flugplan[t] * energie_benoetigt

    # Energie-Bilanz: PV + Netzstrom >= Bedarf
    model.addConstr(
        pv_prod_kwh + stromnetz[t] >= bedarf_kwh,
        name=f"Energie_{t}"
    )

#NB 4 - Spannung/Leistung darf nicht Netzstromwerte überschreiten?
#NB 5


# 6: Optimieren

model.optimize()

# 7: Ergebnis

if model.status == GRB.OPTIMAL:
    
    print("Lösung gefunden!")

    # Ergebnisse auslesen
    plugin_anzahl = int(anzahl_plugin.X)
    swap_anzahl = int(anzahl_swap.X)
    batterien_anzahl = int(anzahl_swapbat.X)

    print(f"\nLösung:")
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
    print("Keine Lösung gefunden!")

