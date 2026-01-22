import os
import sys

def main():
    print("🚀 Configurando ambiente local...")

    # 1. Configurar .streamlit/secrets.toml falso se não existir
    if not os.path.exists(".streamlit"):
        os.makedirs(".streamlit")
        print("📁 Pasta .streamlit criada.")

    if not os.path.exists(".streamlit/secrets.toml"):
        with open(".streamlit/secrets.toml", "w") as f:
            f.write("# Configuração Local Automática\n")
            f.write("GEMINI_KEY=''\n")
        print("✅ .streamlit/secrets.toml criado (Vazio).")
    else:
        print("ℹ️ .streamlit/secrets.toml já existe.")

    # 2. Inicializar Banco de Dados
    print("📊 Verificando banco de dados...")
    try:
        import db
        db.init_db()
        if os.path.exists("market_hacking.db"):
            print("✅ market_hacking.db pronto!")
        else:
            print("❌ Erro: Arquivo de banco não encontrado após init.")
    except Exception as e:
        print(f"❌ Erro ao inicializar DB: {e}")
        print("Tente rodar: pip install -r requirements.txt")

    print("\n\n🎉 TUDO PRONTO! Para rodar:")
    print("streamlit run app.py")

if __name__ == "__main__":
    main()
