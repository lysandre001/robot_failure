# YouTube EN subset BERTopic + RoBERTa (2026-11-16_youtube_en_robot_imagination_self_bertopic)

## Corpus
- Source: labeled Phase1 clean comments (two YouTube batches).
- Gate: `language==en` and `subject_labels` intersects `{Robot, Imagination about Robots, Self}`.
- N=28,096 L1 English comments (Robot=14,267, Imagination=12,520, Self=5,891; overlapping).

## Method
- Embedding: `sentence-transformers/all-MiniLM-L6-v2`
- Clustering: UMAP(5D) + HDBSCAN; sensitivity MCS=[30, 50, 80, 100, 200]; **selected MCS=80**
- Outliers kept as topic `-1` (n=11,658, 41.5%); not force-assigned.
- Sentiment: `cardiffnlp/twitter-roberta-base-sentiment-latest` → negative/neutral/positive.
- Subject labels above are corpus gates only; topics are induced bottom-up.

## Overall sentiment
- negative=42.7%, neutral=41.0%, positive=16.3%

## Selected solution (MCS=80)
- Topics (excl. -1): 60

| topic | n | terms | neg | neu | pos | robot% | imag% | self% |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 0 | 1450 | china robots, chinese robot, china, chinese | 0.55 | 0.28 | 0.17 | 0.40 | 0.46 | 0.16 |
| 1 | 1003 | usain bolt, beat record, faster bolt, bolt | 0.23 | 0.54 | 0.23 | 0.82 | 0.07 | 0.32 |
| 2 | 953 | guns, rifles, weapons, machine guns | 0.51 | 0.41 | 0.08 | 0.07 | 0.94 | 0.11 |
| 3 | 895 | terminator, terminators, james cameron, connor | 0.46 | 0.42 | 0.12 | 0.12 | 0.91 | 0.14 |
| 4 | 686 | cars faster, faster human, faster humans, faster people | 0.32 | 0.50 | 0.17 | 0.76 | 0.10 | 0.44 |
| 5 | 660 | running like, run like, runs like, ran like | 0.23 | 0.60 | 0.17 | 0.86 | 0.08 | 0.37 |
| 6 | 637 | end humanity, end humans, end human, end world | 0.77 | 0.13 | 0.11 | 0.09 | 0.48 | 0.70 |
| 7 | 587 | olympics, olympic, robots compete, watch robots | 0.35 | 0.36 | 0.28 | 0.34 | 0.59 | 0.20 |
| 8 | 553 | remote controlled, remote controls, remote control, control  | 0.39 | 0.57 | 0.04 | 0.96 | 0.04 | 0.02 |
| 9 | 545 | skynet, sky, net, eye | 0.28 | 0.49 | 0.23 | 0.04 | 0.98 | 0.10 |
| 10 | 446 | scary, scary stuff, frightening, scariest | 0.78 | 0.10 | 0.12 | 0.78 | 0.11 | 0.20 |
| 11 | 433 | robots make, work robots, need robots, robots need | 0.58 | 0.27 | 0.15 | 0.12 | 0.89 | 0.33 |
| 12 | 415 | robots faster, running robot, robot run, running robots | 0.40 | 0.45 | 0.15 | 0.72 | 0.33 | 0.26 |
| 13 | 375 | ai, ai just, ai robot, humans ai | 0.53 | 0.34 | 0.14 | 0.31 | 0.67 | 0.25 |
| 14 | 331 | make laugh, stop laughing, laugh years, don laugh | 0.56 | 0.25 | 0.18 | 0.16 | 0.77 | 0.34 |
| 15 | 285 | robot army, army robots, robot soldiers, military robots | 0.53 | 0.36 | 0.11 | 0.06 | 0.96 | 0.14 |
| 16 | 264 | laundry, washing, fold, folding | 0.39 | 0.48 | 0.13 | 0.23 | 0.77 | 0.16 |
| 17 | 251 | drunk, drunken, drinks, drink | 0.23 | 0.61 | 0.16 | 0.74 | 0.04 | 0.34 |
| 18 | 232 | switch, button, controls, turn | 0.49 | 0.46 | 0.05 | 0.85 | 0.17 | 0.06 |
| 19 | 226 | bro, bro just, ass, guy | 0.46 | 0.40 | 0.15 | 0.98 | 0.01 | 0.04 |
| 20 | 204 | impressive, isn impressive, pretty impressive, impressive th | 0.19 | 0.06 | 0.75 | 0.94 | 0.03 | 0.06 |
| 21 | 201 | robot, robot robots, does robot, robot need | 0.32 | 0.64 | 0.03 | 0.84 | 0.17 | 0.03 |
| 22 | 192 | irobot, like irobot, isn far, robot | 0.22 | 0.60 | 0.18 | 0.11 | 0.89 | 0.07 |
| 23 | 181 | clankers, clanker, club, bro | 0.65 | 0.28 | 0.07 | 0.62 | 0.37 | 0.20 |
| 24 | 177 | technology, technologically, tech, high tech | 0.43 | 0.20 | 0.37 | 0.32 | 0.60 | 0.26 |

## Provisional mega-topic grouping
Analyst merge from keywords + examples. Not dual-coded; no Cohen's κ.

- **Awe_Reaction** (topics 20; n=204)
- **Control_Program_Surveillance** (topics 8, 12, 18, 58; n=1,284)
- **Creepy_Uncanny** (topics 10, 50; n=548)
- **Future_Imagination** (topics 22, 24, 33, 38; n=645)
- **Gender_Body_Identity** (topics 28, 40, 41; n=414)
- **Jobs_Labor_Displacement** (topics 11, 13, 16, 25, 27, 36; n=1,544)
- **Performance_Race_Ability** (topics 4, 5, 7, 9, 17, 23, 29, 30, 32, 42, 44, 46, 54; n=3,789)
- **Religion_God** (topics 49; n=103)
- **Robot_General_Other** (topics 21, 35, 39, 53, 56, 59; n=736)
- **Self_Personal_Stance** (topics 14, 26, 37, 45, 48, 51; n=943)
- **War_Military_Weapon** (topics 0, 1, 2, 3, 6, 15, 19, 31, 34, 43, 47, 52, 55, 57; n=6,228)

