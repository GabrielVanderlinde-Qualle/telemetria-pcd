#!/usr/bin/env python3
"""
Script para criar hosts no Zabbix via API (Focado nas Câmeras)
Lê os dados de um arquivo CSV e envia para o Zabbix.
"""
import json
import requests
import csv
import os


# ==============================================================================
# CLASSE DE CONEXÃO COM O ZABBIX (O "Mensageiro")
# ==============================================================================
class ZabbixAPI:
    def __init__(self, url, username=None, password=None, api_token=None):
        self.url = url  # Endereço do Zabbix
        self.username = username
        self.password = password
        self.api_token = api_token  # Token de segurança
        self.auth_token = None
        self.request_id = 1  # Contador de requisições

    def _call(self, method, params):
        """Monta o pacote de dados e envia para a API do Zabbix"""
        payload = {
            "jsonrpc": "2.0",
            "method": method,  # Ex: host.create, host.get
            "params": params,  # As informações (nome, ip, grupo)
            "id": self.request_id
        }
        headers = {"Content-Type": "application/json"}

        # Se tem token, coloca no cabeçalho de segurança
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        elif self.auth_token:
            payload["auth"] = self.auth_token

        self.request_id += 1

        # Envia de fato para o Zabbix
        response = requests.post(self.url, json=payload, headers=headers)
        result = response.json()

        # Se o Zabbix reclamar de algo, o script avisa o erro
        if "error" in result:
            raise Exception(f"Erro na API: {result['error']}")
        return result.get("result")

    def login(self):
        """Avisa o Zabbix quem está tentando mexer no sistema"""
        if self.api_token:
            return self.api_token
        result = self._call("user.login", {"username": self.username, "password": self.password})
        self.auth_token = result
        return result

    def get_hostgroup_ids(self, group_names):
        """O Zabbix usa números (IDs) para os grupos. Essa função descobre qual é o ID do grupo 'BR.RS...'"""
        result = self._call("hostgroup.get", {"output": ["groupid", "name"], "filter": {"name": group_names}})
        return {g["name"]: g["groupid"] for g in result}

    def get_template_ids(self, template_names):
        """Descobre o número (ID) do Template da câmera Hikvision"""
        result = self._call("template.get", {"output": ["templateid", "name"], "filter": {"name": template_names}})
        return {t["name"]: t["templateid"] for t in result}

    def check_host_exists(self, hostname):
        """Pergunta ao Zabbix: 'Você já tem uma câmera com esse nome?'"""
        result = self._call("host.get", {"output": ["hostid", "host"], "filter": {"host": [hostname]}})
        if result:
            return result[0]["hostid"]  # Se existir, devolve o ID dela
        return None  # Se não existir, devolve vazio

    def update_host(self, hostid, visible_name, ip_address, group_ids, template_ids, location_lat=None,
                    location_lon=None):
        """Atualiza a câmera se ela já existir no Zabbix"""
        params = {
            "hostid": hostid,
            "name": visible_name,
            "groups": [{"groupid": gid} for gid in group_ids],
            "templates": [{"templateid": tid} for tid in template_ids],
            "macros": [  # Macros específicas para Câmeras Hikvision
                {"macro": "{$HIKVISION_ISAPI_HOST}", "value": ip_address},
                {"macro": "{$HIKVISION_ISAPI_PORT}", "value": "9080"},
                {"macro": "{$USER}", "value": "admin"},
                {"macro": "{$PASSWORD}", "value": "5enhadaCamera", "type": 1}
            ],
        }
        # Se a câmera tem coordenadas, preenche o Inventário para aparecer no Mapa
        if location_lat is not None and location_lon is not None:
            params["inventory"] = {
                "location_lat": str(location_lat),
                "location_lon": str(location_lon),
                "location": f"{location_lat}, {location_lon}"
            }
        return self._call("host.update", params)

    def create_host(self, hostname, visible_name, ip_address, group_ids, template_ids, location_lat=None,
                    location_lon=None):
        """Cria uma câmera NOVA no Zabbix"""
        params = {
            "host": hostname,
            "name": visible_name,
            "groups": [{"groupid": gid} for gid in group_ids],
            "templates": [{"templateid": tid} for tid in template_ids],
            "macros": [
                {"macro": "{$HIKVISION_ISAPI_HOST}", "value": ip_address},
                {"macro": "{$HIKVISION_ISAPI_PORT}", "value": "9080"},
                {"macro": "{$USER}", "value": "admin"},
                {"macro": "{$PASSWORD}", "value": "5enhadaCamera", "type": 1}
            ],
            "inventory_mode": 0  # 0 significa que podemos colocar a localização manualmente via script
        }
        # Se tem mapa, coloca as coordenadas
        if location_lat is not None and location_lon is not None:
            params["inventory"] = {
                "location_lat": str(location_lat),
                "location_lon": str(location_lon),
                "location": f"{location_lat}, {location_lon}"
            }
        return self._call("host.create", params)

    def create_or_update_hosts_batch(self, hosts_data, group_ids, template_ids, update_existing=False):
        """Função que passa por todas as câmeras da lista e decide se Cria ou Atualiza"""
        created = 0;
        updated = 0;
        skipped = 0;
        errors = 0;
        with_location = 0;
        without_location = 0

        for host_data in hosts_data:
            try:
                hostname = host_data["hostname"]
                hostid = self.check_host_exists(hostname)  # Verifica se já existe

                location_lat = host_data.get("location_lat")
                location_lon = host_data.get("location_lon")

                # Conta quantas têm localização
                if location_lat and location_lon:
                    with_location += 1
                else:
                    without_location += 1

                if hostid:  # SE JÁ EXISTE NO ZABBIX
                    if update_existing:
                        self.update_host(
                            hostid=hostid, visible_name=host_data["visible_name"],
                            ip_address=host_data["ip"], group_ids=group_ids,
                            template_ids=template_ids, location_lat=location_lat, location_lon=location_lon
                        )
                        updated += 1
                    else:
                        skipped += 1  # Pula se não for para atualizar
                else:  # SE É NOVA
                    self.create_host(
                        hostname=hostname, visible_name=host_data["visible_name"],
                        ip_address=host_data["ip"], group_ids=group_ids,
                        template_ids=template_ids, location_lat=location_lat, location_lon=location_lon
                    )
                    created += 1

            except Exception as e:
                print(f"✗ Erro ao processar {host_data['hostname']}: {e}")
                errors += 1

        return created, updated, skipped, errors, with_location, without_location


# ==============================================================================
# FUNÇÃO QUE LÊ O CSV (A Planilha do Banco de Dados)
# ==============================================================================
def load_rs_hosts_from_csv(csv_filepath, device_type="camera"):
    """Lê o arquivo CSV linha por linha e prepara a lista de câmeras"""
    hosts = []

    # Verifica se o arquivo existe na pasta
    if not os.path.exists(csv_filepath):
        raise FileNotFoundError(f"Arquivo CSV não encontrado: {csv_filepath}")

    # Abre o arquivo CSV
    with open(csv_filepath, mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)

        # Para cada linha da planilha...
        for row in reader:
            id_estacao = row['id_estacao']
            ip = row['ip_mikrotik']
            # Limpa o nome da cidade tirando o "PCD " da frente
            nome_cidade = row['nome'].replace("PCD ", "").strip()
            codigo = row['codigo_estacao_interno']
            lat = row['latitude']
            lon = row['longitude']

            # Se não tiver código no BD, inventa um no padrão DCRS-00000
            if not codigo:
                codigo = f"DCRS-{int(id_estacao):05d}"

            # NOME TÉCNICO E NOME VISÍVEL
            # O ".CAMERA" no final impede que o Zabbix confunda a câmera com o Mikrotik
            hostname = f"BR.RS._.DCRS.{codigo}.CAMERA"
            visible_name = f"{codigo} - Camera Hikvision ({nome_cidade})"

            # Ignora as coordenadas se vierem zeradas (0.0) do banco
            location_lat = lat if lat and lat != "0.0" else None
            location_lon = lon if lon and lon != "0.0" else None

            # Guarda essa câmera na lista para enviar pro Zabbix depois
            hosts.append({
                "hostname": hostname,
                "visible_name": visible_name,
                "ip": ip,
                "location_lat": location_lat,
                "location_lon": location_lon
            })
    return hosts


# ==============================================================================
# FUNÇÃO PRINCIPAL (Onde o script começa de verdade)
# ==============================================================================
def main():
    # CONFIGURAÇÕES BÁSICAS
    ZABBIX_URL = "http://10.255.255.4:8888/api_jsonrpc.php"
    ZABBIX_API_TOKEN = "6d0a0ae04ef2e4130189c637ad3b7d552f7511b198a3a1e3f7ee203210b00630"  # <--- INSIRA O SEU TOKEN AQUI
    UPDATE_EXISTING = True  # Se True, atualiza as câmeras que já existem
    CSV_FILE = "consulta_estacoes_RS.csv"

    print("=" * 60)
    print("Script de Criação de CÂMERAS DCRS via API lendo do CSV")
    print("=" * 60)

    # 1. Conecta no Zabbix
    try:
        zapi = ZabbixAPI(ZABBIX_URL, api_token=ZABBIX_API_TOKEN)
        zapi.login()
    except Exception as e:
        print(f"✗ Erro ao conectar: {e}");
        return

    # 2. Busca o ID do Grupo de Câmeras do Rio Grande do Sul
    group_names = ["BR.RS._.DCRS - Cameras"]
    try:
        groups = zapi.get_hostgroup_ids(group_names)
        group_ids = [groups[name] for name in group_names]
    except Exception as e:
        print(f"✗ Erro ao buscar host groups: {e}");
        return

    # 3. Busca o ID do Template da Hikvision
    template_names = ["Hikvision camera by HTTP"]
    try:
        templates = zapi.get_template_ids(template_names)
        template_ids = [templates[name] for name in template_names]
    except Exception as e:
        print(f"✗ Erro ao buscar templates: {e}");
        return

    # 4. Lê o CSV
    print(f"\nLendo dados do CSV {CSV_FILE}...")
    hosts_data = load_rs_hosts_from_csv(CSV_FILE, "camera")
    print(f"✓ {len(hosts_data)} câmeras preparadas.")

    # 5. Envia tudo para o Zabbix
    print("\nIniciando processamento no Zabbix...")
    created, updated, skipped, errors, with_loc, without_loc = zapi.create_or_update_hosts_batch(
        hosts_data, group_ids, template_ids, update_existing=UPDATE_EXISTING
    )

    # 6. Resumo Final
    print("\n" + "=" * 60)
    print(f"✓ Câmeras criadas: {created}")
    print(f"✓ Câmeras atualizadas: {updated}")
    print(f"⊘ Câmeras puladas: {skipped}")
    print(f"✗ Erros: {errors}")
    print(f"📍 Com localização: {with_loc} | ⚠ Sem localização: {without_loc}")
    print("=" * 60)


if __name__ == "__main__":
    main()