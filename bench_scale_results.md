# Bench scale — boucle fermée, chaînes de I

| P | tokens init | tokens max | étapes | Python ms | C ms | speedup |
|---|---|---|---|---|---|---|
| 5 | 14 | 14 | 4 | 82 | 23 | 3.6 |
| 25 | 74 | 74 | 24 | 579 | 153 | 3.8 |
| 50 | 149 | 149 | 49 | 1669 | 322 | 5.2 |
| 100 | 299 | 299 | 99 | 6729 | 1112 | 6.0 |
| 150 | 449 | 449 | 149 | 20154 | 2461 | 8.2 |
| m55 | 36 | 83 | 13 | 1363 | 120 | 11.4 |

Mode production (sans oracle par étape) ; NF = I vérifiée ; traces identiques entre moteurs. Famille choisie pour rester dans l'enveloppe du compteur de balance (finding n°8 : dérive du discharge sur les longs sous-termes).
