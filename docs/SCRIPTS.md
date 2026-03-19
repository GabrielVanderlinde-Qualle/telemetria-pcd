# 🐍 Scripts Python — Guia de Uso

Scripts para automação da inserção e manutenção dos hosts no Zabbix.

---

## Configuração inicial

### Dependências
```bash
pip install requests
```

### Token de API do Zabbix

1. Acesse o Zabbix: `http://SEU_IP_ZABBIX:8888`
2. **Administration → API tokens → Create API token**
3. Nome: `Grafana Scripts`
4. Copie o token e cole nos scripts ou no `.env`

> Em cada script, localize a variável `ZABBIX_API_TOKEN` e substitua pelo seu token.

---

## Scripts de Inserção de Hosts

Todos os scripts de inserção seguem o mesmo padrão:
- Lê um CSV com dados das estações
- Para cada linha, verifica se o host já existe no Zabbix
- Se não existe: **cria**
- Se existe e `UPDATE_EXISTING = True`: **atualiza**
- Se existe e `UPDATE_EXISTING = False`: **pula** (sem alteração)

### Rio Grande do Sul (DCRS)

```bash
cd scripts/zabbix

# Mikrotiks do RS — usa consulta_estacoes_RS.csv
python insert-dcrs-mikrotik.py

# Câmeras do RS — usa consulta_estacoes_RS.csv
python insert-dcrs-cameras.py

# Starlinks do RS — usa consulta_estacoes_RS.csv
python insert-dcrs-starlink.py
```

### Santa Catarina (DCSC)

```bash
cd scripts/zabbix

# Mikrotiks do SC — usa consulta_estacoes_SC.csv
python insert-dcsc-mikrotik.py

# Câmeras do SC — usa consulta_estacoes_SC.csv
python insert-dcsc-cameras.py

# Starlinks do SC — usa consulta_estacoes_SC.csv
python insert-dcsc-starlink.py
```

### Itens de coordenadas (Latitude/Longitude)

Cria itens calculados no Zabbix para que o Grafana possa ler as coordenadas das estações e plotar no mapa:

```bash
python scripts/zabbix/cria_itens_coordenadas.py
```

> Execute este script após inserir/atualizar os hosts, sempre que as coordenadas mudarem.

---

## Scripts Utilitários

### marcar_estacoes_pendentes.py

Marca estações sem coordenadas válidas com a tag `status=pendente`. O Grafana ignora essas estações nas queries, evitando que apareçam como falsas "Sem Comunicação".

```bash
cd scripts/utils
python marcar_estacoes_pendentes.py
```

**Modos de operação** — edite a variável `MODO` no topo do script:

| Modo | O que faz |
|------|-----------|
| `"listar"` | Mostra o que seria feito, **sem alterar nada** ← comece aqui |
| `"adicionar"` | Adiciona a tag `status=pendente` nos hosts sem coordenadas |
| `"remover"` | Remove a tag (desfaz tudo) |

### corrigir_coordenadas.py

Detecta e corrige hosts com latitude e longitude invertidas no Zabbix (aparecem no oceano ou em estados errados no mapa).

```bash
cd scripts/utils
python corrigir_coordenadas.py
```

**Modos de operação:**

| Modo | O que faz |
|------|-----------|
| `"listar"` | Lista as inversões detectadas, **sem alterar nada** ← comece aqui |
| `"corrigir"` | Corrige as coordenadas invertidas no Zabbix |

---

## Formato dos CSVs

Os scripts esperam o seguinte formato:

```csv
"id_estacao","ip_mikrotik","nome","longitude","latitude","codigo_estacao_interno","codigo_estacao_parceiro"
3,"10.192.10.3",PCD Agronômica,-49.712184,-27.258017,DCSC-00001,DCSC-00001
```

> ⚠️ Note que as colunas estão na ordem `longitude, latitude` — não confunda!

---

## Nomenclatura dos hosts no Zabbix

| Tipo | Padrão | Exemplo |
|------|--------|---------|
| Mikrotik RS | `BR.RS._.DCRS.{CODIGO}.MIKROTIK` | `BR.RS._.DCRS.DCRS-00001.MIKROTIK` |
| Câmera RS | `BR.RS._.DCRS.{CODIGO}.CAMERA` | `BR.RS._.DCRS.DCRS-00001.CAMERA` |
| Starlink RS | `BR.RS._.DCRS.{CODIGO}.STARLINK` | `BR.RS._.DCRS.DCRS-00001.STARLINK` |
| Mikrotik SC | `BR.SC._.DCSC.{CODIGO}.MIKROTIK` | `BR.SC._.DCSC.DCSC-00001.MIKROTIK` |
| Câmera SC | `BR.SC._.DCSC.{CODIGO}.CAMERA` | `BR.SC._.DCSC.DCSC-00001.CAMERA` |
| Starlink SC | `BR.SC._.DCSC.{CODIGO}.STARLINK` | `BR.SC._.DCSC.DCSC-00001.STARLINK` |

---

## Lógica de Status

- Estação com IP `0.0.0.0` → Zabbix **desativa** o host automaticamente
- Estação sem coordenadas (lat/lon = 0.0 ou vazio) → marcada como **pendente** pelo script utilitário
- Estação ativa com IP real mas sem resposta → aparece como **Sem Comunicação** no dashboard

A regra de "Sem Comunicação oficial" no Zabbix é **5 pings consecutivos** com falha (5 minutos sem resposta), configurada via trigger no template Mikrotik.
