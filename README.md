# MBS Konfigurations-Generator

> **Hinweis:** Unabhängiges Community- und Hilfswerkzeug zur Generierung von Konfigurationsdateien für MBS-Gateways. Kein offizielles Produkt der [MBS GmbH](https://www.mbs-solutions.de/).

Der **MBS Konfigurations-Generator** erzeugt aus einer CSV-Datenpunktliste automatisch die benötigten Konfigurationsdateien für MBS-Gateways.

---

## Unterstützte Gateway-Protokolle & Ausgabedateien

| Protokoll | Erzeugte Dateien | Besonderheiten |
| :--- | :--- | :--- |
| **ModbusRTU → ModbusTCP** | `dispatch.txt`, `modmster1.txt`, `mbtcp1.txt` | — |
| **ModbusRTU → BacnetIP** | `dispatch.txt`, `modmster1.txt`, `bac1.txt` | BACnet-Objekte & -Instanzen |
| **ModbusIP → ModbusIP** | `dispatch.txt`, `mbtcp1.txt` | Alles über Route `860` (zuerst Remote-Geräte mit IP, danach lokaler Server `0.0.0.0`) |

---

## Ablauf

1. **Fenster 1:** Projektnamen und gewünschte Gateway-Richtung festlegen.
2. **Fenster 2:** CSV-Datenpunktliste auswählen.
3. **Ausgabe:** Der Zielordner `<Projektname>` wird automatisch neben diesem Skript angelegt und mit den generierten Dateien befüllt.

---

## CSV-Format

* **Trennzeichen:** `;` oder `,`
* **Zeichencodierung:** UTF-8 oder Windows-1252
* **Kopfzeile:** Erste Zeile muss die Spaltennamen enthalten

### Basis-Spalten

| Spalte | Pflicht | Beschreibung |
| :--- | :---: | :--- |
| `UnitName` | Nein | Gerätename als Präfix im Namen (z. B. `klima 1`). Leer = Wert aus der Zeile darüber übernehmen. |
| `Description` | **Ja** | Bezeichnung des Datenpunkts (z. B. `unit setpoint temperature day`). |
| `Slave` | **Ja** | Modbus-Slave-Adresse (`1`–`247`). |
| `Register` | **Ja** | `coil` oder `holding`. |
| `Address` | **Ja** | Registeradresse als Zahl (z. B. `1000`). *(Die ältere Schreibweise `coil 1000` in dieser Spalte wird weiterhin unterstützt.)* |
| `Format` | Nein | Nur bei `holding`: `f` = Float (Standard). |
| `Access` | Nein | `r` oder `rw` (Schreibzugriff). Leer: `BV`/`AV` = `rw`, sonst `r`. |
| `Type` | BACnet | `BI`, `BV` (nur bei `coil`) / `AI`, `AV` (nur bei `holding`). |
| `Instance` | Nein | BACnet-Instanznummer. Leer = automatische Vergabe (`Slave * 1000 + n`). |
| `Unit_States` | Nein | Binär: `"inaktiv;aktiv"` (z. B. `"off;on"`).<br>Analog: Einheit (`°C`, `%rF`, `%`, `bar`, `kW` …) oder BACnet-Code (z. B. `62`). |
| `Resolution` | Nein | Nur bei `AI`/`AV`, Standardwert `0.1`. |

### Zusätzliche & abweichende Spalten für `ModbusTCP`

| Spalte | Pflicht | Beschreibung |
| :--- | :---: | :--- |
| `TCP_Format` | Nein | Nur ModbusTCP: `BIT`, `UINT8/16/32/64`, `SINT8/16/32/64`, `FLOAT32/64`, `FIXED32/48` + optional `S:<0-3>`, `F:<faktor>`, `O:<offset>`, `M:<0-2>` (z. B. `"SINT16 F:10"`). Leer: `coil` = `BIT`, `holding` = `FLOAT32` (bei `Format` = `f`). |
| `TCP_Slave` | Nein | Nur ModbusTCP: Slave-Adresse auf TCP-Seite (Standard = `Slave`). |
| `TCP_Address` | Nein | Nur ModbusTCP: Adresse auf TCP-Seite (Standard = `Address`). |

### Zusätzliche & abweichende Spalten nur für `ModbusIP → ModbusIP`

| Spalte | Pflicht | Beschreibung |
| :--- | :---: | :--- |
| `IP` | **Ja** | IP-Adresse des Remote-Geräts, optional mit Port: `192.168.0.1[:502]`. |
| `Slave` | **Ja** | Unit-ID des Remote-Geräts (`0`–`255`). |
| `Register` | **Ja** | `coil`, `holding`, `input` oder `status`. |
| `Address` | **Ja** | Registeradresse am Remote-Gerät. |
| `Format` | Nein | `BIT`, `UINT16`, … (Standard: `status`/`coil` = `BIT`, `holding`/`input` = `UINT16`). |
| `Access` | Nein | `r` oder `rw`. Leer: `holding`/`coil` = `rw`, `input`/`status` = `r`. |
| `TCP_Slave` | Nein | Unit-ID auf der Server-Seite (`0.0.0.0`), Standard = `Slave`. |
| `TCP_Register` | Nein | Registertyp auf der Server-Seite, Standard = `Register`. |
| `TCP_Address` | Nein | Registeradresse auf der Server-Seite, Standard = `Address`. |
| `TCP_Format` | Nein | Datenformat auf der Server-Seite, Standard = `Format`. |
