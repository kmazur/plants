# Roadmap: bogatsze przechwytywanie (RAW-metryki i multi-frame)

Notatka planistyczna — nic z tego nie jest jeszcze zaimplementowane. Kontekst:
scena jest statyczna (sztywny montaż, brak ruchu), snapshot to oneshot co 60 s,
ekspozycja jest po zbieżności AE przypinana (`camera.py`), więc kolejne klatki
w jednym ujęciu są ze sobą zgodne fotometrycznie.

## 1. RAW → metryki (bez trzymania RAW w historii)

**Cel:** prawdziwe, liniowe dane do analizy (kolor/kondycja roślin, luminancja
per-region), których JPEG (gamma + tonemap + AWB + 8 bit) nie daje.

**Czego RAW NIE trzeba do "prawdziwej jasności":** to już mamy — `cam.lux`
(estymata AEC, niezależna od ekspozycji, 0.1 nocą → ~4500 w południe), od teraz
na wykresie w skali log. RAW potrzebny dopiero do koloru/przestrzeni/fotometrii.

**Plan:**
- Próbkować RAW **rzadko** (np. co 15–30 min lub N/dobę), nie co minutę
  (RAW z tej matrycy ~18–24 MB/klatkę → ~25–35 GB/dobę przy 60 s = wykluczone).
- Z RAW liczyć metryki i **kasować plik**, zostawiając tylko liczby:
  - luminancja znormalizowana = (mean_raw − SensorBlackLevel) / (exp_s × gain),
  - średnie liniowe RGB per-region (strefy roślin), indeks zieleni,
  - opcjonalnie histogram / klipowanie.
- Ewentualnie trzymać kilka pełnych RAW/dobę z krótką retencją do wglądu.
- picamera2: `capture_array("raw")` + `capture_metadata()` dla black-level/exp.

## 2. Multi-frame (scena statyczna → łączenie kilku klatek)

Bez ruchu nie ma ghostingu/aligncentu — techniki temporalne stosują się czysto.

### 2a. Odszumianie przez uśrednianie (NAJWIĘKSZY, NAJTAŃSZY zysk — noc)
- Szum maleje ~1/√N. Uśrednienie 9 klatek ≈ 3× mniej szumu ≈ jak 9× więcej
  światła, bez wydłużania ekspozycji.
- Noc działa na gain=16 (bardzo szumna) → stacking 8–16 klatek da wyraźną
  poprawę jakości i ustabilizuje metryki (brightness, canopy, ostrość).
- Implementacja: po settle/pin zrób N × `capture_array()`, uśrednij (akumulacja
  int32/float w numpy), zapisz jeden JPEG. Najpoprawniej w domenie liniowej/RAW,
  ale uśrednianie przetworzonego RGB też skutecznie odszumia i jest prostsze.
- Synergia z przypiętą ekspozycją: wszystkie N klatek mają tę samą ekspozycję.
- Koszt: dłuższe "camera busy" (N klatek + ~150 MB transient na full-res),
  przy 60 s cadence bez problemu; lekka rywalizacja z podglądem live (lock).

### 2b. HDR (bracketing ekspozycji) — opcjonalnie
- Dla scen o dużym kontraście (jasne niebo + zacieniona roślina): 3 ekspozycje
  + tonemap. Sensowne tylko jeśli realnie widać przepalenia/zgaszone cienie.
  Większa złożoność (tonemapping). Na razie nie priorytet.

### 2c. Super-rozdzielczość — POMIŃ
- Klasyczna multi-frame SR wymaga sub-pikselowego drgania między klatkami.
  Sztywny montaż = brak drgania = brak realnego zysku detalu. Uśrednianie daje
  czystszy, ale NIE bardziej szczegółowy obraz.

### 2d. "Wyższa rozdzielczość" — to osobny tryb, nie multi-frame
- Matryca ma tryb pełnej rozdzielczości; to kwestia trybu przechwytywania i
  dysku, niezależna od łączenia klatek. Multi-frame nie dodaje rozdzielczości.

### 2e. Ostrzejsze krawędzie
- Same uśrednianie nie wyostrza — ale po odszumieniu można bezpiecznie dodać
  delikatny unsharp mask (mniej szumu do wzmocnienia → czystsze krawędzie).
  Realna ostrość zależy głównie od ostrości obiektywu/fokusu.

## Rekomendowana kolejność
1. (zrobione) Lux (log) jako prawdziwe światło na wykresie.
2. **Nocny stacking 8–16 klatek** — największy zysk jakości, wykorzystuje brak
   ruchu, dokłada się do już przypiętej ekspozycji. Konfigurowalny `night_stack_frames`.
3. Lekki dzienny stacking (2–4) tylko jeśli metryki/obraz tego wymagają.
4. RAW→metryki rzadkim próbkowaniem, gdy pojawi się potrzeba analizy koloru/roślin.
5. HDR/unsharp tylko jeśli obserwacje pokażą taką potrzebę.
