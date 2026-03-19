#!/usr/bin/env python3
import requests
import csv
import os


class ZabbixAPI:
    def __init__(self, url, api_token=None):
        self.url = url
        self.api_token = api_token
        self.request_id = 1

    def _call(self, method, params):
        payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": self.request_id}
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_token}"}
        self.request_id += 1
        response = requests.post(self.url, json=payload, headers=headers)
        result = response.json()
        if "error" in result: raise Exception(f"Erro na API: {result['error']}")
        return result.get("result")

    def login(self):
        return self.api_token

    def get_hostgroup_ids(self, group_names):
        result = self._call("hostgroup.get", {"output": ["groupid", "name"], "filter": {"name": group_names}})
        return {g["name"]: g["groupid"] for g in result}

    def get_template_ids(self, template_names):
        result = self._call("template.get", {"output": ["templateid", "name"], "filter": {"name": template_names}})
        return {t["name"]: t["templateid"] for t in result}

    def check_host_exists(self, hostname):
        """Busca o host e também o ID da interface para não quebrar o Zabbix na hora de atualizar"""
        result = self._call("host.get", {
            "output": ["hostid"],
            "selectInterfaces": ["interfaceid", "type"],
            "filter": {"host": [hostname]}
        })
        if result:
            hostid = result[0]["hostid"]
            iface_id = None
            # Procura a interface SNMP (Type 2)
            for iface in result[0].get("interfaces", []):
                if str(iface["type"]) == "2":
                    iface_id = iface["interfaceid"]
                    break
            return hostid, iface_id
        return None, None

    def create_or_update_host(self, hostid, iface_id, hostname, visible_name, ip_address, group_ids, template_ids,
                              snmp_community="public", location_lat=None, location_lon=None):
        # Desativa o host (status 1) se o IP for 0.0.0.0, senão Ativa (status 0)
        status = 1 if ip_address == "0.0.0.0" else 0

        # Monta a interface. Se já existe, passa o ID para o Zabbix não reclamar!
        interface_payload = {
            "type": 2, "main": 1, "useip": 1, "ip": ip_address, "dns": "", "port": "161",
            "details": {"version": 2, "community": snmp_community}
        }
        if iface_id:
            interface_payload["interfaceid"] = iface_id

        params = {
            "name": visible_name,
            "status": status,
            "groups": [{"groupid": gid} for gid in group_ids],
            "templates": [{"templateid": tid} for tid in template_ids],
            "interfaces": [interface_payload],
            "macros": [{"macro": "{$SNMP_COMMUNITY}", "value": snmp_community}],
            "inventory_mode": 0
        }

        if location_lat and location_lon:
            params["inventory"] = {"location_lat": str(location_lat), "location_lon": str(location_lon)}

        if hostid:
            params["hostid"] = hostid
            return self._call("host.update", params)
        else:
            params["host"] = hostname
            return self._call("host.create", params)


def load_rs_hosts_from_csv(csv_filepath):
    hosts = []
    if not os.path.exists(csv_filepath): raise FileNotFoundError("CSV não encontrado.")
    with open(csv_filepath, mode='r', encoding='utf-8') as file:
        for row in csv.DictReader(file):
            codigo = row['codigo_estacao_interno']

            # Filtra apenas o Rio Grande do Sul
            if not codigo or not codigo.startswith("DCRS"):
                continue

            id_estacao, ip = row['id_estacao'], row['ip_mikrotik']
            nome_cidade = row['nome'].replace("PCD ", "").replace(" (H)", "").strip()

            hostname = f"BR.RS._.DCRS.{codigo}.MIKROTIK"
            visible_name = f"{codigo} - {nome_cidade}"

            lat, lon = row['latitude'], row['longitude']
            hosts.append({
                "hostname": hostname, "visible_name": visible_name, "ip": ip,
                "location_lat": lat if lat and lat != "0.0" else None,
                "location_lon": lon if lon and lon != "0.0" else None
            })
    return hosts


def main():
    ZABBIX_URL = "http://10.255.255.4:8888/api_jsonrpc.php"
    ZABBIX_API_TOKEN = "6d0a0ae04ef2e4130189c637ad3b7d552f7511b198a3a1e3f7ee203210b00630"
    CSV_FILE = r"C:\Users\gabriel\Documents\Pessoal\Projetos\Profissional\Telemetria\BACK\scripts-zabbix-py\info_estacoes_rs_sc.csv"

    print("Iniciando MIKROTIK DCRS (Nomes simplificados + Filtro 0.0.0.0)...")
    zapi = ZabbixAPI(ZABBIX_URL, api_token=ZABBIX_API_TOKEN)

    group_ids = [zapi.get_hostgroup_ids(["BR.RS._.DCRS - PCDs"])["BR.RS._.DCRS - PCDs"]]
    template_ids = [zapi.get_template_ids(["Mikrotik by SNMP"])["Mikrotik by SNMP"]]

    hosts_data = load_rs_hosts_from_csv(CSV_FILE)

    for h in hosts_data:
        hostid, iface_id = zapi.check_host_exists(h["hostname"])
        zapi.create_or_update_host(hostid, iface_id, h["hostname"], h["visible_name"], h["ip"], group_ids, template_ids,
                                   "public", h["location_lat"], h["location_lon"])
        print(f"[{'ATUALIZADO' if hostid else 'CRIADO'}] {h['visible_name']} (IP: {h['ip']})")


if __name__ == "__main__":
    main()