# 🚀 SCOPE3 FastAPI - Guia Rápido

## ✅ Correção Aplicada

**Problema:** Email duplicado causava erro genérico  
**Solução:** Sistema agora detecta e mostra mensagens amigáveis:
- ✅ "Email já está cadastrado"
- ✅ "Nome de usuário já está em uso"
- ✅ "As senhas não coincidem"
- ✅ Formulário mantém valores preenchidos

---

## 🔧 Como Testar Agora

### 1. Parar Streamlit (se estiver rodando)
```bash
# Pressione Ctrl+C no terminal do Streamlit
```

### 2. Instalar Dependências FastAPI
```bash
pip install fastapi uvicorn[standard] jinja2 python-multipart python-jose[cryptography] passlib[bcrypt] python-dotenv pydantic email-validator supabase
```

### 3. Configurar Variáveis de Ambiente

Criar arquivo `.env` na raiz do projeto:
```env
SUPABASE_URL=sua_url_supabase
SUPABASE_KEY=sua_chave_supabase
JWT_SECRET=sua_chave_secreta_jwt
```

### 4. Rodar FastAPI
```bash
python main.py
```

Ou:
```bash
uvicorn main:app --reload --port 8000
```

### 5. Acessar
- **App**: http://localhost:8000
- **Registro**: http://localhost:8000/auth/register
- **Login**: http://localhost:8000/auth/login
- **API Docs**: http://localhost:8000/api/docs

---

## 📊 Status da Migração

### ✅ Completo
- [x] Estrutura modular
- [x] Database layer (Supabase)
- [x] Autenticação (JWT + bcrypt)
- [x] Dashboard básico
- [x] Templates Tailwind CSS
- [x] Error handling amigável

### 🚧 Em Progresso
- [ ] Análise de Ações (Graham + Magic Formula)
- [ ] ETFs
- [ ] Elite Mix
- [ ] FIIs
- [ ] Arena

---

## 🎯 Próximos Passos

1. **Testar registro/login** com o novo sistema
2. **Migrar análise de ações** do app.py antigo
3. **Adicionar funcionalidades AI** (Gemini)
4. **Deploy no Render.com**

---

## 💡 Dicas

### Criar Usuário Novo
Se o email `tonyoecruz@gmail.com` já existe, use outro email ou delete o registro antigo no Supabase.

### Verificar Logs
O FastAPI mostra logs detalhados no terminal, facilitando debug.

### Hot Reload
Com `--reload`, o servidor reinicia automaticamente ao salvar arquivos.

---

## 🐛 Troubleshooting

**Erro de import:**
```bash
pip install --upgrade -r requirements.txt
```

**Porta 8000 ocupada:**
```bash
uvicorn main:app --reload --port 8001
```

**Supabase não conecta:**
Verifique se `.env` está configurado corretamente.
