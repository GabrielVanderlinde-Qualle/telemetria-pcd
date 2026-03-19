#!/usr/bin/env python3
import requests

# ================= CONFIGURAÇÕES =================
ZABBIX_URL = "http://10.255.255.4:8888/api_jsonrpc.php"
ZABBIX_TOKEN = "6d0a0ae04ef2e4130189c637ad3b7d552f7511b198a3a1e3f7ee203210b00630"  # <--- COLOQUE SEU TOKEN AQUI
# Vamos vasculhar as estações dos dois estados para garantir!
GRUPOS = ["BR.RS._.DCRS - PCDs", "BR.SC._.DCSC - PCDs"]


# =================================================

def zabbix_api_call(method, params):
    payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
    headers = {'Content-Type': 'application/json-rpc'}
    if ZABBIX_TOKEN:
        headers['Authorization'] = f'Bearer {ZABBIX_TOKEN}'
    response = requests.post(ZABBIX_URL, json=payload, headers=headers)
    return response.json()


def main():
    print("=" * 60)
    print("Sincronizando Inventário -> Itens de Coordenada (RS e SC)")
    print("=" * 60)

    # 1. Pega os IDs dos grupos
    group_res = zabbix_api_call("hostgroup.get", {"filter": {"name": GRUPOS}})
    if "error" in group_res or not group_res.get("result"):
        print("❌ Erro ao buscar os grupos.")
        return
    group_ids = [g["groupid"] for g in group_res["result"]]

    # 2. Pega todos os hosts com inventário e itens
    hosts_res = zabbix_api_call("host.get", {
        "groupids": group_ids,
        "selectInventory": ["location_lat", "location_lon"],
        "selectItems": ["name", "key_"]
    })

    hosts = hosts_res.get("result", [])
    print(f"Lendo {len(hosts)} equipamentos...")

    sucessos = 0

    for host in hosts:
        hostid = host["hostid"]
        hostname = host["name"]
        inv = host.get("inventory") or {}

        lat = inv.get("location_lat")
        lon = inv.get("location_lon")

        # Se não tem coordenada no inventário, ignora
        if not lat or not lon or lat == "0.0" or lon == "0.0":
            continue

        # Verifica se os itens já existem nesse host
        items_existentes = [item["key_"] for item in host.get("items", [])]

        # --- LATITUDE ---
        if "lat.calc" not in items_existentes:
            zabbix_api_call("item.create", {
                "name": "Latitude",
                "key_": "lat.calc",
                "hostid": hostid,
                "type": 15,  # 15 = Calculated
                "value_type": 0,  # Numeric float
                "delay": "1h",  # Atualiza a cada 1h para não pesar
                "params": str(lat)
            })
            print(f"[{hostname}] ✅ Item Latitude criado ({lat})")
            sucessos += 1

        # --- LONGITUDE ---
        if "lon.calc" not in items_existentes:
            zabbix_api_call("item.create", {
                "name": "Longitude",
                "key_": "lon.calc",
                "hostid": hostid,
                "type": 15,
                "value_type": 0,
                "delay": "1h",
                "params": str(lon)
            })
            print(f"[{hostname}] ✅ Item Longitude criado ({lon})")
            sucessos += 1

    print("=" * 60)
    print(f"Finalizado! {sucessos} itens criados para o Grafana ler.")


if __name__ == "__main__":
    main()