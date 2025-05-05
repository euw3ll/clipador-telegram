from configuracoes import GATEWAY_PAGAMENTO

if GATEWAY_PAGAMENTO == "KIRVANO":
    # A Kirvano não possui API de criação ou consulta de pagamento
    # As cobranças são feitas por links fixos e validadas via Webhook
    def criar_pagamento_pix(*args, **kwargs):
        raise NotImplementedError("❌ O gateway 'KIRVANO' não permite gerar Pix via API.")

    def criar_pagamento_cartao(*args, **kwargs):
        raise NotImplementedError("❌ O gateway 'KIRVANO' não permite gerar Cartão via API.")

    def consultar_pagamento(*args, **kwargs):
        raise NotImplementedError("❌ O gateway 'KIRVANO' não permite consultar status de pagamento via API.")

elif GATEWAY_PAGAMENTO == "MERCADOPAGO":
    from core.gateway.mercadopago import (
        criar_pagamento_pix,
        criar_pagamento_cartao,
        consultar_pagamento
    )

else:
    raise ValueError(f"❌ Gateway de pagamento '{GATEWAY_PAGAMENTO}' não é suportado. Verifique o valor em configuracoes.py.")
