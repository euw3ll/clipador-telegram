from core.launcher import iniciar_clipador

try:
    iniciar_clipador()
except KeyboardInterrupt:
    pass
finally:
    print("\n🛑 Clipador encerrado.")
