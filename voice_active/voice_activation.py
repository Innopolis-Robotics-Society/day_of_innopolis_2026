#!/usr/bin/env python3
"""
Модуль голосовой активации робота.
Одновременно слушает русский и английский язык.
Фраза состоит из 3 этапов — каждый этап принимает слова на RU или EN.
"""

import queue
import threading
import json
import time
import numpy as np
import sounddevice as sd
import soxr
from vosk import Model, KaldiRecognizer

# ─────────────────────────────────────────────
# Настройки устройства
# ─────────────────────────────────────────────
DEVICE_NAME = 24#"HECATE"
DEVICE_RATE = 48000
VOSK_RATE   = 16000
BLOCK_SIZE  = 8000*DEVICE_RATE//VOSK_RATE

MODEL_RU = "model_ru"
MODEL_EN = "model_en"

# Таймаут между этапами (секунды)
PHRASE_TIMEOUT = 5.0

# ─────────────────────────────────────────────
# Фраза: 3 этапа, каждый — набор слов RU и EN
# Любое слово из набора засчитывается как этап
# ─────────────────────────────────────────────
PHRASE_STAGES = [
    {
        "ru": {"жду", "что", "что-то"},
        "en": {"waiting", "wait"},
        "label": "жду/что | waiting/wait",
    },
    {
        "ru": {"твой", "твоего"},
        "en": {"your", "toy"},
        "label": "твой/твоего | your",
    },
    {
        "ru": {"автограф", "автографа", "фотограф", "фотографа"},
        "en": {"autograph", "october", "target"},
        "label": "автограф/автографа | autograph",
    },
]


# ─────────────────────────────────────────────
# Глобальная очередь вывода — один поток пишет
# ─────────────────────────────────────────────
_print_queue: queue.Queue = queue.Queue()

def _print_worker():
    while True:
        msg = _print_queue.get()
        if msg is None:
            break
        print(msg, flush=True)

_print_thread = threading.Thread(target=_print_worker, daemon=True)
_print_thread.start()

def log(msg: str):
    _print_queue.put(msg)


# ─────────────────────────────────────────────
# Callback активации
# ─────────────────────────────────────────────
def on_activation(word: str, lang: str):
    """Замени на отправку сигнала роботу."""
    log(f"\n🤖 АКТИВАЦИЯ! Слово: '{word}' (язык: {lang})\n")


# ─────────────────────────────────────────────
# Единый детектор фразы (общий для RU и EN)
# ─────────────────────────────────────────────
class PhraseDetector:
    def __init__(self, stages: list, timeout: float):
        self.stages  = stages
        self.timeout = timeout
        self._step      = 0
        self._last_time = 0.0
        self._lock      = threading.Lock()

    def feed(self, word: str, lang: str) -> bool:
        """Передай одно слово и язык. Возвращает True если фраза завершена."""
        word = word.lower()
        with self._lock:
            now = time.time()

            # Таймаут — сброс если слишком долгая пауза
            if self._step > 0 and (now - self._last_time) > self.timeout:
                log(f"  ⏱ Таймаут, сброс на этап 1")
                self._step = 0

            current_stage = self.stages[self._step]

            # Слово из текущего этапа — переходим дальше
            if word in current_stage.get(lang, set()):
                self._step += 1
                self._last_time = now
                log(f"  ✓ Этап {self._step}/{len(self.stages)} — '{word}' [{lang.upper()}]")
                if self._step == len(self.stages):
                    self._step = 0
                    return True
                return False

            # Слово из этапа 1 во время этапа 2 или 3 — засчитываем как этап 1, переходим на этап 2
            if self._step > 0:
                for i in range(self._step):
                    if word in self.stages[i].get(lang, set()):
                        log(f"  ↺ Слово из этапа {i+1}, перезапуск с этапа {i+2}")
                        self._step = i + 1
                        self._last_time = now
                        break

        return False

    def reset(self):
        with self._lock:
            self._step = 0
            self._last_time = 0.0


# ─────────────────────────────────────────────
# Поток распознавания одного языка
# ─────────────────────────────────────────────
class RecognizerThread(threading.Thread):
    def __init__(self, model_path: str, lang: str, detector: PhraseDetector):
        super().__init__(daemon=True)
        self.lang     = lang
        self.detector = detector
        self.audio_queue = queue.Queue()
        self._stop_event  = threading.Event()
        self._cooldown    = 2.0
        self._last_activation = 0.0

        log(f"[{lang}] Загрузка модели: {model_path} ...")
        self.model = Model(model_path=model_path)
        self.rec   = KaldiRecognizer(self.model, VOSK_RATE)
        self.rec.SetWords(True)
        log(f"[{lang}] Модель загружена.")

    def put_audio(self, data: bytes):
        self.audio_queue.put(data)

    def stop(self):
        self._stop_event.set()

    def _process_words(self, text: str, is_partial: bool):
        for word in text.lower().split():
            now = time.time()
            if now - self._last_activation < self._cooldown:
                continue
            if self.detector.feed(word, self.lang):
                self._last_activation = now
                on_activation(word, self.lang)

    def run(self):
        while not self._stop_event.is_set():
            try:
                data = self.audio_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if self.rec.AcceptWaveform(data):
                result = json.loads(self.rec.Result())
                text = result.get("text", "").strip()
                if text:
                    log(f"[{self.lang}] {text}")
                    self._process_words(text, is_partial=False)
            else:
                partial = json.loads(self.rec.PartialResult())
                text = partial.get("partial", "").strip()
                if text:
                    log(f"[{self.lang}] ...{text}")
                    self._process_words(text, is_partial=True)


# ─────────────────────────────────────────────
# Основной класс
# ─────────────────────────────────────────────
class VoiceActivator:
    def __init__(self):
        self._detector = PhraseDetector(PHRASE_STAGES, PHRASE_TIMEOUT)
        self.ru = RecognizerThread(MODEL_RU, "ru", self._detector)
        self.en = RecognizerThread(MODEL_EN, "en", self._detector)
        self._stream = None

    def _audio_callback(self, indata, frames, time, status):
        if status:
            log(f"[audio] {status}")
        audio = np.frombuffer(bytes(indata), dtype=np.int16)
        resampled = soxr.resample(audio.astype(np.float32), DEVICE_RATE, VOSK_RATE)
        data = resampled.astype(np.int16).tobytes()
        self.ru.put_audio(data)
        self.en.put_audio(data)

    def start(self):
        log("Запуск потоков распознавания...")
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

        log("=" * 50)
        log("Жду фразу по этапам:")
        for i, stage in enumerate(PHRASE_STAGES):
            log(f"  Этап {i+1}: {stage['label']}")
        log(f"Таймаут между этапами: {PHRASE_TIMEOUT}с")
        log("Ctrl+C для остановки.")
        log("=" * 50)

    def stop(self):
        if self._stream:
            self._stream.stop()
            self._stream.close()
        self.ru.stop()
        self.en.stop()
        log("Остановлено.")


# ─────────────────────────────────────────────
# Точка входа
# ─────────────────────────────────────────────
if __name__ == "__main__":
    activator = VoiceActivator()
    try:
        activator.start()
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nОстановка...")
    finally:
        activator.stop()
        _print_queue.put(None)