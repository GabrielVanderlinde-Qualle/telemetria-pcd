#!/usr/bin/env python3
"""
=============================================================================
 marcar_estacoes_pendentes_v2.py

 LÓGICA CORRIGIDA:
   Antes buscávamos por IP = 0.0.0.0 — mas o script de inserção já
   atualizou todos os hosts com IPs reais.

   A regra correta é: estação não instalada fisicamente = sem coordenadas
   no inventário do Zabbix (location_lat = "" ou "0.0").

   O script:
   1. Busca todos os hosts dos grupos PCDs com inventário
   2. Filtra os que têm latitude vazia ou = "0.0" (não instalados)
   3. Adiciona a tag  status=pendente  nesses hosts
   4. O Grafana ignora hosts com essa tag nas queries

 REVERSÍVEL:
   Mude MODO = "remover" para desfazer.
   Mude MODO = "listar" para só ver o que seria afetado.
=============================================================================
"""

import requests

# ==============================================================================
# CONFIGURAÇÕES
# ==============================================================================
ZABBIX_URL   = "http://10.255.255.4:8888/api_jsonrpc.php"
ZABBIX_TOKEN = "6d0a0ae04ef2e4130189c637ad3b7d552f7511b198a3a1e3f7ee203210b00630"

GRUPOS_PCDS = [
    "BR.RS._.DCRS - PCDs",
    "BR.SC._.DCSC - PCDs",
]

TAG_NOME  = "status"
TAG_VALOR = "pendente"

# "listar"    → só mostra, sem alterar nada  ← comece aqui
# "adicionar" → marca os hosts sem coordenadas
# "remover"   → desfaz tudo
MODO = "listar"

# ==============================================================================
# CLIENTE ZABBIX API
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
        """Busca todos os hosts dos grupos com inventário e tags."""
        return self._call("host.get", {
            "output":          ["hostid", "host", "name", "status"],
            "groupids":        group_ids,
            "selectTags":      ["tag", "value"],
            "selectInventory": ["location_lat", "location_lon"],
        })

    def update_tags(self, hostid, new_tags):
        return self._call("host.update", {
            "hostid": hostid,
            "tags":   new_tags,
        })


def is_sem_coordenada(inventory):
    """Retorna True se o host não tem coordenadas válidas."""
    if not inventory:
        return True
    lat = str(inventory.get("location_lat", "")).strip()
    lon = str(inventory.get("location_lon", "")).strip()
    # Sem coordenada = vazio, "0", "0.0", ou "0.00..."
    lat_invalida = not lat or float(lat) == 0.0 if lat else True
    lon_invalida = not lon or float(lon) == 0.0 if lon else True
    return lat_invalida or lon_invalida


# ==============================================================================
# MAIN
# ==============================================================================
def main():
    print("=" * 65)
    print(f" Estações Pendentes v2 (por coordenada) — modo: {MODO.upper()}")
    print("=" * 65)

    zapi = ZabbixAPI(ZABBIX_URL, ZABBIX_TOKEN)

    # 1. Grupos
    print(f"\n[1/3] Buscando grupos...")
    grupos = zapi.get_group_ids(GRUPOS_PCDS)
    if not grupos:
        print("✗ Nenhum grupo encontrado.")
        return
    group_ids = [g["groupid"] for g in grupos]
    for g in grupos:
        print(f"      ✓ {g['name']}  (id={g['groupid']})")

    # 2. Todos os hosts
    print(f"\n[2/3] Buscando todos os hosts dos grupos...")
    todos = zapi.get_all_hosts(group_ids)
    print(f"      Total de hosts: {len(todos)}")

    # Filtra os sem coordenada
    sem_coord = [h for h in todos if is_sem_coordenada(h.get("inventory"))]
    com_coord = [h for h in todos if not is_sem_coordenada(h.get("inventory"))]

    print(f"      Com coordenadas (instalados):     {len(com_coord)}")
    print(f"      Sem coordenadas (não instalados): {len(sem_coord)}")

    if not sem_coord:
        print("\n      Todos os hosts têm coordenadas. Nada a fazer.")
        return

    # 3. Aplica ação
    print(f"\n[3/3] Executando modo '{MODO}'...")
    adicionados = removidos = ignorados = 0

    for h in sem_coord:
        hostid        = h["hostid"]
        nome          = h["name"]
        existing_tags = h.get("tags", [])
        tem_tag       = any(
            t["tag"] == TAG_NOME and t["value"] == TAG_VALOR
            for t in existing_tags
        )

        if MODO == "listar":
            status = "JÁ MARCADO" if tem_tag else "SERIA MARCADO"
            lat = h.get("inventory", {}).get("location_lat", "vazio")
            print(f"      [{status}] {nome}  (lat={lat})")
            ignorados += 1

        elif MODO == "adicionar":
            if tem_tag:
                print(f"      [JÁ TEM TAG] {nome}")
                ignorados += 1
            else:
                new_tags = existing_tags + [{"tag": TAG_NOME, "value": TAG_VALOR}]
                zapi.update_tags(hostid, new_tags)
                print(f"      [MARCADO] {nome}")
                adicionados += 1

        elif MODO == "remover":
            if not tem_tag:
                print(f"      [SEM TAG]  {nome}")
                ignorados += 1
            else:
                new_tags = [
                    t for t in existing_tags
                    if not (t["tag"] == TAG_NOME and t["value"] == TAG_VALOR)
                ]
                zapi.update_tags(hostid, new_tags)
                print(f"      [REMOVIDO] {nome}")
                removidos += 1

    # Resumo
    print("\n" + "=" * 65)
    if MODO == "listar":
        print(f" {len(sem_coord)} hosts sem coordenadas encontrados.")
        print(f" Mude MODO = 'adicionar' para aplicar as tags.")
    elif MODO == "adicionar":
        print(f" ✓ Tags adicionadas: {adicionados}")
        print(f" ⊘ Já tinham a tag:  {ignorados}")
        print()
        print(" Próximo passo: use o dashboard_v4.json no Grafana.")
        print(" Esses hosts serão ignorados em todas as queries.")
    elif MODO == "remover":
        print(f" ✓ Tags removidas:   {removidos}")
        print(f" ⊘ Não tinham a tag: {ignorados}")
    print("=" * 65)


if __name__ == "__main__":
    main()