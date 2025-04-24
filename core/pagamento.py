from configuracoes import GATEWAY_PAGAMENTO

if GATEWAY_PAGAMENTO == "KIRVANO":
    from core.gateway.kirvano import (
        criar_pagamento_pix,
        criar_pagamento_cartao,
        consultar_pagamento
    )

elif GATEWAY_PAGAMENTO == "MERCADOPAGO":
    from core.gateway.mercadopago import (
        criar_pagamento_pix,
        criar_pagamento_cartao,
        consultar_pagamento
    )

else:
    raise ValueError(f"❌ Gateway de pagamento '{GATEWAY_PAGAMENTO}' não é suportado. Verifique o valor em configuracoes.py.")
