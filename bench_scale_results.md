# Bench scale — boucle fermée, chaînes de I

| P | tokens init | tokens max | étapes | Python ms | C ms | speedup |
|---|---|---|---|---|---|---|
| 5 | 14 | 14 | 4 | 69 | 22 | 3.1 |
| 25 | 74 | 74 | 24 | 499 | 133 | 3.8 |
| 50 | 149 | 149 | 49 | 1428 | 290 | 4.9 |
| 100 | 299 | 299 | 99 | 5794 | 959 | 6.0 |
| 150 | 449 | 449 | 149 | 13041 | 1507 | 8.7 |
| m55 | 36 | 83 | 13 | 795 | 79 | 10.0 |

Mode production (sans oracle par étape) ; NF = I vérifiée ; traces identiques entre moteurs. Famille choisie pour rester dans l'enveloppe du compteur de balance (finding n°8 : dérive du discharge sur les longs sous-termes).
