# 🚀 Guia de Implantação (Deployment Guide)

Este guia descreve como configurar e implantar o aplicativo **Scope3 Ultimate** no Streamlit Cloud, com foco na autenticação do Google.

## 1. Configuração do Google Cloud Console

Para que o login com Google funcione no ambiente web (Streamlit Cloud), você deve configurar as credenciais corretamente.

1. Acesse o [Google Cloud Console](https://console.cloud.google.com/).
2. Selecione seu projeto.
3. Vá para **APIs e Serviços > Credenciais**.
4. Edite sua credencial **ID do cliente OAuth 2.0**.
5. Em **URIs de redirecionamento autorizados**, adicione a URL da sua aplicação implantada:
   - Formato: `https://scope3.streamlit.app`
   - **IMPORTANTE:** Não use a barra final (`/`) no Google Console, mas certifique-se de que a configuração no `secrets.toml` corresponda exatamente.

## 2. Configurando Secrets no Streamlit Cloud

No Streamlit Cloud, não usamos o arquivo `client_secret.json`. Usamos os **Secrets**.

1. No painel do Streamlit Cloud, vá nas configurações do seu app.
2. Clique em **Secrets**.
3. Adicione o seguinte conteúdo (substitua pelos seus dados):

```toml
# Chave da API Gemini (IA)
GEMINI_KEY = "sua-chave-gemini-aqui"

# Configuração Google Auth
REDIRECT_URI = "https://scope3.streamlit.app"

[google_auth]
client_id = "seu-client-id-do-google.apps.googleusercontent.com"
project_id = "seu-project-id"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_secret = "seu-client-secret-aqui"
redirect_uris = ["https://scope3.streamlit.app"]
```

> **Nota:** A seção `[google_auth]` deve conter os campos que estão dentro do JSON baixado do Google (geralmente dentro de "installed" ou "web"). Certifique-se de ajustar a estrutura se necessário. O código espera `st.secrets["google_auth"]` como um dicionário.

## 3. Arquivos Importantes

- **requirements.txt**: Garante que as bibliotecas necessárias sejam instaladas. Certifique-se de que ele contém:
  ```text
  streamlit>=1.30.0
  google-auth-oauthlib
  google-generativeai
  ...
  ```
- **assets/**: Pasta contendo imagens e recursos estáticos.

## 4. Testando

Asssim que implantar:
1. Abra o app na URL pública.
3. Se houver erro de "redirect_uri_mismatch", verifique se a URL no navegador é EXATAMENTE igual (http vs https, www vs sem www) à cadastrada no Google Cloud Console e na variável `REDIRECT_URI` nos Secrets.

## 5. Configurando Supabase (Banco de Dados)

Para persistir dados, configuramos o app para conectar ao Postgres do Supabase.

1. **Crie o Projeto**: Crie um novo projeto no [Supabase](https://supabase.com/).
2. **Crie as Tabelas**: 
   - Vá em **SQL Editor** no menu esquerdo.
   - Copie o conteúdo do arquivo `supabase_schema.sql` do seu repositório.
   - Cole e clique em **Run**.
3. **Pegue a String de Conexão (IMPORTANTE)**:
   - Vá em **Project Settings (engrenagem) > Database**.
   - Em "Connection Method", procure por **Connection Pooler** (ou Transaction Pooler).
   - Use a **Mode: Session**.
   - A porta DEVE ser **6543** (isso garante suporte IPv4, necessário para o Streamlit Cloud).
   - Copie a URI.
   - **CORREÇÃO DE PROTOCOLO**: Se começar com `postgres://`, mude para `postgresql://`.
   - Exemplo final correto: `postgresql://postgres.xxxx:senha@aws-0-sa-east-1.pooler.supabase.com:6543/postgres?sslmode=require`

4. **Adicione aos Secrets**:
   - No Streamlit Cloud (App Settings > Secrets), edite para ficar assim:

   ```toml
   [connections.postgresql]
   dialect = "postgresql"
   url = "postgresql://postgres.xxxx:[SUA-SENHA]@aws-0-sa-east-1.pooler.supabase.com:6543/postgres"
   ```
   *(Ou se preferir o formato de chave única que configuramos antes, ajuste conforme necessário, mas o padrão `st.connection` prefere a seção toml acima).*

