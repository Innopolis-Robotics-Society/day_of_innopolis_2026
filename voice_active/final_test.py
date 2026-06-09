from voice_activator import VoiceActivator

activator = VoiceActivator()          # загружает модель один раз
ok, text = activator.listen()         # блокирует до активации
print(text)                           # "привет что твой автограф спасибо"