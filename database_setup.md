# Configuração de Banco de Dados na Nuvem (PostgreSQL)

Para garantir que seus dados (carteira, login) não sejam perdidos a cada atualização do App no Streamlit Cloud, migramos para **PostgreSQL**.

Você precisa de um banco de dados **GRATUITO**. Recomendamos **Supabase** ou **Neon**.

## Opção 1: Supabase (Recomendado)
1. Crie uma conta em [supabase.com](https://supabase.com).
2. Crie um novo projeto (New Project).
3. Vá em **Project Settings** (Engrenagem) -> **Database**.
4. Em **Connection parameters**, desmarque "Use Supabase Pooler" (se houver essa opção para simplificar, ou use a Session Mode).
5. Copie a **URI** (Connection String). Ela se parece com:
   `postgresql://postgres.user:password@aws-0-sa-east-1.pooler.supabase.com:6543/postgres`
   *(Lembre-se de substituir [YOUR-PASSWORD] pela senha que criou)*.

## Opção 2: Neon.tech
1. Crie uma conta em [neon.tech](https://neon.tech).
2. Crie um projeto.
3. Copie a **Connection String** do Dashboard.

---

## Onde Colocar a Senha?

### No Streamlit Cloud (Produção)
1. Vá no Dashboard do seu App no Streamlit.
2. Clique em **Settings** -> **Secrets**.
3. Adicione o seguinte bloco:

```toml
[connections.postgresql]
dialect = "postgresql"
username = "SEU_USUARIO"
password = "SUA_SENHA_REAL"
host = "SEU_HOST_DO_SUPABASE"
port = 5432
database = "postgres"
```

**OU (Mais Fácil) usando URL direta:**

```toml
[connections.postgresql]
url = "postgresql://postgres.xxxx:yyyy@host:5432/postgres"
```

### Localmente (Seu PC)
Se não configurar nada, o app usará **SQLite local** (`market_hacking.db`) automaticamente como fallback. Você não precisa fazer nada se só quiser testar.
Mas se quiser testar o banco real, edite `.streamlit/secrets.toml`.
