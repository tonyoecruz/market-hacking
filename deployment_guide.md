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
2. Tente fazer login com o Google.
3. Se houver erro de "redirect_uri_mismatch", verifique se a URL no navegador é EXATAMENTE igual (http vs https, www vs sem www) à cadastrada no Google Cloud Console e na variável `REDIRECT_URI` nos Secrets.
