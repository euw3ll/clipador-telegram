import os
from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO
import logging

logger = logging.getLogger(__name__)

async def gerar_imagem_canal_personalizada(telegram_id: int, context) -> str:
    """
    Gera uma imagem de perfil personalizada para o canal do Telegram.
    Coloca a foto de perfil do usuário no canto inferior direito de uma imagem base.
    """
    base_image_path = os.path.join("images", "logo_canal.jpg")
    output_dir = "memoria/canais_imagens"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"canal_{telegram_id}.jpg")

    try:
        # Carregar imagem base
        if not os.path.exists(base_image_path):
            logger.warning(f"Imagem base não encontrada em {base_image_path}. Criando uma imagem padrão.")
            base_img = Image.new('RGB', (500, 500), color = (73, 109, 137))
            d = ImageDraw.Draw(base_img)
            fnt = ImageFont.load_default()
            d.text((10,10), "Clipador", font=fnt, fill=(255,255,255))
        else:
            base_img = Image.open(base_image_path).convert("RGBA")

        # Obter foto de perfil do usuário
        user_profile_photos = await context.bot.get_user_profile_photos(user_id=telegram_id, limit=1)
        if user_profile_photos.photos and user_profile_photos.photos[0]:
            photo_file_id = user_profile_photos.photos[0][-1].file_id # Pega a maior versão da foto
            photo_file = await context.bot.get_file(photo_file_id)
            response = requests.get(photo_file.file_path)
            user_img = Image.open(BytesIO(response.content)).convert("RGBA")

            # Redimensionar e colar a imagem do usuário (MAIOR)
            base_width, base_height = base_img.size
            target_size = int(min(base_width, base_height) * 0.6) # Aumentado de 0.4 para 0.6 para preencher mais
            user_img = user_img.resize((target_size, target_size), Image.LANCZOS)

            # Criar uma máscara circular
            mask = Image.new('L', (target_size, target_size), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, target_size, target_size), fill=255)
            
            # Posição no canto inferior direito, com uma pequena margem proporcional
            margin = int(target_size * 0.02) # 2% da nova dimensão como margem
            position_x = base_width - target_size - margin
            position_y = base_height - target_size - margin

            base_img.paste(user_img, (position_x, position_y), mask)
        else:
            logger.info(f"Usuário {telegram_id} não possui foto de perfil. Gerando avatar com inicial.")
            
            # 1. Obter nome do usuário para a inicial
            user = await context.bot.get_chat(telegram_id)
            initial = user.first_name[0].upper() if user.first_name else '?'

            # 2. Definir tamanho e criar a imagem do avatar
            base_width, base_height = base_img.size
            target_size = int(min(base_width, base_height) * 0.6)
            
            # 3. Escolher uma cor de fundo baseada no ID do usuário para consistência
            colors = [
                (255, 105, 97), (255, 182, 193), (255, 204, 153), (204, 255, 153),
                (173, 216, 230), (204, 153, 255), (255, 153, 204), (153, 255, 204)
            ]
            bg_color = colors[telegram_id % len(colors)]

            # 4. Desenhar o avatar
            avatar_img = Image.new('RGBA', (target_size, target_size), (255, 255, 255, 0))
            draw = ImageDraw.Draw(avatar_img)
            draw.ellipse((0, 0, target_size, target_size), fill=bg_color)

            # 5. Adicionar a inicial no centro
            try:
                font_size = int(target_size * 0.6)
                font = ImageFont.truetype("arial.ttf", font_size)
            except IOError:
                logger.warning("Fonte 'arial.ttf' não encontrada, usando fonte padrão.")
                font = ImageFont.load_default()

            bbox = draw.textbbox((0, 0), initial, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            text_x = (target_size - text_width) / 2
            text_y = (target_size - text_height) / 2 - bbox[1]
            draw.text((text_x, text_y), initial, font=font, fill=(255, 255, 255))

            # 6. Colar o avatar gerado na imagem base
            base_img.paste(avatar_img, (base_width - target_size - int(target_size * 0.02), base_height - target_size - int(target_size * 0.02)), avatar_img)

        # Salvar imagem final
        # Converte para RGB antes de salvar como JPEG para evitar problemas com o canal alfa
        if base_img.mode == 'RGBA':
            base_img = base_img.convert('RGB')
        
        base_img.save(output_path, "JPEG")
        return output_path

    except Exception as e:
        logger.error(f"Erro ao gerar imagem de canal personalizada para {telegram_id}: {e}")
        # Retorna a imagem padrão se houver erro
        return base_image_path