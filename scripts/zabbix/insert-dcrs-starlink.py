#!/usr/bin/env python3
"""
Script para criar hosts no Zabbix via API (Focado na Starlink)
Lê os dados de um arquivo CSV e envia para o Zabbix usando Template da antena.
"""
import json
import requests
import csv
import os


# ==============================================================================
# CLASSE DE CONEXÃO COM O ZABBIX
# ==============================================================================
class ZabbixAPI:
    def __init__(self, url, username=None, password=None, api_token=None):
        self.url = url
        self.username = username
        self.password = password
        self.api_token = api_token
        self.auth_token = None
        self.request_id = 1

    def _call(self, method, params):
        """Mensageiro para a API do Zabbix (Formato JSON)"""
        payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": self.request_id}
        headers = {"Content-Type": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        elif self.auth_token:
            payload["auth"] = self.auth_token

        self.request_id += 1
        response = requests.post(self.url, json=payload, headers=headers)
        result = response.json()
        if "error" in result: raise Exception(f"Erro na API: {result['error']}")
        return result.get("result")

    def login(self):
        """Login seguro no Zabbix"""
        if self.api_token: return self.api_token
        result = self._call("user.login", {"username": self.username, "password": self.password})
        self.auth_token = result
        return result

    def get_hostgroup_ids(self, group_names):
        """Pega o ID do Grupo de Hosts da Starlink"""
        result = self._call("hostgroup.get", {"output": ["groupid", "name"], "filter": {"name": group_names}})
        return {g["name"]: g["groupid"] for g in result}

    def get_template_ids(self, template_names):
        """Pega o ID do Template Starlink Dishy"""
        result = self._call("template.get", {"output": ["templateid", "name"], "filter": {"name": template_names}})
        return {t["name"]: t["templateid"] for t in result}

    def check_host_exists(self, hostname):
        """Verifica se a Starlink já existe"""
        result = self._call("host.get", {"output": ["hostid", "host"], "filter": {"host": [hostname]}})
        return result[0]["hostid"] if result else None

    def update_host(self, hostid, visible_name, ip_address, group_ids, template_ids, snmp_community="public",
                    location_lat=None, location_lon=None):
        """Atualiza a Starlink no Zabbix"""
        params = {
            "hostid": hostid, "name": visible_name,
            "groups": [{"groupid": gid} for gid in group_ids],
            "templates": [{"templateid": tid} for tid in template_ids],
            # Starlink também costuma usar interface SNMP
            "interfaces": [{
                "type": 2, "main": 1, "useip": 1, "ip": ip_address, "dns": "", "port": "161",
                "details": {"version": 2, "community": snmp_community}
            }],
            "macros": [{"macro": "{$SNMP_COMMUNITY}", "value": snmp_community}]
        }
        if location_lat and location_lon:
            params["inventory"] = {"location_lat": str(location_lat), "location_lon": str(location_lon),
                                   "location": f"{location_lat}, {location_lon}"}
        return self._call("host.update", params)

    def create_host(self, hostname, visible_name, ip_address, group_ids, template_ids, snmp_community="public",
                    location_lat=None, location_lon=None):
        """Cria uma NOVA Starlink no Zabbix"""
        params = {
            "host": hostname, "name": visible_name,
            "groups": [{"groupid": gid} for gid in group_ids],
            "templates": [{"templateid": tid} for tid in template_ids],
            "interfaces": [{
                "type": 2, "main": 1, "useip": 1, "ip": ip_address, "dns": "", "port": "161",
                "details": {"version": 2, "community": snmp_community}
            }],
            "macros": [{"macro": "{$SNMP_COMMUNITY}", "value": snmp_community}],
            "inventory_mode": 0
        }
        if location_lat and location_lon:
            params["inventory"] = {"location_lat": str(location_lat), "location_lon": str(location_lon),
                                   "location": f"{location_lat}, {location_lon}"}
        return self._call("host.create", params)

    def create_or_update_hosts_batch(self, hosts_data, group_ids, template_ids, update_existing=False):
        """Envia todas as Starlinks da lista para o Zabbix"""
        created, updated, skipped, errors, with_location, without_location = 0, 0, 0, 0, 0, 0

        for host_data in hosts_data:
            try:
                hostname = host_data["hostname"]
                hostid = self.check_host_exists(hostname)

                location_lat = host_data.get("location_lat")
                location_lon = host_data.get("location_lon")

                if location_lat and location_lon:
                    with_location += 1
                else:
                    without_location += 1

                if hostid:  # Atualiza se já tem
                    if update_existing:
                        self.update_host(
                            hostid=hostid, visible_name=host_data["visible_name"],
                            ip_address=host_data["ip"], group_ids=group_ids,
                            template_ids=template_ids, snmp_community=host_data.get("community", "public"),
                            location_lat=location_lat, location_lon=location_lon
                        )
                        updated += 1
                    else:
                        skipped += 1
                else:  # Cria se for nova
                    self.create_host(
                        hostname=hostname, visible_name=host_data["visible_name"],
                        ip_address=host_data["ip"], group_ids=group_ids,
                        template_ids=template_ids, snmp_community=host_data.get("community", "public"),
                        location_lat=location_lat, location_lon=location_lon
                    )
                    created += 1
            except Exception as e:
                print(f"✗ Erro ao processar {host_data['hostname']}: {e}");
                errors += 1

        return created, updated, skipped, errors, with_location, without_location


# ==============================================================================
# FUNÇÃO QUE LÊ O CSV (A Planilha do Banco de Dados)
# ==============================================================================
def load_rs_hosts_from_csv(csv_filepath, device_type="starlink"):
    """Puxa os dados da planilha para a memória do script"""
    hosts = []
    if not os.path.exists(csv_filepath): raise FileNotFoundError(f"Arquivo CSV não encontrado: {csv_filepath}")

    with open(csv_filepath, mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)

        for row in reader:
            id_estacao = row['id_estacao']
            ip = row['ip_mikrotik']
            nome_cidade = row['nome'].replace("PCD ", "").strip()
            codigo = row['codigo_estacao_interno']
            lat, lon = row['latitude'], row['longitude']

            if not codigo: codigo = f"DCRS-{int(id_estacao):05d}"

            # O Final ".STARLINK" garante que a Starlink não apague os outros equipamentos
            hostname = f"BR.RS._.DCRS.{codigo}.STARLINK"
            visible_name = f"{codigo} - Starlink Dishy ({nome_cidade})"

            hosts.append({
                "hostname": hostname, "visible_name": visible_name, "ip": ip, "community": "public",
                "location_lat": lat if lat and lat != "0.0" else None,
                "location_lon": lon if lon and lon != "0.0" else None
            })
    return hosts


# ==============================================================================
# FUNÇÃO PRINCIPAL
# ==============================================================================
def main():
    # CONFIGURAÇÕES BÁSICAS
    ZABBIX_URL = "http://10.255.255.4:8888/api_jsonrpc.php"
    ZABBIX_API_TOKEN = "6d0a0ae04ef2e4130189c637ad3b7d552f7511b198a3a1e3f7ee203210b00630"  # <--- INSIRA O SEU TOKEN
    UPDATE_EXISTING = True  # Atualizar o que já existir
    CSV_FILE = "consulta_estacoes_RS.csv"

    print("=" * 60)
    print("Script de Criação de STARLINK DCRS via API lendo do CSV")
    print("=" * 60)

    try:
        zapi = ZabbixAPI(ZABBIX_URL, api_token=ZABBIX_API_TOKEN)
        zapi.login()
    except Exception as e:
        print(f"✗ Erro: {e}"); return

    # GRUPO E TEMPLATE DA STARLINK
    group_names = ["BR.RS._.DCRS - Starlinks"]
    try:
        group_ids = [zapi.get_hostgroup_ids(group_names)[n] for n in group_names]
    except Exception as e:
        print(f"✗ Erro grupos: {e}"); return

    template_names = ["Starlink Dishy"]
    try:
        template_ids = [zapi.get_template_ids(template_names)[n] for n in template_names]
    except Exception as e:
        print(f"✗ Erro templates: {e}"); return

    print(f"\nLendo dados do CSV {CSV_FILE}...")
    hosts_data = load_rs_hosts_from_csv(CSV_FILE, "starlink")
    print(f"✓ {len(hosts_data)} Starlinks preparadas.")

    print("\nIniciando processamento no Zabbix...")
    created, updated, skipped, errors, with_loc, without_loc = zapi.create_or_update_hosts_batch(
        hosts_data, group_ids, template_ids, update_existing=UPDATE_EXISTING
    )

    print("\n" + "=" * 60)
    print(f"✓ Starlinks criadas/atualizadas: {created}/{updated} | ⊘ Puladas: {skipped} | ✗ Erros: {errors}")
    print("=" * 60)


if __name__ == "__main__":
    main()