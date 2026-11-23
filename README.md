# Config4MBS
Erstellt Konfigurationsdateien für das MBS Gateway

MBS Konfigurations-Generator
============================
Unabhängiges Community-/Hilfswerkzeug zur Generierung von Konfigurationsdateien für MBS-Gateways; kein offizielles Produkt der MBS GmbH  https://www.mbs-solutions.de/

-Erzeugt aus einer CSV-Datenpunktliste die MBS-Gateway-Dateien:

  ModbusRTU>ModbusTCP :  dispatch.txt  modmster1.txt  mbtcp1.txt

  ModbusRTU>BacnetIP  :  dispatch.txt  modmster1.txt  bac1.txt

  ModbusIP-->ModbusIP :  dispatch.txt  mbtcp1.txt   (alles über Route 860:
                         erst Remote-Geräte mit IP, dann lokaler Server 0.0.0.0)

Ablauf:  Fenster 1 (Projektname + Protokoll) 
 ->  Fenster 2 (CSV wählen)
 ->  Ordner <Projektname> wird neben diesem Skript angelegt.


CSV-Format (Trenner ; oder , -- UTF-8 oder Windows-1252, 1. Zeile = Kopf)

-Spalte         Pflicht  Beschreibung
_____________________________________

UnitName       nein     Gerätename, Prefix im Namen ("klima 1"). Leer = wie Zeile darüber

Description    ja       Bezeichnung des Datenpunkts ("unit setpoint temperature day")

Slave          ja       Modbus-Slave-Adresse (1..247)

Register       ja       coil oder holding

Address        ja       Adresse als Zahl, z.B. 1000  (die alte Schreibweise "coil 1000"
                        in der Spalte Address wird weiterhin akzeptiert)

Format         nein     nur holding: f = Float (Standard)

Access         nein     r oder rw (Schreibzugriff). Leer: BV/AV = rw, sonst r

Type           BACnet   BI, BV (nur coil)  /  AI, AV (nur holding)

Instance       nein     BACnet-Instanz. Leer = automatisch (Slave*1000 + n)

Unit_States    nein     Binär: "inaktiv;aktiv" (z.B. "off;on")
                        Analog: Einheit (°C, %rF, %, bar, kW ...) oder BACnet-Code (62)

Resolution     nein     nur AI/AV, Standard 0.1


-Zusätzliche CSV-Spalten nur für ModbusIP-->ModbusIP 
____________________________________________________

IP             ja       IP des Remote-Geräts, optional mit Port: 192.168.0.1[:502]

Slave          ja       Unit-ID des Remote-Geräts (0..255)

Register       ja       coil, holding, input oder status

Address        ja       Registeradresse (Remote-Gerät)

Format         nein     BIT, UINT16, ... (Standard: status/coil = BIT, holding/input = UINT16)

Access         nein     r oder rw. Leer: holding/coil = rw, input/status = r

TCP_Slave      nein     Unit-ID auf der Server-Seite (0.0.0.0), Standard = Slave

TCP_Register   nein     Registertyp Server-Seite, Standard = Register

TCP_Address    nein     Adresse Server-Seite, Standard = Address

TCP_Format     nein     Format Server-Seite, Standard = Format


TCP_Format     nein     nur ModbusTCP: BIT, UINT8/16/32/64, SINT8/16/32/64, FLOAT32/64,
                        FIXED32/48 + optional S:<0-3> F:<faktor> O:<offset> M:<0-2>
                        z.B. "SINT16 F:10". Leer: coil=BIT, holding=FLOAT32 (bei Format f)

TCP_Slave      nein     nur ModbusTCP: Slave-Adresse auf TCP-Seite (Standard = Slave)

TCP_Address    nein     nur ModbusTCP: Adresse auf TCP-Seite (Standard = Address)
