#!/bin/bash

echo ""
echo "📤 Subindo alterações para o Git..."

# Solicita mensagem do commit
echo -n "📝 Digite uma mensagem de commit: "
read mensagem

# Adiciona todos os arquivos
git add .

# Faz o commit
git commit -m "$mensagem"

# Envia para o repositório
git push origin main

echo "✅ Alterações enviadas com sucesso!"
echo ""
