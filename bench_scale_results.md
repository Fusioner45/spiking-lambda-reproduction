# Bench scale — boucle fermée, chaînes de I

| P | tokens init | tokens max | étapes | Python ms | C ms | speedup |
|---|---|---|---|---|---|---|
| 5 | 14 | 14 | 4 | 77 | 25 | 3.1 |
| 25 | 74 | 74 | 24 | 548 | 139 | 3.9 |
| 50 | 149 | 149 | 49 | 1528 | 302 | 5.1 |
| 100 | 299 | 299 | 99 | 4973 | 749 | 6.6 |
| 150 | 449 | 449 | 149 | 10491 | 1157 | 9.1 |
| m55 | 36 | 83 | 13 | 700 | 74 | 9.5 |

Mode production (sans oracle par étape) ; NF = I vérifiée ; traces identiques entre moteurs. Famille choisie pour rester dans l'enveloppe du compteur de balance (finding n°8 : dérive du discharge sur les longs sous-termes).
