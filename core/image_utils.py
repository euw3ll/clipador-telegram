import os
from PIL import Image, ImageDraw, ImageOps
from telegram.ext import ContextTypes

# Certifique-se de que a pasta temp exista
os.makedirs("temp", exist_ok=True)

BASE_LOGO_PATH = os.path.join("images", "logo_canal.jpg")

async def gerar_imagem_canal_personalizada(telegram_id: int, context: ContextTypes.DEFAULT_TYPE) -> str:
    """
    Gera uma imagem de perfil para o canal, combinando o logo base com a foto do usuário.
    Retorna o caminho para a imagem gerada ou o caminho do logo base se algo falhar.
    """
    try:
        # 1. Verificar se o logo base existe
        if not os.path.exists(BASE_LOGO_PATH):
            print(f"⚠️ Aviso: Imagem base não encontrada em {BASE_LOGO_PATH}. Usando fallback.")
            return BASE_LOGO_PATH

        # 2. Obter a foto de perfil do usuário
        fotos_perfil = await context.bot.get_user_profile_photos(user_id=telegram_id, limit=1)
        if not fotos_perfil or not fotos_perfil.photos:
            print(f"ℹ️ Info: Usuário {telegram_id} não tem foto de perfil. Usando logo padrão.")
            return BASE_LOGO_PATH

        # 3. Baixar a foto de maior resolução
        foto_file = await fotos_perfil.photos[0][-1].get_file()
        caminho_foto_temp = os.path.join("temp", f"{telegram_id}_profile.jpg")
        await foto_file.download_to_drive(caminho_foto_temp)

        # 4. Manipulação de imagem com Pillow
        logo_base = Image.open(BASE_LOGO_PATH).convert("RGBA")
        foto_usuario = Image.open(caminho_foto_temp).convert("RGBA")

        # Define o tamanho do círculo da foto do usuário (ex: 180x180 pixels)
        tamanho_circulo = (180, 180)
        foto_usuario = foto_usuario.resize(tamanho_circulo, Image.Resampling.LANCZOS)

        # Cria a máscara circular
        mascara = Image.new('L', tamanho_circulo, 0)
        desenho = ImageDraw.Draw(mascara)
        desenho.ellipse((0, 0) + tamanho_circulo, fill=255)

        # Aplica a máscara e cola no logo base (canto inferior direito com margem de 20px)
        posicao = (logo_base.width - tamanho_circulo[0] - 20, logo_base.height - tamanho_circulo[1] - 20)
        logo_base.paste(foto_usuario, posicao, mascara)

        # 5. Salva a imagem final
        caminho_final = os.path.join("temp", f"{telegram_id}_final_logo.png")
        logo_base.save(caminho_final, "PNG")

        # 6. Limpa o arquivo temporário da foto do usuário
        os.remove(caminho_foto_temp)

        print(f"✅ Imagem de perfil personalizada criada para {telegram_id} em {caminho_final}")
        return caminho_final

    except Exception as e:
        print(f"❌ Erro ao gerar imagem personalizada para {telegram_id}: {e}. Usando logo padrão.")
        return BASE_LOGO_PATH