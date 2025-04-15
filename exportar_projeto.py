import os

PASTA_BASE = "."  # você pode trocar por "canal_gratuito", por exemplo
EXTENSOES = [".py"]
EXCLUIR_PASTAS = ["__pycache__", ".git", ".venv"]

saida = []

for root, dirs, files in os.walk(PASTA_BASE):
    dirs[:] = [d for d in dirs if d not in EXCLUIR_PASTAS and not d.startswith('.venv')]
    for file in files:
        caminho_completo = os.path.join(root, file)
        caminho_relativo = os.path.relpath(caminho_completo, start=PASTA_BASE)

        # Ignorar arquivos ocultos (ex: .env, .venv, etc.)
        if any(part.startswith('.') for part in caminho_relativo.split(os.sep)):
            continue

        if any(file.endswith(ext) for ext in EXTENSOES):
            with open(caminho_completo, "r", encoding="utf-8") as f:
                conteudo = f.read()
            saida.append(f"📄 {caminho_relativo}\n---\n{conteudo}\n---\n")

with open("export_projeto.txt", "w", encoding="utf-8") as f_out:
    f_out.writelines(saida)

print("✅ Projeto exportado para export_projeto.txt")
