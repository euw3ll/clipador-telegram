#!/bin/bash

echo ""
echo "🔄 Atualizando projeto Clipador..."

# Salva alterações não commitadas
git stash save -u "Backup automático antes de atualizar"

# Puxa do repositório remoto
git pull origin main

# Tenta reaplicar as alterações stashed
git stash pop || echo "⚠️ Nenhuma alteração stashed para reaplicar."

echo "✅ Projeto atualizado com sucesso!"
echo ""
