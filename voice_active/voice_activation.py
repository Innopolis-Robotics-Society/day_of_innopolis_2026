#!/usr/bin/env python3
"""
Голосовая активация робота (только русский язык).
Фраза состоит из 3 этапов.

Внешнее использование:
    from voice_activator import VoiceActivator
    ok, transcript = VoiceActivator().listen()
    # ok == True, transcript == всё услышанное до и включая фразу активации
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
# Настройки
# ─────────────────────────────────────────────
DEVICE_NAME    = 11          # 9 - micro, 11 - laptop
DEVICE_RATE    = 44100
VOSK_RATE      = 16000
BLOCK_SIZE     = 8000 * DEVICE_RATE // VOSK_RATE

MODEL_PATH     = "voice_active/model_ru"
PHRASE_TIMEOUT = 5.0        # секунды между этапами
MIC_GAIN       = 1.1        # усиление микрофона

# ─────────────────────────────────────────────
# Фраза: 3 этапа — любое слово из набора засчитывается
# ─────────────────────────────────────────────
PHRASE_STAGES = [
    {"words": {"жду", "что", "что-то"},              "label": "жду / что"},
    {"words": {"твой", "твоего"},                    "label": "твой / твоего"},
    {"words": {"автограф", "автографа", "фотограф"}, "label": "автограф / автографа"},
]


# ─────────────────────────────────────────────
# Детектор фразы
# ─────────────────────────────────────────────
class PhraseDetector:
    def __init__(self, stages: list, timeout: float):
        self.stages     = stages
        self.timeout    = timeout
        self._step      = 0
        self._last_time = 0.0
        self._lock      = threading.Lock()

    def feed(self, word: str) -> bool:
        """Передай слово. Возвращает True если фраза завершена."""
        word = word.lower()
        with self._lock:
            now = time.time()

            # Сброс по таймауту
            if self._step > 0 and (now - self._last_time) > self.timeout:
                print(f"  ⏱ Таймаут, сброс на этап 1", flush=True)
                self._step = 0

            # Слово совпадает с текущим этапом
            if word in self.stages[self._step]["words"]:
                self._step += 1
                self._last_time = now
                print(f"  ✓ Этап {self._step}/{len(self.stages)} — '{word}'", flush=True)
                if self._step == len(self.stages):
                    self._step = 0
                    return True
                return False

            # Слово из более раннего этапа — перезапуск с нужного места
            for i in range(self._step):
                if word in self.stages[i]["words"]:
                    print(f"  ↺ Слово из этапа {i+1}, перезапуск с этапа {i+2}", flush=True)
                    self._step = i + 1
                    self._last_time = now
                    break

        return False

    def reset(self):
        with self._lock:
            self._step      = 0
            self._last_time = 0.0


# ─────────────────────────────────────────────
# Основной класс
# ─────────────────────────────────────────────
class VoiceActivator:
    def __init__(self):
        print(f"Загрузка модели: {MODEL_PATH} ...", flush=True)
        self._model = Model(model_path=MODEL_PATH)
        print("Модель загружена.", flush=True)

    # ──────────────────────────────────────────
    # Публичный метод для внешнего использования
    # ──────────────────────────────────────────
    def listen(self) -> tuple[bool, str]:
        """
        Запускает микрофон и распознавание, блокирует вызывающий поток
        до момента, когда фраза активации будет услышана.

        Возвращает:
            (True, transcript) — фраза услышана;
                                  transcript — всё, что было распознано
                                  с начала прослушивания включая саму фразу.

        Пример:
            ok, text = VoiceActivator().listen()
            print(text)  # "привет что твой автограф пожалуйста"
        """
        detector     = PhraseDetector(PHRASE_STAGES, PHRASE_TIMEOUT)
        rec          = KaldiRecognizer(self._model, VOSK_RATE)
        rec.SetWords(True)

        audio_queue  = queue.Queue()
        done_event   = threading.Event()
        transcript_parts: list[str] = []   # финальные фразы по порядку
        cooldown     = 2.0
        last_activation = [0.0]            # список для записи из вложенной функции

        # — аудио-колбэк —————————————————————
        def _audio_callback(indata, frames, time_info, status):
            if status:
                print(f"[audio] {status}", flush=True)
            audio     = np.frombuffer(bytes(indata), dtype=np.int16)
            resampled = soxr.resample(audio.astype(np.float32), DEVICE_RATE, VOSK_RATE)
            amplified = np.clip(resampled * MIC_GAIN, -32768, 32767)
            audio_queue.put(amplified.astype(np.int16).tobytes())

        # — цикл распознавания ————————————————
        def _recognize_loop():
            while not done_event.is_set():
                try:
                    data = audio_queue.get(timeout=0.5)
                except queue.Empty:
                    continue

                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    text   = result.get("text", "").strip()
                    if text:
                        print(f"[ru] {text}", flush=True)
                        transcript_parts.append(text)
                        _check_words(text)
                else:
                    partial = json.loads(rec.PartialResult())
                    text    = partial.get("partial", "").strip()
                    if text:
                        print(f"[ru] ...{text}", flush=True)
                        # партиалы не добавляем в transcript — только для детектора
                        _check_words(text)

        def _check_words(text: str):
            for word in text.lower().split():
                now = time.time()
                if now - last_activation[0] < cooldown:
                    continue
                if detector.feed(word):
                    last_activation[0] = now
                    print(f"\n🤖 АКТИВАЦИЯ! Слово: '{word}'\n", flush=True)
                    done_event.set()
                    return

        # — запуск ————————————————————————————
        worker = threading.Thread(target=_recognize_loop, daemon=True)
        worker.start()

        stream = sd.RawInputStream(
            samplerate=DEVICE_RATE,
            blocksize=BLOCK_SIZE,
            device=DEVICE_NAME,
            dtype="int16",
            channels=1,
            callback=_audio_callback,
        )

        print("=" * 50, flush=True)
        print("Слушаю фразу по этапам:", flush=True)
        for i, stage in enumerate(PHRASE_STAGES):
            print(f"  Этап {i+1}: {stage['label']}", flush=True)
        print(f"Таймаут между этапами: {PHRASE_TIMEOUT}с", flush=True)
        print("=" * 50, flush=True)

        with stream:
            done_event.wait()   # ждём активации — поток не занят

        worker.join(timeout=2.0)

        transcript = " ".join(transcript_parts).strip()
        return True, transcript


# ─────────────────────────────────────────────
# Точка входа (для ручного запуска / теста)
# ─────────────────────────────────────────────
if __name__ == "__main__":
    activator = VoiceActivator()
    try:
        ok, text = activator.listen()
        print(f"\nРезультат: ok={ok}")
        print(f"Транскрипт: «{text}»")
    except KeyboardInterrupt:
        print("\nОстановка.")
    try:
        ok, text = activator.listen()
        print(f"\nРезультат: ok={ok}")
        print(f"Транскрипт: «{text}»")
    except KeyboardInterrupt:
        print("\nОстановка.")