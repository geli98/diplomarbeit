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
            1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0,  #...
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,  
            1, 0, 1, 0, 1, 0, 1, 0, 0, 0, 0, 0,  
            1, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0,  
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,  
            1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0,  
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,  #...
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]  # Stunde 10 (15:00-16:00)

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

# Turnaround

turnaround_swap = 25  # min (Annahme für Turnaround mit battery swap) - später kann aufgeschlüsselt werden
batterie_leihgebuehr = 300  # EUR pro Swap

# Flugzeug-Parameter
fzg_reichweite = 463    # km
fzg_geschw = 489        # km/h
pax = 44
flugzeit = fzg_reichweite/fzg_geschw * 60   # min
flugzeit_gesamt = flugzeit * 2 + turnaround_swap              # hin und zurück + turnaround am anderen Flughafen

bat_blockzeit = (swap_ladezeit * 2) + flugzeit + swap_zeit   # min


# Airline-Kosten

delay_kosten = 50    # EUR pro Minute Wartezeit
abstellentgelt_std = 15 

# Opportunitätskosten (Kosten, die nicht verdient werden bspw. durch Delay - entgangener Gewinn)

opportunitaet_kosten = 60   # EUR/min
#opportunitaet_plugin = plugin_ladezeit - turnaround_swap ---

# Begrenzungen in Kapazität
max_plugin_stationen = 10
max_swap_stationen = 10    
max_batterien = 20

# PV - Energiespeicher
speicher_kapazitaet = 5000  # kWh (feste Groesse)
speicher_effizienz = 0.90   # 90% Effizienz beim Laden/Entladen
speicher_kosten_kwh = 150   # EUR pro kWh Kapazitaet



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
    ist_swap[f] = model.addVar(vtype=GRB.BINARY, name=f"Swap_Flugzeug_{f}")

    #Anfang von Ladung (Slot) soll später (>=) als der Ankunft sein
    ankunft = flugzeuge[f]["ankunft"]
    start_slot[f] = model.addVar(vtype=GRB.INTEGER, lb=ankunft, ub=anzahl_slots-1, name=f"Start_Slot_{f}")

    # Start-Slot - Ankunft-Slot
    wartezeit[f] = model.addVar(vtype=GRB.INTEGER, lb=0, name=f"Wartezeit_{f}")

# Bodenzeit für Abstellkosten
bodenzeit_stunden = {}
for f in range(anzahl_flugzeuge):
    bodenzeit_stunden[f] = model.addVar(vtype=GRB.INTEGER, lb=1, name=f"Bodenzeit_Std_{f}")


def belegte_stationen(aktueller_slot, ladezeit_minuten):
    # es wird aktueller slot (int) geprüft mit ladezeit_minuten (int)

    # Logik
    # startzeit(i) + ladezeit > aktueller slot --- Ladevorgang noch nicht fertig
    # Bsp. aktueller_slot = 6 (Minute 30) und ladezeit 75 min:
    # 0 + 75 > 30 --- Ladegerät noch belegt

    aktuelle_zeit = slot_startzeit[aktueller_slot]

    belegte_stationen = []  #Liste für belegte Ladegeräte

    for i in range(aktueller_slot + 1): 
        # Ladevorgang fängt in dem Slot
        start_zeit_i = slot_startzeit[i]   # slot_startzeit[2] = 06:10
        
        # Zeit, wann der Vorgang fertig ist
        ende_zeit_i = start_zeit_i + ladezeit_minuten
        # 
        # Prüfung, ob der Ladevorgang aus Slot i noch aktiv
        # Wenn ja, dann wird in die Liste hinzugefügt
        if ende_zeit_i > aktuelle_zeit:
            belegte_stationen.append(i)

    return belegte_stationen


#  4: Zielfunktion

# ---Hilfsberechnungen---
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


# CAPEX (Flughafen)
capex_plugin = plugin_kosten * anzahl_plugin
capex_swap = swap_kosten * anzahl_swap
capex_swapbat = swapbat_kosten * anzahl_bat
capex_pv = pv_flaeche * pv_kosten_pro_m2

capex = capex_plugin + capex_swap + capex_swapbat + capex_pv

# OPEX (Flughafen)
# Energiekosten
# summiert Stromwerte über alle Slots
strom_pro_tag = gp.quicksum(stromnetz[t] for t in range(anzahl_slots))
opex_energie = strom_pro_tag * strompreis_kwh #* 365 * planungsjahre

# opex - Wartung: 10% der Anschaffung × Anzahl Stationen
plugin_wartung = 0.10 * plugin_kosten * anzahl_plugin
swap_wartung = 0.10 * swap_kosten * anzahl_swap

opex_wartung = plugin_wartung + swap_wartung

opex = opex_energie + opex_wartung #+ opex_personal

# Flughafen-Kosten gesamt
kosten_flughafen = capex + opex

# Kosten (Airlines)
total_plugin = gp.quicksum(plugin_start[t] for t in range(anzahl_slots))
total_swap = gp.quicksum(swap_start[t] for t in range(anzahl_slots))

# Abstellkosten basierend auf Bodenzeit in ganzen Stunden (aufgerundet)

kosten_abstellen = gp.quicksum(bodenzeit_stunden[f] * abstellentgelt_std for f in range(anzahl_flugzeuge))
kosten_batterie = total_swap * batterie_leihgebuehr

# Delay-Kosten basierend auf Wartezeit pro Flugzeug
kosten_delay = gp.quicksum(wartezeit[f] * slot_dauer * delay_kosten for f in range(anzahl_flugzeuge))

kosten_airline = kosten_abstellen + kosten_batterie + kosten_delay #+ kosten_opportunitaet

# ---- ZIELFUNKTION GESAMT -----

zielfkt = kosten_flughafen + kosten_airline

model.setObjective(zielfkt, GRB.MINIMIZE)


# 5: Nebenbedingungen


for t in range(anzahl_slots):

    #NB 1 --- Plug-In Kapazität
    belegte_plugin_slots = belegte_stationen(t, plugin_ladezeit)

    # Anzahl der belegten Plug-in Stationen in Slot t; i ist Slot-Nr.
    # bsp. plugin_belegt = plugin_start[0] + plugin_start[1] + plugin_start[2] + ...
    plugin_belegt = gp.quicksum(plugin_start[i] for i in belegte_plugin_slots)

    # Diese Summe darf nicht größer sein als die Anzahl Plugin-Stationen
    model.addConstr(plugin_belegt <= anzahl_plugin, name=f"Plugin_Kap_Slot_{t}")

    #NB 2 --- Swap Kapazität---
    # muss überprüft werden, welche Stationen in Slot t belegt sind

    flugzeit_slots = math.ceil(flugzeit_gesamt / slot_dauer)  # 114/5 = 23 Slots
    ladezeit_slots = math.ceil(swap_ladezeit / slot_dauer)

    swap_stationen_belegt = 0
    for i in range(t + 1):  # Alle früheren Slots bis einschliesslich t prpfen
        # Wann kommt die Batterie von Swap i zurueck? -> Slot i + flugzeit_slots
        batterie_zurueck_slot = i + flugzeit_slots #+ evtl. lade- oder swapzeit an anderem Flughafen

        # Wann ist die Batterie fertig geladen? -> batterie_zurueck_slot + ladezeit_slots
        batterie_fertig_slot = batterie_zurueck_slot + ladezeit_slots

        # Belegt diese Batterie in Slot t eine Station?
        # Ja, wenn: batterie_zurueck_slot <= t < batterie_fertig_slot
        if batterie_zurueck_slot <= t < batterie_fertig_slot:
            swap_stationen_belegt = swap_stationen_belegt + swap_start[i]

    model.addConstr(swap_stationen_belegt <= anzahl_swap, name=f"Swap_Station_Kap_{t}")

    #NB 3 --- Batterie Kapazität ---

    #Blockzeit = Flugzeit + Ladezeit (+ swap davor)
    belegte_bat_slots = belegte_stationen(t, bat_blockzeit)
    bat_blockiert = gp.quicksum(swap_start[i] for i in belegte_bat_slots)

    model.addConstr(bat_blockiert <= anzahl_bat, name=f"Batterie_Verfuegbar_{t}")


# NB 4: Verbindung zwischen Flugzeug-Variablen und Slot-Variablen
# plugin_start[t] = Anzahl Flugzeuge die in Slot t mit Plugin starten
# Das muss gleich sein wie die Summe aller ist_plugin[f] wo start_slot[f] == t

# Hilfsvariable: startet_in_slot[f,t] = 1 wenn Flugzeug f in Slot t startet
startet_in_slot = {}
for f in range(anzahl_flugzeuge):
    for t in range(anzahl_slots):
        startet_in_slot[f, t] = model.addVar(vtype=GRB.BINARY, name=f"Startet_{f}_in_{t}")

# Verbindung: startet_in_slot[f,t] = 1 genau dann wenn start_slot[f] == t
for f in range(anzahl_flugzeuge):
    # Genau ein Slot muss der Start-Slot sein
    model.addConstr(gp.quicksum(startet_in_slot[f, t] for t in range(anzahl_slots)) == 1, name=f"Genau_ein_Start_{f}")
    # start_slot[f] = Summe(t * startet_in_slot[f,t])
    model.addConstr(start_slot[f] == gp.quicksum(t * startet_in_slot[f, t] for t in range(anzahl_slots)), name=f"Start_Slot_Wert_{f}")

# Jetzt verbinden wir plugin_start und swap_start mit den Flugzeug-Entscheidungen
for t in range(anzahl_slots):
    # plugin_start[t] = Anzahl Flugzeuge die in Slot t mit Plugin starten
    model.addConstr(
        plugin_start[t] == gp.quicksum(ist_plugin[f] * startet_in_slot[f, t] for f in range(anzahl_flugzeuge)), name=f"Plugin_Start_Verbindung_{t}")
    # swap_start[t] = Anzahl Flugzeuge die in Slot t mit Swap starten
    model.addConstr(
        swap_start[t] == gp.quicksum(ist_swap[f] * startet_in_slot[f, t] for f in range(anzahl_flugzeuge)), name=f"Swap_Start_Verbindung_{t}")



#NB 5 - Begrenzung der Stationen und Batterien
model.addConstr(anzahl_plugin <= max_plugin_stationen, name="Max_Plugin")
model.addConstr(anzahl_swap <= max_swap_stationen, name="Max_Swap")
model.addConstr(anzahl_bat <= max_batterien, name="Max_Batterien")

#NB 6 -- Nebenbedingungen fuer einzelne Flugzeuge --
for f in range(anzahl_flugzeuge):
    ankunft = flugzeuge[f]["ankunft"]

    #NB 6a: Jedes Flugzeug muss entweder Plugin ODER Swap nutzen (nicht beides, nicht keins)
    model.addConstr(ist_plugin[f] + ist_swap[f] == 1, name=f"Entweder_Plugin_oder_Swap_{f}")

    #NB 6b: Wartezeit = Start-Slot - Ankunfts-Slot
    model.addConstr(wartezeit[f] == start_slot[f] - ankunft, name=f"Wartezeit_Berechnung_{f}")

    # NB 6c: Bodenzeit in Stunden (aufgerundet für Abstellkosten - jede angefangene Stunde)
    # Bodenzeit = Wartezeit + Ladezeit (Plugin: 75 min, Swap: 25 min Turnaround)
    #
    # Aufrunden: stunden >= bodenzeit/60 und stunden <= bodenzeit/60 + 0.99
    bodenzeit_min = wartezeit[f] * slot_dauer + ist_plugin[f] * plugin_ladezeit + ist_swap[f] * turnaround_swap
    model.addConstr(bodenzeit_stunden[f] >= bodenzeit_min / 60, name=f"Bodenzeit_Min_{f}")
    model.addConstr(bodenzeit_stunden[f] <= bodenzeit_min / 60 + 0.99, name=f"Bodenzeit_Max_{f}")


#NB 5 - Energiebilanz (Bedarf <= verfügbare Strom (PV-Strom + Netzstrom + Speicher))

# PV-Strahlung (Sommer) - best case
strahlung_stunde = [121, 173, 210, 262, 297, 319, 315, 296, 266, 216]  # J/cm²

""" stündlich/slot/tag
for t in range(anzahl_slots):
    # PV-Produktion dieser Stunde
    pv_prod_kwh = pv_flaeche * pv_tag_pro_m2 * sonne_profil[t]

    # Bedarf dieser Stunde (vereinfacht: Anzahl Flugzeuge * Energie pro Flugzeug)
    # pro Flugzeug: energie_benoetigt kWh
    bedarf_kwh = flugplan[t] * energie_benoetigt

    # Energie-Bilanz: PV + Netzstrom >= Bedarf
    model.addConstr(pv_prod_kwh + stromnetz[t] >= bedarf_kwh,name=f"Energie_{t}")
"""

speicher_stand = {-1: 0} # stand der speicher am ende der Stunde h, # Speicher fängt bei 0 an
speicher_ein = {} # strom, die hergestellt wird und gespeichert
speicher_aus = {} # 

umrechnung_pv = 1/360  #J/m² --> kWh/m²

# Netzstrom pro Std
stromnetz = {}
for h in range(10): 
    stromnetz[h] = model.addVar(vtype=GRB.CONTINUOUS, lb=0, name=f"Netz_Stunde_{h}")


for h in range(10):   #range - Betriebsstunden
    speicher_stand[h] = model.addVar(vtype=GRB.CONTINUOUS, lb=0, ub=speicher_kapazitaet, name=f"Speicher_Stand_{h}")
    speicher_ein[h] = model.addVar(vtype=GRB.CONTINUOUS, lb=0, name=f"Speicher_Ein_{h}")
    speicher_aus[h] = model.addVar(vtype=GRB.CONTINUOUS, lb=0, name=f"Speicher_Aus_{h}")

for h in range(10):
    # PV pro Std [kWh]
    pv_std = pv_flaeche * strahlung_stunde[h] * umrechnung_pv * pv_wirkungsgrad

    # jede stunde 12 slots
    slot_start = h * 12 
    slot_ende = (h + 1) * 12

    # Bedarf = Summe aller Flugzeuge die in dieser Stunde mit Laden STARTEN
    bedarf_stunde = gp.quicksum(startet_in_slot[f, t] * energie_benoetigt for f in range(anzahl_flugzeuge)
        for t in range(slot_start, slot_ende))

    # Energiebilanz
    model.addConstr(
        pv_std + stromnetz[h] + speicher_aus[h] * speicher_effizienz >= stromnetz[h] + speicher_ein[h], name=f"Energie_Stunde_{h}")
    
    # Speicher-Stand pro std
    model.addConstr(
        speicher_stand[h] == speicher_stand[h-1] + speicher_ein[h] * speicher_effizienz - speicher_aus[h], name=f"Speicher_Update_{h}")

# 6: Optimieren

model.optimize()

# 7: Ergebnis

if model.status == GRB.OPTIMAL:
    
    print("Lösung gefunden!")

    # Ergebnisse auslesen
    n_plugin = int(anzahl_plugin.X)
    n_swap = int(anzahl_swap.X)
    n_bat = int(anzahl_bat.X)
    n_plugin_total = sum(plugin_start[t].X for t in range(anzahl_slots))
    n_swap_total = sum(swap_start[t].X for t in range(anzahl_slots))

    print(f"\nLösung:")

    # Delay-Kosten berechnen
    total_wartezeit_slots = sum(wartezeit[f].X for f in range(anzahl_flugzeuge))
    total_wartezeit_min = total_wartezeit_slots * slot_dauer
    total_delay_kosten = total_wartezeit_min * delay_kosten

    print(f"Plugin: {n_plugin} ; Swap: {n_swap} ; Batterien: {n_bat} ")
    print(f"Ladevorgaenge: {n_plugin_total:.0f} Plugin, {n_swap_total:.0f} Swap")
    print(f"\nGesamtkosten (optimiert): €{model.ObjVal:,.2f}")

    print("\nDetails pro Flugzeug:")
    for f in range(anzahl_flugzeuge):
        ankunft = flugzeuge[f]["ankunft"]
        start = int(start_slot[f].X)
        warte = int(wartezeit[f].X)
        typ = "Plugin" if ist_plugin[f].X > 0.5 else "Swap"
        print(f"  Flugzeug {f}: Ankunft Slot {ankunft}, Start Slot {start}, Wartezeit {warte} Slots ({warte*slot_dauer} min), {typ}")

else:
    print("Keine Lösung gefunden!")

