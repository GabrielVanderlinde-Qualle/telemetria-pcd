# 🔐 Autenticação com Conta Microsoft (Azure AD)

Este guia explica como configurar o login do Grafana usando as contas corporativas Microsoft — as mesmas do Outlook, Teams e demais serviços da empresa.

---

## Como funciona

O Grafana usa o protocolo **OAuth2** para se comunicar com o Azure Active Directory (Azure AD). Quando o usuário clica em "Sign in with Microsoft", é redirecionado para a tela de login da Microsoft e, após autenticar, volta para o Grafana já logado.

**Nenhuma senha é armazenada no Grafana.** A autenticação é 100% gerenciada pela Microsoft.

---

## Passo 1: Registrar aplicação no Azure

1. Acesse o [Portal Azure](https://portal.azure.com) com uma conta de administrador

2. Pesquise por **"App registrations"** na barra de busca

3. Clique em **"New registration"**

4. Preencha:
   - **Name**: `Grafana Telemetria PCDs`
   - **Supported account types**: `Accounts in this organizational directory only`
   - **Redirect URI**: Selecione `Web` e digite:
     ```
     http://SEU_IP_OU_DOMINIO:3000/login/azuread
     ```
     (se usar HTTPS: `https://monitoramento.suaempresa.com.br/login/azuread`)

5. Clique em **"Register"**

---

## Passo 2: Coletar o Client ID e Tenant ID

Após criar o registro, na página do aplicativo:

- Copie o **Application (client) ID** → será o `AZURE_CLIENT_ID`
- Copie o **Directory (tenant) ID** → será o `AZURE_TENANT_ID`

---

## Passo 3: Criar o Client Secret

1. No menu lateral, clique em **"Certificates & secrets"**
2. Clique em **"New client secret"**
3. Descrição: `Grafana Telemetria` | Validade: `24 months`
4. Clique em **"Add"**
5. **COPIE IMEDIATAMENTE o valor** (Value, não o Secret ID) — ele não será mostrado novamente
   → Este é o `AZURE_CLIENT_SECRET`

---

## Passo 4: Configurar permissões da API

1. No menu lateral, clique em **"API permissions"**
2. Clique em **"Add a permission"**
3. Selecione **"Microsoft Graph"** → **"Delegated permissions"**
4. Adicione as permissões:
   - `email`
   - `openid`
   - `profile`
5. Clique em **"Grant admin consent"** (requer conta de administrador)

---

## Passo 5: Preencher o .env

```bash
nano .env
```

```env
AZURE_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_CLIENT_SECRET=sua_secret_aqui~ABCdef
AZURE_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_ALLOWED_DOMAINS=suaempresa.com.br
GF_AUTH_AZUREAD_ENABLED=true
```

Reinicie o Grafana:
```bash
podman-compose down && podman-compose up -d
```

---

## Passo 6: Testar o login

1. Abra uma janela anônima no navegador
2. Acesse `http://SEU_IP:3000`
3. Deve aparecer o botão **"Sign in with Microsoft"**
4. Clique e faça login com sua conta corporativa (`usuario@suaempresa.com.br`)
5. Na primeira vez, pode pedir para aceitar as permissões — clique em **"Accept"**

---

## Configurações adicionais (recomendadas após teste)

### Remover o formulário de login padrão

Depois de confirmar que o Azure AD está funcionando, você pode esconder o formulário de usuário/senha:

```env
GF_AUTH_DISABLE_LOGIN_FORM=true
```

### Login automático (redireciona diretamente para Microsoft)

```env
GF_AUTH_AZUREAD_AUTO_LOGIN=true
```

> ⚠️ **Ative o login automático SOMENTE após confirmar que o Azure funciona.** Caso contrário, você pode ser bloqueado. Para recuperar o acesso de emergência, remova essa variável e reinicie.

---

## Controle de acesso por cargo

Por padrão, todos os usuários autenticados pelo Azure recebem o papel de `Viewer` (somente leitura).

Para dar acesso de `Editor` ou `Admin` a usuários específicos:

1. Acesse o Grafana com conta admin
2. **Administration → Users**
3. Localize o usuário e altere o papel (Role)

---

## Troubleshooting

### "Invalid redirect URI"
- Verifique se a URI no Azure corresponde EXATAMENTE à URL do Grafana (incluindo `/login/azuread`)
- O Azure diferencia `http` de `https`

### "Forbidden: The user is not allowed"
- Verifique `AZURE_ALLOWED_DOMAINS` — deve ser o domínio do e-mail do usuário
- Ou deixe `AZURE_ALLOWED_GROUPS` vazio para permitir todos do domínio

### O botão Microsoft não aparece
- Verifique se `GF_AUTH_AZUREAD_ENABLED=true` está no `.env`
- Veja os logs: `podman-compose logs grafana | grep -i azure`
