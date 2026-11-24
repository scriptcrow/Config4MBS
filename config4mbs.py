#!/usr/bin/env python3
#pyinstaller --noconsole --icon=MBS.ico --add-data "MBS.ico;." config4mbs.py
"""
MBS Konfigurations-Generator
============================
Unabhängiges Community-/Hilfswerkzeug zur Generierung von Konfigurationsdateien für MBS-Gateways; kein offizielles Produkt der MBS GmbH https://www.mbs-solutions.de/

Erzeugt aus einer CSV-Datenpunktliste die MBS-Gateway-Dateien:

  ModbusRTU-->ModbusTCP :  dispatch.txt  modmster1.txt  mbtcp1.txt
  ModbusRTU-->BacnetIP  :  dispatch.txt  modmster1.txt  bac1.txt
  ModbusIP-->ModbusIP :  dispatch.txt  mbtcp1.txt   (alles ueber Route 860:
                         erst Remote-Geraete mit IP, dann lokaler Server 0.0.0.0)

Ablauf:  Fenster 1 (Projektname + Richtung)  ->  Fenster 2 (CSV waehlen)
         ->  Ordner <Projektname> wird neben diesem Skript angelegt.

CSV-Format (Trenner ; oder , -- UTF-8 oder Windows-1252, 1. Zeile = Kopf)
------------------------------------------------------------------------
Spalte         Pflicht  Beschreibung
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

--- Zusätzliche CSV-Spalten nur für ModbusIP-->ModbusIP -------------------
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
-----------------------------------------------------------------------------
TCP_Format     nein     nur ModbusTCP: BIT, UINT8/16/32/64, SINT8/16/32/64, FLOAT32/64,
                        FIXED32/48 + optional S:<0-3> F:<faktor> O:<offset> M:<0-2>
                        z.B. "SINT16 F:10". Leer: coil=BIT, holding=FLOAT32 (bei Format f)
TCP_Slave      nein     nur ModbusTCP: Slave-Adresse auf TCP-Seite (Standard = Slave)
TCP_Address    nein     nur ModbusTCP: Adresse auf TCP-Seite (Standard = Address)
"""
import csv
import getpass
import re
import socket
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


MOD_CH = 80          # dispatch.txt: Kanal Modbus-Master   ("80 mod ...")
BAC_CH = 940         # dispatch.txt: Kanal BACnet          ("940 bac local.BV ...")
# Modbus-TCP-Treiber laut MBS-Doku (mbs-support.de/modbus-tcpip): Name "mbtcp",
# Routing-Adresse des ersten Treibers = 860. Das Zeilenformat in dispatch.txt ist
# analog zum BACnet
MBTCP_CH = 860
MBTCP_KEY = "mbtcp"
MBTCP_IP = "0.0.0.0"  # wie in mbtcp1.txt ("[S 0.0.0.0 1 coil 1002]")

MODES = ("[80]ModbusRTU ==> [860]ModbusTCP", "[80]ModbusRTU ==> [940]BacnetIP", "[860]ModbusTCP1 ==> [860]ModbusTCP2")

# BACnet-Einheitencodes. 
UNITS = {
    "": 95, "°c": 62, "c": 62, "%rf": 95, "%": 98, "k": 63, "pa": 53, "kpa": 54,
    "bar": 55, "kw": 48, "kwh": 19, "v": 5, "a": 3, "hz": 27, "rpm": 104,
    "h": 71, "min": 72, "s": 73, "m3/h": 135,
}

# Formate des Modbus-TCP-Treibers (Breite in 16-Bit-Registern)
TCP_WIDTH = {"BIT": 1, "UINT8": 1, "SINT8": 1, "UINT16": 1, "SINT16": 1, "UINT32": 2,
             "SINT32": 2, "UINT64": 4, "SINT64": 4, "FLOAT32": 2, "FLOAT64": 4,
             "FIXED32": 2, "FIXED48": 3}

ADDR_RE = re.compile(r"^(coil|holding)\s+(\d+)$", re.I)
COLS = {
    "unitname": "unitname", "device": "unitname", "geraet": "unitname", "gerät": "unitname",
    "description": "description", "datapoint": "description", "datenpunkt": "description",
    "slave": "slave",
    "register": "regtype", "registertyp": "regtype", "reg_type": "regtype",
    "address": "address", "adresse": "address",
    "format": "format",
    "access": "access", "zugriff": "access",
    "type": "type", "typ": "type",
    "instance": "instance", "instanz": "instance",
    "unit_states": "unit", "unit or states": "unit", "unit": "unit", "einheit": "unit",
    "resolution": "resolution", "aufloesung": "resolution", "auflösung": "resolution",
    "ip": "ip", "ip_adresse": "ip",
    "tcp_register": "tcp_regtype", "tcp_registertyp": "tcp_regtype",
    "tcp_format": "tcp_format",
    "tcp_slave": "tcp_slave", "tcp_address": "tcp_address", "tcp_adresse": "tcp_address",
}


def is_integer_fmt(fmt):
    """Ganzzahl-Format ohne Faktor/Offset -> Typbuchstabe M/S, sonst Analogwert X/Y."""
    t = fmt.upper().split()
    if not t:
        return False
    scaled = any(x.startswith(("F:", "O:")) for x in t[1:])
    return (t[0] == "BIT" or t[0].startswith(("UINT", "SINT"))) and not scaled


def check_tcp_format(spec, mtype):
    """Prueft 'FORMAT [S:n] [F:x] [O:x] [M:n]'. Rückgabe (normierter Text, Fehlertext)."""
    toks = spec.split()
    if not toks:
        return "", "Format leer"
    base = toks[0].upper()
    if base not in TCP_WIDTH:
        return "", f"Format '{toks[0]}' unbekannt (erlaubt: {', '.join(TCP_WIDTH)})"
    if mtype in ("coil", "status") and base != "BIT":
        return "", f"{mtype} erlaubt nur das Format BIT"
    if mtype in ("holding", "input") and base == "BIT":
        return "", f"BIT in {mtype} braucht eine Bitadresse ({mtype} 11.5) - noch nicht unterstützt"
    out = [base]
    for t in toks[1:]:
        k, _, v = t.partition(":")
        k = k.upper()
        try:
            if k == "S" and int(v) in (0, 1, 2, 3):
                pass
            elif k == "M" and int(v) in (0, 1, 2):
                pass
            elif k in ("F", "O"):
                float(v)
            else:
                raise ValueError
        except ValueError:
            return "", f"Parameter '{t}' ungültig (S:0-3, F:<zahl>, O:<zahl>, M:0-2)"
        out.append(f"{k}:{v}")
    return " ".join(out), ""


@dataclass
class DP:
    line: int
    device: str
    text: str
    slave: int
    mtype: str          # coil | holding
    addr: int
    fmt: str
    rw: bool
    btype: str = ""
    inst: int = 0
    inactive: str = ""
    active: str = ""
    unit_code: int = 95
    resolution: str = "0.1"
    tcp_slave: int = 0
    tcp_addr: int = 0
    tcp_fmt: str = ""

    @property
    def name(self):
        return f"{self.device} {self.text}".strip()


# --------------------------------------------------------------------------
# CSV einlesen
# --------------------------------------------------------------------------
def _read_text(path):
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("latin-1")


def parse_csv(path, mode):
    """Gibt (datenpunkte, fehlerliste) zurück."""
    errors, dps = [], []
    text = _read_text(path)
    lines = text.splitlines()
    if not lines:
        return [], ["Die CSV-Datei ist leer."]
    delim = ";" if lines[0].count(";") >= lines[0].count(",") else ","
    rows = list(csv.reader(lines, delimiter=delim))
    header = [COLS.get(h.strip().lower(), h.strip().lower()) for h in rows[0]]
    need = ["description", "slave", "address"] + (["type"] if mode == MODES[1] else [])
    missing = [c for c in need if c not in header]
    if missing:
        return [], [f"Pflichtspalte(n) fehlen: {', '.join(missing)}  (gefunden: {', '.join(header)})"]

    last_device = ""
    for n, row in enumerate(rows[1:], start=2):
        if not any(c.strip() for c in row) or row[0].lstrip().startswith("#"):
            continue
        r = {h: (row[i].strip() if i < len(row) else "") for i, h in enumerate(header)}
        err = lambda m: errors.append(f"Zeile {n}: {m}")

        if r.get("unitname"):
            last_device = r["unitname"]
        if not r["description"]:
            err("Description ist leer"); continue
        reg, a = r.get("regtype", "").lower(), r["address"]
        m = ADDR_RE.match(a)
        if m:                                      # alte Schreibweise "coil 1000"
            mtype, addr = m.group(1).lower(), int(m.group(2))
        elif reg in ("coil", "holding") and a.isdigit():
            mtype, addr = reg, int(a)
        elif a.isdigit():
            err(f"Register '{reg}' ungültig oder leer (coil oder holding)"); continue
        else:
            err(f"Address '{a}' ungültig (Zahl erwartet, z.B. 1000)"); continue
        try:
            slave = int(r["slave"]); assert 1 <= slave <= 247
        except Exception:
            err(f"Slave '{r['slave']}' ungültig (1..247)"); continue

        d = DP(n, last_device, r["description"], slave, mtype, addr,
               (r.get("format") or "f") if mtype == "holding" else "", False)
        d.tcp_slave, d.tcp_addr = slave, addr

        acc = r.get("access", "").lower()
        if acc not in ("", "r", "ro", "0", "rw", "w", "1", "yes"):
            err(f"Access '{acc}' ungültig (r oder rw)"); continue
        d.rw = acc in ("rw", "w", "1", "yes")

        if mode == MODES[1]:                       # ---- BACnet-Felder
            t = r["type"].upper()
            if t not in ("BI", "BV", "AI", "AV"):
                err(f"Type '{r['type']}' ungültig (BI, BV, AI, AV)"); continue
            if (t in ("BI", "BV")) != (mtype == "coil"):
                err(f"Type {t} passt nicht zu '{r['address']}' (coil=BI/BV, holding=AI/AV)"); continue
            d.btype = t
            if acc == "":
                d.rw = t in ("BV", "AV")
            if t in ("BV", "AV") and not d.rw:
                err(f"Type {t} ist schreibbar - Access darf nicht 'r' sein"); continue
            if r.get("instance"):
                try:
                    d.inst = int(r["instance"])
                except ValueError:
                    err(f"Instance '{r['instance']}' ungültig"); continue
            u = r.get("unit", "")
            if t in ("BI", "BV"):
                parts = re.split(r"[;#]", u, maxsplit=1)
                d.inactive = parts[0].strip()
                d.active = parts[1].strip() if len(parts) > 1 else ""
            else:
                key = u.lower()
                if key.isdigit():
                    d.unit_code = int(key)
                elif key in UNITS:
                    d.unit_code = UNITS[key]
                else:
                    err(f"Einheit '{u}' unbekannt - Zahl (BACnet-Code) eintragen oder UNITS erweitern"); continue
                d.resolution = r.get("resolution") or "0.1"
        else:                                      # ---- Modbus-TCP-Felder
            try:
                if r.get("tcp_slave"): d.tcp_slave = int(r["tcp_slave"])
                if r.get("tcp_address"): d.tcp_addr = int(r["tcp_address"])
            except ValueError:
                err("TCP_Slave/TCP_Address ungültig"); continue
            spec = r.get("tcp_format", "")
            if not spec:
                spec = "BIT" if mtype == "coil" else ("FLOAT32" if d.fmt.lower() == "f" else d.fmt)
            d.tcp_fmt, e = check_tcp_format(spec, mtype)
            if e:
                err(e); continue
        dps.append(d)

    # Duplikate / automatische Instanzen
    seen = {}
    for d in dps:
        k = (d.slave, d.mtype, d.addr)
        if k in seen:
            errors.append(f"Zeile {d.line}: Modbus-Adresse {d.mtype} {d.addr} (Slave {d.slave}) doppelt (Zeile {seen[k]})")
        seen[k] = d.line
    if mode == MODES[0]:                      # Register-Überlappung (Formate > 16 Bit)
        regs = {}
        for d in dps:
            if d.mtype != "holding":
                continue
            base = d.tcp_fmt.split()[0]
            for off in range(TCP_WIDTH[base]):
                k = (d.tcp_slave, d.tcp_addr + off)
                if k in regs:
                    ol, ob = regs[k]
                    errors.append(f"Zeile {d.line}: Register {k[1]} (Slave {k[0]}) ist schon durch Zeile {ol} "
                                  f"belegt ({ob} braucht {TCP_WIDTH[ob]} Register)")
                    break
                regs[k] = (d.line, base)
    if mode == MODES[1]:
        used = {}
        for d in dps:
            if d.inst:
                if (d.btype, d.inst) in used:
                    errors.append(f"Zeile {d.line}: BACnet {d.btype} {d.inst} doppelt (Zeile {used[(d.btype, d.inst)]})")
                used[(d.btype, d.inst)] = d.line
        taken = {i for (_, i) in used}
        counters = {}
        for d in dps:
            if not d.inst:
                c = counters.get(d.slave, d.slave * 1000)
                while c in taken:
                    c += 1
                d.inst = c; taken.add(c); counters[d.slave] = c + 1
    if not dps and not errors:
        errors.append("Keine Datenpunkte gefunden.")
    return dps, errors


# --------------------------------------------------------------------------
# Textbausteine
# --------------------------------------------------------------------------
# --------------------------------------------------------------------------
# Modus ModbusIP-->ModbusIP  (Route 860 -> Route 860, alles in mbtcp1.txt)
# --------------------------------------------------------------------------
IP_REGS = ("coil", "holding", "input", "status")


@dataclass
class IPDP:
    line: int
    unit: str
    text: str
    ip: str
    slave: int
    reg: str
    addr: int
    fmt: str
    rw: bool
    tslave: int = 0
    treg: str = ""
    taddr: int = 0
    tfmt: str = ""

    @property
    def name(self):
        return f"{self.unit} {self.text}".strip()


def _valid_ip(v):
    m = re.match(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})(?::(\d{1,5}))?$", v)
    return bool(m) and all(int(g) <= 255 for g in m.groups()[:4]) and (m.group(5) is None or int(m.group(5)) <= 65535)


def parse_csv_ip(path):
    """CSV fuer ModbusIP-->ModbusIP. Gibt (datenpunkte, fehlerliste) zurück."""
    errors, dps = [], []
    lines = _read_text(path).splitlines()
    if not lines:
        return [], ["Die CSV-Datei ist leer."]
    delim = ";" if lines[0].count(";") >= lines[0].count(",") else ","
    rows = list(csv.reader(lines, delimiter=delim))
    header = [COLS.get(h.strip().lower(), h.strip().lower()) for h in rows[0]]
    need = ["description", "ip", "slave", "regtype", "address"]
    missing = [c for c in need if c not in header]
    if missing:
        return [], [f"Pflichtspalte(n) fehlen: {', '.join(missing)}  (gefunden: {', '.join(header)})"]

    last_unit = ""
    for n, row in enumerate(rows[1:], start=2):
        if not any(c.strip() for c in row) or row[0].lstrip().startswith("#"):
            continue
        r = {h: (row[i].strip() if i < len(row) else "") for i, h in enumerate(header)}
        err = lambda m: errors.append(f"Zeile {n}: {m}")
        if r.get("unitname"):
            last_unit = r["unitname"]
        if not r["description"]:
            err("Description ist leer"); continue
        if not _valid_ip(r["ip"]):
            err(f"IP '{r['ip']}' ungültig (z.B. 192.168.0.1 oder 192.168.0.1:502)"); continue
        try:
            slave = int(r["slave"]); assert 0 <= slave <= 255
        except Exception:
            err(f"Slave '{r['slave']}' ungültig (0..255)"); continue
        reg = r["regtype"].lower()
        if reg not in IP_REGS:
            err(f"Register '{r['regtype']}' ungültig (coil, holding, input oder status)"); continue
        if not r["address"].isdigit():
            err(f"Address '{r['address']}' ungültig (Zahl erwartet)"); continue
        addr = int(r["address"])
        spec = r.get("format") or ("BIT" if reg in ("coil", "status") else "UINT16")
        fmt, e = check_tcp_format(spec, reg)
        if e:
            err(f"Format: {e}"); continue
        acc = r.get("access", "").lower()
        if acc not in ("", "r", "ro", "0", "rw", "w", "1", "yes"):
            err(f"Access '{acc}' ungültig (r oder rw)"); continue
        rw = (acc in ("rw", "w", "1", "yes")) if acc else reg in ("holding", "coil")

        try:
            tslave = int(r.get("tcp_slave") or slave); assert 0 <= tslave <= 255
            taddr = int(r.get("tcp_address") or addr)
        except Exception:
            err("TCP_Slave/TCP_Address ungueltig"); continue
        treg = (r.get("tcp_regtype") or reg).lower()
        if treg not in IP_REGS:
            err(f"TCP_Register '{r['tcp_regtype']}' ungültig (coil, holding, input oder status)"); continue
        tfmt, e = check_tcp_format(r.get("tcp_format") or fmt, treg)
        if e:
            err(f"TCP_Format: {e}"); continue
        dps.append(IPDP(n, last_unit, r["description"], r["ip"], slave, reg, addr, fmt, rw,
                        tslave, treg, taddr, tfmt))

    # Doppelte bzw. überlappende Register (Formate > 16 Bit belegen Folgeregister), je Seite
    for side, label in (("c", "Client-Seite (Remote-IP)"), ("s", "Server-Seite (0.0.0.0)")):
        occ = {}
        for d in dps:
            ip, sl, rg, ad, fm = ((d.ip, d.slave, d.reg, d.addr, d.fmt) if side == "c"
                                  else ("0.0.0.0", d.tslave, d.treg, d.taddr, d.tfmt))
            base = fm.split()[0]
            width = 1 if rg in ("coil", "status") else TCP_WIDTH[base]
            for off in range(width):
                k = (ip, sl, rg, ad + off)
                if k in occ:
                    ol, ob = occ[k]
                    errors.append(f"Zeile {d.line}: {rg} {ad + off} (IP {ip}, Slave {sl}) ist auf der {label} "
                                  f"schon durch Zeile {ol} belegt ({ob})")
                    break
                occ[k] = (d.line, base)
    if not dps and not errors:
        errors.append("Keine Datenpunkte gefunden.")
    return dps, errors


def gen_ip_mbtcp(dps, source):
    """mbtcp1.txt: zuerst alle Remote-Einträge (IP des Geräts), dann alle lokalen (0.0.0.0)."""
    L = box_header(source)
    for server in (False, True):
        for d in dps:
            if server:
                ip, sl, rg, ad, fm = MBTCP_IP, d.tslave, d.treg, d.taddr, d.tfmt
            else:
                ip, sl, rg, ad, fm = d.ip, d.slave, d.reg, d.addr, d.fmt
            letter = "S" if rg in ("coil", "status") else "Y"
            L += [f"[{letter} {ip} {sl} {rg.capitalize()} {ad}]", "  query = pe", f"  name = {d.name}",
                  f"  format = {fm}", "  writecache = yes", ""]
    return L


def gen_ip_dispatch(dps, source):
    L = box_header(source)
    for d in dps:
        c = f"{MBTCP_CH} {MBTCP_KEY} {d.ip} {d.slave} {d.reg.capitalize()} {d.addr}"
        s_ = f"{MBTCP_CH} {MBTCP_KEY} {MBTCP_IP} {d.tslave} {d.treg.capitalize()} {d.taddr}"
        L.append(f"# {d.name}")
        if d.rw:                                  # Schreibrichtung lokal -> Remote zuerst 
            L += [f"[{s_}]", f"  target = {c}"]
        L += [f"[{c}]", f"  target = {s_}", ""]
    return L


def _ascii(s):
    for a, b in {"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue",
                 "ß": "ss", "°": "deg", "µ": "u"}.items():
        s = s.replace(a, b)
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def box_header(source):
    now = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    bar = "# " + "=" * 69 + " #"
    sep = "# " + "-" * 69 + " #"
    row = lambda t: f"# {t:<69} #"
    return [bar, row(f"Erzeugt: {now}"), sep, row(f"User   : {getpass.getuser()}"),
            row(f"Host   : {socket.gethostname()}"), row(f"Datei  : {source}"), bar, "", ""]


def tcp_header():
    now = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    return [f"# Automatische Erzeugung, {getpass.getuser()}@{socket.gethostname()}, {now}", ""]


def gen_modmster(dps, source):
    L = box_header(source)
    for d in dps:
        if d.mtype == "coil":
            letter = "S" if d.rw else "M"
        elif is_integer_fmt(d.fmt):
            letter = "S" if d.rw else "M"
        else:
            letter = "Y" if d.rw else "X"
        L += [f"[{letter} {d.slave} {d.mtype} {d.addr}]", f"  name = {d.name}", "  query = pe"]
        if d.mtype == "holding":
            L.append(f"  format = {d.fmt}")
        if d.rw:
            L.append("  writecache = yes")
        L.append("")
    return L


def gen_bac(dps, source):
    L = box_header(source) + ["[M failure]", "  name = Failure BACnet", "  query = pe", ""]
    for d in dps:
        binary = d.btype in ("BI", "BV")
        L += [f"[{'S' if binary else 'Y'} local.{d.btype} {d.inst}]",
              f"  name = {d.name}", "  query = pe", "  writecache = yes",
              f"  bac_description = {d.text}"]
        if binary:
            L += [f"  bac_inactive_text = {d.inactive}", f"  bac_active_text = {d.active}",
                  "  bac_polarity = 0"]
        else:
            L += [f"  bac_resolution = {d.resolution}||WP", "  bac_cov_increment = 0||WP",
                  f"  bac_units = {d.unit_code}"]
        if d.btype in ("BV", "AV"):
            L.append("  bac_relinquish_default = 0 -V")
        L.append("")
    return L


def gen_mbtcp(dps):
    L = tcp_header()
    last = None
    for d in dps:
        key = (d.device, d.tcp_slave)
        if key != last:                       # Kommunikationsstatus je Gerät (wie im Beispiel)
            L += [f"[S {MBTCP_IP} {d.tcp_slave} status 0]", "  query = pe",
                  f"  name = {(d.device + ' ').lstrip()}Kommunikation Modbus",
                  "  format = BIT", "  writecache = yes", ""]
            last = key
        letter = "S" if (d.mtype == "coil" or is_integer_fmt(d.tcp_fmt)) else "Y"
        L += [f"[{letter} {MBTCP_IP} {d.tcp_slave} {d.mtype} {d.tcp_addr}]",
              "  query = pe", f"  name = {d.name}", f"  format = {d.tcp_fmt}", "  writecache = yes", ""]
    return L


def gen_dispatch(dps, mode, source):
    L = box_header(source)
    for d in dps:
        src = f"{MOD_CH} mod {d.slave} {d.mtype} {d.addr}"
        if mode == MODES[1]:
            dst = f"{BAC_CH} bac local.{d.btype} {d.inst}"
        else:
            dst = f"{MBTCP_CH} {MBTCP_KEY} {MBTCP_IP} {d.tcp_slave} {d.mtype} {d.tcp_addr}"
        L += [f"# {d.name}", f"[{src}]", f"  target = {dst}"]
        if d.rw:
            L += [f"[{dst}]", f"  target = {src}"]
        L.append("")
    return L


def _write(path, lines):
    data = "\r\n".join(_ascii(l) for l in lines) + "\r\n"
    Path(path).write_bytes(data.encode("ascii"))


def generate(csv_path, mode, out_dir):
    """Liest CSV und schreibt die Dateien. Rückgabe: (geschriebene Dateien, Fehlerliste)."""
    if mode == MODES[2]:
        dps, errors = parse_csv_ip(csv_path)
        if errors:
            return [], errors
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        src = Path(csv_path).name
        files = {"dispatch.txt": gen_ip_dispatch(dps, src),
                 "mbtcp1.txt": gen_ip_mbtcp(dps, src)}
        for name, lines in files.items():
            _write(out / name, lines)
        return [out / n for n in files], []
    dps, errors = parse_csv(csv_path, mode)
    if errors:
        return [], errors
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    src = Path(csv_path).name
    files = {"dispatch.txt": gen_dispatch(dps, mode, src), "modmster1.txt": gen_modmster(dps, src)}
    if mode == MODES[1]:
        files["bac1.txt"] = gen_bac(dps, src)
    else:
        files["mbtcp1.txt"] = gen_mbtcp(dps)
    for name, lines in files.items():
        _write(out / name, lines)
    return [out / n for n in files], []


# --------------------------------------------------------------------------
# GUI
# --------------------------------------------------------------------------
def base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def resource_path(name):
    """Pfad zu einer mitgelieferten Datei (funktioniert als .py und als PyInstaller-.exe)."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / name


ICON_FILE = "MBS.ico"


def run_gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    try:                                   # Icon in Titelleiste/Taskleiste (auch für Meldungsfenster)
        root.iconbitmap(default=str(resource_path(ICON_FILE)))
    except tk.TclError:
        pass                               # Icon fehlt oder Plattform unterstützt .ico nicht
    root.title("Konfigurations-Generator für MBS Gateway")
    root.resizable(False, False)
    frm = ttk.Frame(root, padding=16)
    frm.grid()

    ttk.Label(frm, text="Projektname:").grid(row=0, column=0, sticky="w")
    name_var = tk.StringVar()
    entry = ttk.Entry(frm, textvariable=name_var, width=38)
    entry.grid(row=1, column=0, pady=(2, 12))

    ttk.Label(frm, text="Protokoll: Client ==> Server").grid(row=2, column=0, sticky="w")
    mode_var = tk.StringVar(value=MODES[0])
    combo = ttk.Combobox(frm, textvariable=mode_var, values=MODES, state="readonly", width=35)
    combo.grid(row=3, column=0, pady=(2, 14))

    def on_ok(_event=None):
        name = name_var.get().strip()
        if not name or re.search(r'[<>:"/\\|?*]', name) or name in (".", ".."):
            messagebox.showerror("Projektname", "Bitte einen gültigen Projektnamen eingeben\n"
                                 "(keine Zeichen wie  < > : \" / \\ | ? * ).", parent=root)
            return
        mode = mode_var.get()
        root.withdraw()
        # Fenster 2: Dateiauswahl (Doppelklick auf Datei oder Öffnen/OK)
        path = filedialog.askopenfilename(
            parent=root, title=f"Datenpunkte (CSV) wählen - {mode}",
            filetypes=[("CSV-Dateien", "*.csv"), ("Alle Dateien", "*.*")])
        if not path:
            root.deiconify()
            return
        out_dir = base_dir() / name
        if out_dir.exists() and any((out_dir / f).exists() for f in
                                    ("dispatch.txt", "modmster1.txt", "bac1.txt", "mbtcp1.txt")):
            if not messagebox.askyesno("Ordner vorhanden",
                                       f"Im Ordner\n{out_dir}\nexistieren bereits Konfigurationsdateien.\n"
                                       "Überschreiben?", parent=root):
                root.deiconify()
                return
        try:
            files, errors = generate(path, mode, out_dir)
        except Exception as exc:                                  # noqa: BLE001
            messagebox.showerror("Fehler", f"{type(exc).__name__}: {exc}", parent=root)
            root.deiconify()
            return
        if errors:
            shown = "\n".join(errors[:25]) + (f"\n... und {len(errors) - 25} weitere" if len(errors) > 25 else "")
            messagebox.showerror("CSV fehlerhaft - nichts erzeugt", shown, parent=root)
            root.deiconify()
            return
        messagebox.showinfo("Fertig", f"Ordner: {out_dir}\n\n" + "\n".join(f.name for f in files), parent=root)
        root.destroy()

    ttk.Button(frm, text="OK", command=on_ok, width=12).grid(row=4, column=0, sticky="e")
    root.bind("<Return>", on_ok)
    entry.focus()
    root.update_idletasks()
    root.geometry(f"{max(root.winfo_reqwidth(), 520)}x{root.winfo_reqheight()}")
    root.mainloop()


if __name__ == "__main__":
    # Ohne GUI:  python config4mbs.py --cli <bacnet|tcp|ip> <datei.csv> <ausgabeordner>
    if len(sys.argv) == 5 and sys.argv[1] == "--cli":
        m = {"bacnet": MODES[1], "ip": MODES[2]}.get(sys.argv[2], MODES[0])
        f, e = generate(sys.argv[3], m, sys.argv[4])
        print("\n".join(e) if e else "\n".join(map(str, f)))
        sys.exit(1 if e else 0)
    run_gui()
