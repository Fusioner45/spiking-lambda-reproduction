# Bench scale — boucle fermée, chaînes de I

| P | tokens init | tokens max | étapes | Python ms | C ms | speedup |
|---|---|---|---|---|---|---|
| 5 | 14 | 14 | 4 | 87 | 27 | 3.3 |
| 25 | 74 | 74 | 24 | 673 | 174 | 3.9 |
| 50 | 149 | 149 | 49 | 2059 | 498 | 4.1 |
| 100 | 299 | 299 | 99 | 8155 | 1567 | 5.2 |
| 150 | 449 | 449 | 149 | 15920 | 1957 | 8.1 |
| m55 | 36 | 83 | 13 | 1154 | 115 | 10.0 |

Mode production (sans oracle par étape) ; NF = I vérifiée ; traces identiques entre moteurs. Famille choisie pour rester dans l'enveloppe du compteur de balance (finding n°8 : dérive du discharge sur les longs sous-termes).
