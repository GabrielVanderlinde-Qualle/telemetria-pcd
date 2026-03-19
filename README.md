# 📡 Sistema de Monitoramento de Estações Telemétricas

Sistema de monitoramento em tempo real de PCDs (Plataformas de Coleta de Dados) dos estados de **Rio Grande do Sul** e **Santa Catarina**, integrado com Zabbix e visualizado via Grafana.

---

## 🗂️ Estrutura do Repositório

```
telemetria-pcd/
│
├── 📁 grafana/                    # Configurações do Grafana
│   ├── 📁 config/                 # grafana.ini (autenticação Microsoft, SMTP)
│   ├── 📁 provisioning/
│   │   ├── 📁 dashboards/         # Provisionamento automático dos dashboards
│   │   └── 📁 datasources/        # Provisionamento automático do Zabbix
│   └── 📄 docker-compose.yml      # (referência — usamos Podman)
│
├── 📁 dashboards/                 # JSONs dos dashboards Grafana
│   ├── 📄 monitoramento_estacoes.json   ← Dashboard principal (ATUAL)
│   └── 📁 historico/                    ← Versões anteriores (para referência)
│
├── 📁 scripts/                    # Scripts Python de automação
│   ├── 📁 zabbix/                 # Inserção/atualização de hosts no Zabbix
│   │   ├── 📄 insert-dcrs-mikrotik.py
│   │   ├── 📄 insert-dcrs-cameras.py
│   │   ├── 📄 insert-dcrs-starlink.py
│   │   ├── 📄 insert-dcsc-mikrotik.py
│   │   ├── 📄 insert-dcsc-cameras.py
│   │   ├── 📄 insert-dcsc-starlink.py
│   │   └── 📄 cria_itens_coordenadas.py
│   └── 📁 utils/                  # Utilitários de manutenção
│       ├── 📄 marcar_estacoes_pendentes.py
│       └── 📄 corrigir_coordenadas.py
│
├── 📁 data/                       # CSVs com dados das estações (NÃO versionar dados sensíveis)
│   ├── 📄 consulta_estacoes_RS.csv
│   └── 📄 consulta_estacoes_SC.csv
│
├── 📁 docs/                       # Documentação adicional
│   ├── 📄 DEPLOY.md               # Guia completo de deploy com Podman
│   ├── 📄 AUTENTICACAO.md         # Configurar login com conta Microsoft
│   └── 📄 SCRIPTS.md              # Como usar os scripts Python
│
├── 📄 podman-compose.yml          # ← Deploy principal com Podman
├── 📄 .env.example                # Variáveis de ambiente (copiar para .env)
├── 📄 .gitignore
└── 📄 README.md                   # Este arquivo
```

---

## 🚀 Deploy Rápido (Podman)

### Pré-requisitos
- Podman instalado (`podman --version`)
- Podman Compose (`pip install podman-compose`)
- Acesso à rede onde o Zabbix está rodando
- Conta Microsoft para autenticação (Azure AD configurado)

### 1. Clonar o repositório
```bash
git clone https://github.com/SUA_ORG/telemetria-pcd.git
cd telemetria-pcd
```

### 2. Configurar variáveis de ambiente
```bash
cp .env.example .env
nano .env   # Preencha as variáveis com seus dados reais
```

### 3. Subir o Grafana com Podman
```bash
podman-compose up -d
```

### 4. Acessar o dashboard
Abra no navegador: `http://SEU_IP_SERVIDOR:3000`

Login com sua conta Microsoft (`usuario@suaempresa.com.br`)

> 📖 Para deploy completo com URL pública e HTTPS, veja [docs/DEPLOY.md](docs/DEPLOY.md)

---

## 🏗️ Arquitetura

```
Internet / Rede Interna
        │
        ▼
┌───────────────────┐
│   Nginx (Proxy)   │  :443 HTTPS → :3000 Grafana
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  Grafana (Podman) │  Lê dados do Zabbix via plugin
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  Zabbix Server    │  Monitora 314 estações (RS + SC)
└─────────┬─────────┘
          │
     ┌────┴────┐
     ▼         ▼
 PCDs RS    PCDs SC
(Mikrotik) (Mikrotik)
```

---

## 📊 O Dashboard

O painel principal exibe:

| Painel | Função |
|--------|--------|
| **SEM COMUNICAÇÃO** | Contagem de estações com ICMP ping = 0 (instaladas + sem resposta) |
| **ESTAÇÕES ESTÁVEIS** | Contagem de estações com ICMP ping = 1 (online) |
| **Mapa Geolocalização** | Mapa interativo: 🔴 Offline / 🟢 Online |

### Filtros disponíveis
- **GRUPO / ESTADO** → Filtra por RS, SC ou ambos
- **ESTAÇÃO** → Seleciona uma estação específica
- **STATUS MAPA** → Mostra Todos / Somente Estáveis / Somente Sem Comunicação

---

## 🐍 Scripts Python

### Inserção de hosts no Zabbix
```bash
cd scripts/zabbix

# Rio Grande do Sul
python insert-dcrs-mikrotik.py    # Insere/atualiza Mikrotiks do RS
python insert-dcrs-cameras.py     # Insere/atualiza Câmeras do RS
python insert-dcrs-starlink.py    # Insere/atualiza Starlinks do RS

# Santa Catarina
python insert-dcsc-mikrotik.py    # Insere/atualiza Mikrotiks do SC
python insert-dcsc-cameras.py     # Insere/atualiza Câmeras do SC
python insert-dcsc-starlink.py    # Insere/atualiza Starlinks do SC
```

### Utilitários de manutenção
```bash
cd scripts/utils

# Marca estações sem coordenadas como "pendente" (ignora no Grafana)
python marcar_estacoes_pendentes.py   # MODO = "listar" (seguro)
# → Mude para MODO = "adicionar" para aplicar

# Corrige lat/lon invertidos no Zabbix
python corrigir_coordenadas.py        # MODO = "listar" (seguro)
# → Mude para MODO = "corrigir" para aplicar
```

> 📖 Detalhes de cada script em [docs/SCRIPTS.md](docs/SCRIPTS.md)

---

## 🔐 Autenticação Microsoft

O Grafana está configurado para usar **Azure AD (OAuth2)** — o mesmo login do Outlook/Teams.

Ao acessar o dashboard, clique em **"Sign in with Microsoft"**.

> 📖 Como configurar o Azure AD: [docs/AUTENTICACAO.md](docs/AUTENTICACAO.md)

---

## 👥 Equipe

| Papel | Responsabilidade |
|-------|-----------------|
| Infraestrutura | Zabbix, rede, PCDs |
| Desenvolvimento | Scripts Python, Dashboard Grafana |
| Gestão | Acompanhamento do monitoramento |

---

## 📝 Changelog

| Versão | Data | Descrição |
|--------|------|-----------|
| v1.0.0 | 2025-03 | Dashboard inicial com mapa e gauges |
| v1.1.0 | 2025-03 | Filtro por estado RS/SC funcionando |
| v1.2.0 | 2025-03 | Cores do mapa corrigidas (ping 0=vermelho, 1=verde) |
| v1.3.0 | 2025-03 | Filtro de estações fantasmas via Latitude |
