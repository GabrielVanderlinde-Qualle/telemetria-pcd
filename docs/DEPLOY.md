# 🚀 Guia de Deploy — Grafana com Podman

Este guia cobre a instalação do zero até o Grafana acessível via URL na rede.

---

## Índice

1. [Pré-requisitos](#1-pré-requisitos)
2. [Instalar Podman e Podman Compose](#2-instalar-podman-e-podman-compose)
3. [Clonar o repositório](#3-clonar-o-repositório)
4. [Configurar variáveis](#4-configurar-variáveis)
5. [Subir o Grafana](#5-subir-o-grafana)
6. [Configurar o Zabbix Plugin](#6-configurar-o-zabbix-plugin)
7. [Importar o Dashboard](#7-importar-o-dashboard)
8. [Tornar acessível via URL (Nginx)](#8-tornar-acessível-via-url-nginx)
9. [Manutenção e atualizações](#9-manutenção-e-atualizações)
10. [Migração do VirtualBox para Podman](#10-migração-do-virtualbox-para-podman)

---

## 1. Pré-requisitos

- **Servidor**: Ubuntu 22.04 LTS ou superior (pode ser a mesma VM atual)
- **Acesso**: SSH ou terminal no servidor
- **Rede**: O servidor deve ter acesso ao IP do Zabbix (`10.255.255.4:8888`)
- **Porta**: Liberar porta `3000` no firewall (e `80`/`443` se usar Nginx)

---

## 2. Instalar Podman e Podman Compose

### Ubuntu 22.04+

```bash
# Atualiza pacotes
sudo apt update && sudo apt upgrade -y

# Instala Podman
sudo apt install -y podman

# Verifica instalação
podman --version
# Esperado: podman version 3.x.x ou superior

# Instala Podman Compose via pip
sudo apt install -y python3-pip
pip3 install podman-compose

# Verifica
podman-compose --version
```

### Configurar Podman sem root (rootless — recomendado)

```bash
# Adiciona seu usuário ao grupo correto
sudo usermod --add-subuids 100000-165535 $USER
sudo usermod --add-subgids 100000-165535 $USER

# Reinicia a sessão ou rode:
podman system migrate
```

---

## 3. Clonar o repositório

```bash
# Va para um diretório adequado
cd /opt

# Clone (substitua pela URL real do seu repositório)
sudo git clone https://github.com/SUA_ORG/telemetria-pcd.git
sudo chown -R $USER:$USER telemetria-pcd
cd telemetria-pcd
```

---

## 4. Configurar variáveis

```bash
# Copia o arquivo de exemplo
cp .env.example .env

# Edita com seus dados reais
nano .env
```

**Campos obrigatórios para preencher:**

| Variável | Onde encontrar |
|----------|----------------|
| `GF_SERVER_ROOT_URL` | IP ou domínio do servidor |
| `GF_SECURITY_SECRET_KEY` | Execute: `openssl rand -base64 32` |
| `GF_SECURITY_ADMIN_PASSWORD` | Escolha uma senha forte |
| `AZURE_CLIENT_ID` | Portal Azure → App Registrations |
| `AZURE_CLIENT_SECRET` | Portal Azure → App Registrations → Certificates |
| `AZURE_TENANT_ID` | Portal Azure → Azure Active Directory |
| `AZURE_ALLOWED_DOMAINS` | Seu domínio corporativo |
| `ZABBIX_URL` | URL da API do Zabbix |
| `ZABBIX_TOKEN` | Token de API do Zabbix |

> ⚠️ **Nunca commite o arquivo `.env`** — ele está no `.gitignore`.

---

## 5. Subir o Grafana

```bash
# Coloque o JSON do dashboard na pasta de provisionamento
cp dashboards/monitoramento_estacoes.json grafana/provisioning/dashboards/

# Sobe os containers em background
podman-compose up -d

# Acompanha os logs (Ctrl+C para sair)
podman-compose logs -f

# Verifica se está rodando
podman ps
```

**Saída esperada:**
```
CONTAINER ID  IMAGE                    COMMAND     STATUS
abc123def456  docker.io/grafana/grafana:latest     Up 2 minutes
```

Acesse: `http://IP_DO_SERVIDOR:3000`

---

## 6. Configurar o Zabbix Plugin

O plugin é instalado automaticamente via variável de ambiente `GF_INSTALL_PLUGINS`.

Na primeira vez, pode demorar 1-2 minutos para baixar. Acompanhe:

```bash
podman logs grafana-telemetria | grep -i plugin
```

Para ativar o plugin manualmente na interface:

1. Acesse `http://SEU_IP:3000`
2. Menu lateral → **Administration → Plugins**
3. Pesquise "Zabbix"
4. Clique em **Enable**

---

## 7. Importar o Dashboard

Se o provisionamento automático não carregar o dashboard:

1. Menu lateral → **Dashboards → Import**
2. Clique em **Upload dashboard JSON file**
3. Selecione `dashboards/monitoramento_estacoes.json`
4. Clique em **Import**

---

## 8. Tornar acessível via URL (Nginx)

Para expor o Grafana na rede com uma URL amigável:

```bash
# Instala Nginx
sudo apt install -y nginx

# Cria configuração
sudo nano /etc/nginx/sites-available/grafana
```

**Conteúdo do arquivo (sem HTTPS por enquanto):**

```nginx
server {
    listen 80;
    server_name monitoramento.suaempresa.com.br;  # Ou apenas o IP

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket (necessário para atualizações em tempo real)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

```bash
# Ativa a configuração
sudo ln -s /etc/nginx/sites-available/grafana /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx
```

Acesse via: `http://monitoramento.suaempresa.com.br`

### (Opcional) HTTPS com Certbot

```bash
# Instala Certbot (apenas se tiver domínio público)
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d monitoramento.suaempresa.com.br

# Atualize o .env com a URL HTTPS:
# GF_SERVER_ROOT_URL=https://monitoramento.suaempresa.com.br
podman-compose restart grafana
```

---

## 9. Manutenção e atualizações

```bash
# Ver logs
podman-compose logs -f

# Parar
podman-compose down

# Atualizar imagem do Grafana
podman-compose pull
podman-compose up -d

# Backup dos dados do Grafana
podman run --rm -v grafana-data:/data -v $(pwd):/backup alpine \
  tar czf /backup/grafana-backup-$(date +%Y%m%d).tar.gz -C /data .

# Restaurar backup
podman run --rm -v grafana-data:/data -v $(pwd):/backup alpine \
  tar xzf /backup/grafana-backup-YYYYMMDD.tar.gz -C /data

# Reiniciar após mudanças no .env
podman-compose down && podman-compose up -d
```

---

## 10. Migração do VirtualBox para Podman

Se você tem o Grafana rodando no VirtualBox e quer migrar:

### Passo 1: Exportar dados do Grafana atual

No terminal da VM do VirtualBox:
```bash
# Descubra onde os dados do Grafana estão
find / -name "grafana.db" 2>/dev/null

# Exemplo: /var/lib/grafana/grafana.db
# Copie via SCP para a nova máquina:
scp /var/lib/grafana/grafana.db usuario@IP_NOVA_MAQUINA:/opt/telemetria-pcd/grafana-backup.db
```

### Passo 2: Restaurar no Podman

```bash
# Na nova máquina, após o Grafana subir pela primeira vez:
podman-compose down

# Copia o banco antigo para o volume
podman run --rm \
  -v grafana-data:/var/lib/grafana \
  -v $(pwd):/backup \
  alpine cp /backup/grafana-backup.db /var/lib/grafana/grafana.db

podman-compose up -d
```

### Passo 3: Verificar

Acesse o Grafana e verifique se os dashboards e datasources estão presentes.

> ✅ Após confirmar, pode desligar a VM do VirtualBox.
