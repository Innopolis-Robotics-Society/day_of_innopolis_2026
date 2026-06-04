#!/usr/bin/env python3
"""
Модуль голосовой активации робота.
Одновременно слушает русский и английский язык.
При обнаружении слова из списка вызывает on_activation().
"""

import queue
import threading
import json
import numpy as np
import sounddevice as sd
import soxr
from vosk import Model, KaldiRecognizer
import time

# for i, dev in enumerate(sd.query_devices()):
#     if dev['max_input_channels'] > 0:
#         print(f"{i}: {dev['name']}  (rate: {int(dev['default_samplerate'])})")

# ─────────────────────────────────────────────
# Настройки
# ─────────────────────────────────────────────
DEVICE_NAME     = 8#"HECATE"          # подстрока имени устройства
DEVICE_RATE     = 44100             # частота микрофона
VOSK_RATE       = 16000             # частота Vosk
BLOCK_SIZE      = 8000 * DEVICE_RATE // VOSK_RATE             # blocksize (DEVICE_RATE * 8000 / VOSK_RATE)

MODEL_RU        = "model_ru"        # путь к русской модели
MODEL_EN        = "model_en"        # путь к английской модели

# Слова-активаторы (в нижнем регистре)
WAKE_WORDS_RU = {
    "подпиши", "подписать", "подпись", "подписывай",
    "нарисуй", "рисуй", "нарисовать",
    "робот", "активируйся", "начинай", "поехали", "давай",
    "открытку", "открытка", "напиши", "написать",

    "стоп", "остановись", "хватит", "отмена"
}

WAKE_WORDS_EN = {
    "sign", "signing", "signed", "write", "writing", "draw", "drawing",
    "robot", "activate", "start", "go", "begin", "hello", "hey",
    "card", "postcard", "greeting", "message", "note",
    
    "stop", "cancel", "enough", "abort"
}

COOLDOWN = 2
# ─────────────────────────────────────────────
# Callback — срабатывает при обнаружении слова
# ─────────────────────────────────────────────
def on_activation(word: str, lang: str):
    """Замени этот метод на отправку сигнала роботу."""
    print(f"\n🤖 АКТИВАЦИЯ! Слово: '{word}' (язык: {lang})\n")


# ─────────────────────────────────────────────
# Поток распознавания для одного языка
# ─────────────────────────────────────────────
class RecognizerThread(threading.Thread):
    def __init__(self, model_path: str, wake_words: set, lang: str):
        super().__init__(daemon=True)
        self.lang       = lang
        self.wake_words = wake_words
        self.queue      = queue.Queue()
        self._stop_event = threading.Event()

        print(f"[{lang}] Загрузка модели: {model_path} ...")
        self.model = Model(model_path=model_path)
        self.rec   = KaldiRecognizer(self.model, VOSK_RATE)
        # Ограничиваем словарь — распознавание быстрее и точнее
        self.rec.SetWords(True)
        self._last_activation = 0       # <-- добавь
        self._cooldown = COOLDOWN            # <-- добавь (секунды)
        print(f"[{lang}] Модель загружена.")

    def put_audio(self, data: bytes):
        self.queue.put(data)

    def stop(self):
        self._stop_event.set()

    def _check_wake_words(self, text: str):
        now = time.time()
        if now - self._last_activation < self._cooldown:
            return False                    # ещё в кулдауне — пропускаем
        words = text.lower().split()
        for word in words:
            if word in self.wake_words:
                self._last_activation = now
                on_activation(word, self.lang)
                return True
        return False

    def run(self):
        while not self._stop_event.is_set():
            try:
                data = self.queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if self.rec.AcceptWaveform(data):
                result = json.loads(self.rec.Result())
                text = result.get("text", "").strip()
                if text:
                    print(f"[{self.lang}] Распознано: {text}")
                    self._check_wake_words(text)
            else:
                partial = json.loads(self.rec.PartialResult())
                text = partial.get("partial", "").strip()
                if text:
                    print(f"[{self.lang}] ...{text}", end="\r")
                    # Проверяем wake words и в partial — быстрее реакция
                    self._check_wake_words(text)


# ─────────────────────────────────────────────
# Основной класс — микрофон + оба распознавателя
# ─────────────────────────────────────────────
class VoiceActivator:
    def __init__(self):
        self.ru = RecognizerThread(MODEL_RU, WAKE_WORDS_RU, "RU")
        self.en = RecognizerThread(MODEL_EN, WAKE_WORDS_EN, "EN")
        self._stream = None

    def _audio_callback(self, indata, frames, time, status):
        if status:
            print(f"[audio] {status}")
        # Ресемплинг 44100 → 16000
        audio = np.frombuffer(bytes(indata), dtype=np.int16)
        resampled = soxr.resample(audio.astype(np.float32), DEVICE_RATE, VOSK_RATE)
        data = resampled.astype(np.int16).tobytes()
        # Оба распознавателя получают одинаковые данные
        self.ru.put_audio(data)
        self.en.put_audio(data)

    def start(self):
        print("Запуск потоков распознавания...")
        self.ru.start()
        self.en.start()

        self._stream = sd.RawInputStream(
            samplerate=DEVICE_RATE,
            blocksize=BLOCK_SIZE,
            device=DEVICE_NAME,
            dtype="int16",
            channels=1,
            callback=self._audio_callback,
        )
        self._stream.start()
        print("=" * 50)
        print("Слушаю... Скажи одно из слов:")
        print(f"  RU: {', '.join(sorted(WAKE_WORDS_RU))}")
        print(f"  EN: {', '.join(sorted(WAKE_WORDS_EN))}")
        print("Ctrl+C для остановки.")
        print("=" * 50)

    def stop(self):
        if self._stream:
            self._stream.stop()
            self._stream.close()
        self.ru.stop()
        self.en.stop()
        print("Остановлено.")


# ─────────────────────────────────────────────
# Точка входа
# ─────────────────────────────────────────────
if __name__ == "__main__":
    activator = VoiceActivator()
    try:
        activator.start()
        threading.Event().wait()   # ждём Ctrl+C
    except KeyboardInterrupt:
        print("\nОстановка...")
    finally:
        activator.stop()
