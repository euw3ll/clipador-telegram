@echo off
echo 🔁 Atualizando projeto local...

git stash
git pull origin main
git stash pop

echo ✅ Projeto atualizado com sucesso!
pause
