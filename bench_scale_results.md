# Bench scale — boucle fermée, chaînes de I

| P | tokens init | tokens max | étapes | Python ms | C ms | speedup |
|---|---|---|---|---|---|---|
| 5 | 14 | 14 | 4 | 111 | 34 | 3.3 |
| 25 | 74 | 74 | 24 | 817 | 219 | 3.7 |
| 50 | 149 | 149 | 49 | 2814 | 659 | 4.3 |
| 100 | 299 | 299 | 99 | 10059 | 1754 | 5.7 |
| 150 | 449 | 449 | 149 | 17700 | 2198 | 8.1 |
| m55 | 36 | 83 | 13 | 1131 | 120 | 9.4 |

Mode production (sans oracle par étape) ; NF = I vérifiée ; traces identiques entre moteurs. Famille choisie pour rester dans l'enveloppe du compteur de balance (finding n°8 : dérive du discharge sur les longs sous-termes).
