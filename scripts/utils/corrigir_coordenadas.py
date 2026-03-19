#!/usr/bin/env python3
"""
=============================================================================
 corrigir_coordenadas_zabbix.py

 PROBLEMA:
   Algumas estações no Zabbix têm Latitude e Longitude armazenadas de forma
   INVERTIDA. Isso faz com que apareçam no Oceano Atlântico, no Uruguai, ou
   em SC quando deveriam estar no RS (e vice-versa).

   CAUSA: O CSV original tinha as colunas "longitude" e "latitude" com os
   VALORES trocados em algumas entradas. O script de inserção leu por nome
   de coluna, armazenando o valor errado para cada campo.

 O QUE ESTE SCRIPT FAZ:
   1. Busca todos os hosts dos grupos PCDs com inventário
   2. Para cada host, verifica se lat/lon estão dentro das faixas válidas
      para RS e SC (aproximadamente -34 a -25 para latitude, -58 a -47 lon)
   3. Se lat está na faixa de longitude válida E lon está na faixa de
      latitude válida → estão INVERTIDOS → corrige no Zabbix
   4. Se estão completamente fora de range → lista para revisão manual

 MODO = "listar" → só mostra, não altera nada (seguro para rodar primeiro)
 MODO = "corrigir" → aplica a correção no Zabbix
=============================================================================
"""

import requests

ZABBIX_URL   = "http://10.255.255.4:8888/api_jsonrpc.php"
ZABBIX_TOKEN = "6d0a0ae04ef2e4130189c637ad3b7d552f7511b198a3a1e3f7ee203210b00630"

GRUPOS_PCDS = [
    "BR.RS._.DCRS - PCDs",
    "BR.SC._.DCSC - PCDs",
]

# Faixas geográficas válidas para RS + SC combinados
# Latitude:  de -34.5 (extremo sul RS) a -25.9 (extremo norte SC)
# Longitude: de -58.0 (extremo oeste RS) a -47.5 (extremo leste SC)
LAT_MIN, LAT_MAX = -34.5, -25.9
LON_MIN, LON_MAX = -58.0, -47.5

# Inicia em "listar" — rode assim primeiro para ver o que seria corrigido
# Depois mude para "corrigir" para aplicar as correções
MODO = "listar"


# ==============================================================================
class ZabbixAPI:
    def __init__(self, url, token):
        self.url    = url
        self.token  = token
        self.req_id = 1

    def _call(self, method, params):
        payload = {
            "jsonrpc": "2.0",
            "method":  method,
            "params":  params,
            "id":      self.req_id,
        }
        headers = {
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {self.token}",
        }
        self.req_id += 1
        r = requests.post(self.url, json=payload, headers=headers, timeout=30)
        result = r.json()
        if "error" in result:
            raise Exception(f"Zabbix API erro [{method}]: {result['error']}")
        return result["result"]

    def get_group_ids(self, names):
        return self._call("hostgroup.get", {
            "output": ["groupid", "name"],
            "filter": {"name": names},
        })

    def get_all_hosts(self, group_ids):
        return self._call("host.get", {
            "output":          ["hostid", "host", "name"],
            "groupids":        group_ids,
            "selectInventory": ["location_lat", "location_lon", "location"],
        })

    def update_inventory(self, hostid, new_lat, new_lon):
        return self._call("host.update", {
            "hostid": hostid,
            "inventory": {
                "location_lat": str(new_lat),
                "location_lon": str(new_lon),
                "location": f"{new_lat}, {new_lon}",
            }
        })


# ==============================================================================
def detectar_problema(lat_str, lon_str):
    """
    Analisa as coordenadas e retorna:
    - ("ok",       lat, lon)  → dentro das faixas válidas
    - ("invertido", lat, lon) → lat e lon estão trocados (detectável)
    - ("zero",      0,  0)    → sem coordenadas (lat ou lon = 0)
    - ("invalido",  lat, lon) → completamente fora de range, revisar manualmente
    """
    if not lat_str or not lon_str:
        return "zero", 0.0, 0.0

    try:
        lat = float(lat_str)
        lon = float(lon_str)
    except ValueError:
        return "invalido", None, None

    # Sem coordenadas
    if lat == 0.0 or lon == 0.0:
        return "zero", lat, lon

    # Já corretos
    if LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX:
        return "ok", lat, lon

    # Detecta inversão:
    # Se o que está em "lat" cabe na faixa de longitude E
    # o que está em "lon" cabe na faixa de latitude → INVERTIDO
    lat_parece_lon = LON_MIN <= lat <= LON_MAX
    lon_parece_lat = LAT_MIN <= lon <= LAT_MAX

    if lat_parece_lon and lon_parece_lat:
        return "invertido", lat, lon

    # Fora de range mas não claramente invertido
    return "invalido", lat, lon


# ==============================================================================
def main():
    print("=" * 65)
    print(f" Correção de Coordenadas Zabbix — modo: {MODO.upper()}")
    print("=" * 65)

    zapi = ZabbixAPI(ZABBIX_URL, ZABBIX_TOKEN)

    # Grupos
    print("\n[1/3] Buscando grupos...")
    grupos = zapi.get_group_ids(GRUPOS_PCDS)
    if not grupos:
        print("✗ Nenhum grupo encontrado.")
        return
    group_ids = [g["groupid"] for g in grupos]
    for g in grupos:
        print(f"      ✓ {g['name']}  (id={g['groupid']})")

    # Hosts
    print("\n[2/3] Buscando todos os hosts com inventário...")
    hosts = zapi.get_all_hosts(group_ids)
    print(f"      Total: {len(hosts)} hosts")

    # Análise
    print("\n[3/3] Analisando coordenadas...\n")

    ok_count       = 0
    zero_count     = 0
    invertido_count = 0
    invalido_count  = 0
    corrigido_count = 0

    invalidos = []

    for h in hosts:
        inv     = h.get("inventory") or {}
        lat_str = inv.get("location_lat", "")
        lon_str = inv.get("location_lon", "")
        nome    = h["name"]
        hostid  = h["hostid"]

        status, lat, lon = detectar_problema(lat_str, lon_str)

        if status == "ok":
            ok_count += 1

        elif status == "zero":
            zero_count += 1
            # Já tratadas pelo script marcar_estacoes_pendentes

        elif status == "invertido":
            invertido_count += 1
            new_lat = lon   # o que estava em lon é a latitude correta
            new_lon = lat   # o que estava em lat é a longitude correta

            if MODO == "listar":
                print(f"  [INVERTIDO] {nome}")
                print(f"             Armazenado: lat={lat:.6f}, lon={lon:.6f}")
                print(f"             Corrigido:  lat={new_lat:.6f}, lon={new_lon:.6f}")
                print()
            elif MODO == "corrigir":
                try:
                    zapi.update_inventory(hostid, round(new_lat, 7), round(new_lon, 7))
                    print(f"  [✓ CORRIGIDO] {nome}: lat {lat:.4f}→{new_lat:.4f}, lon {lon:.4f}→{new_lon:.4f}")
                    corrigido_count += 1
                except Exception as e:
                    print(f"  [✗ ERRO] {nome}: {e}")

        elif status == "invalido":
            invalido_count += 1
            invalidos.append((nome, lat_str, lon_str))

    # Resumo
    print("\n" + "=" * 65)
    print(f" RESUMO:")
    print(f"   ✓ Coordenadas corretas:  {ok_count}")
    print(f"   ⊘ Sem coordenadas (0,0): {zero_count}")
    print(f"   ↔ Invertidas detectadas: {invertido_count}")
    print(f"   ? Inválidas (ver abaixo): {invalido_count}")

    if invalidos:
        print(f"\n   Hosts com coordenadas completamente fora de range")
        print(f"   (precisam de correção manual no Zabbix):")
        for nome, lat, lon in invalidos:
            print(f"     - {nome}: lat={lat}, lon={lon}")

    if MODO == "listar" and invertido_count > 0:
        print(f"\n   → Mude MODO = 'corrigir' para aplicar as {invertido_count} correções.")
    elif MODO == "corrigir":
        print(f"\n   ✓ {corrigido_count} hosts corrigidos no Zabbix.")
        print(f"   Atualize o Grafana (aguarde 1 refresh) para ver as mudanças.")

    print("=" * 65)


if __name__ == "__main__":
    main()