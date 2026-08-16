# ASCEND

**ASCEND** is a real-life progression app that turns self-improvement into an RPG-style system.

## Features

- Track **Gym, Study and Social** activities
- Earn XP and progress through **E → D → C → B → A → S → NATIONAL** ranks
- **Daily quests** with real progress and 24-hour resets
- **Gym, Study and Social history** to track long-term improvement
- **Status screen** with circular progression and attributes
- **Rank badges** that unlock with progression
- Equipped rank badge becomes the player's **profile picture**
- **Arena** with separate competitive ranking
- Anime/System-inspired HUD, backgrounds and animations
- **Webcam System Scan** with face detection and visual jawline/cheekbone/eye guides
- Click and level-up sound effects

## Rank Progression

```text
E-RANK        0 XP
D-RANK     1500 XP
C-RANK     4000 XP
B-RANK     8000 XP
A-RANK    14000 XP
S-RANK    22000 XP
NATIONAL  35000 XP
```

Progression is intentionally slow so higher ranks represent long-term consistency.

## Installation

```bash
python -m pip install -r requirements.txt
python main.py
```

## Project Structure

```text
ASCEND/
├── main.py
├── ui.py
├── database.py
├── ascend.db
└── assets/
    ├── badges/
    ├── sounds/
    └── backgrounds
```

### Custom Assets

Replace the files in:

```text
assets/badges/
assets/sounds/
assets/
```

using the existing filenames.

## Webcam Scan

The System Scan uses OpenCV to detect a face and display a futuristic analysis HUD.

The facial lines are **visual guides only**. Actual Strength, Intelligence, Social and other attributes come from the player's tracked ASCEND activity.

## Database

`ascend.db` stores player profile, XP, levels, ranks, activity history, quests, Arena points and equipped badges.

> **You are the character.**
